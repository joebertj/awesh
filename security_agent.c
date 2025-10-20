#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/select.h>
#include <sys/time.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <ctype.h>
#include <regex.h>
#include <errno.h>

// Transparent middleware proxy - intercepts ALL frontend-backend communication
static int running = 1;
static int verbose_level = 0;
static int frontend_socket_fd = -1;  // Frontend connects here
static int backend_socket_fd = -1;   // We connect to backend here
static char backend_socket_path[512];

// Read configuration from ~/.aweshrc and set environment variables
int read_config_and_set_env(void) {
    const char* home = getenv("HOME");
    if (!home) return 0;
    
    char config_path[512];
    snprintf(config_path, sizeof(config_path), "%s/.aweshrc", home);
    
    FILE* config_file = fopen(config_path, "r");
    if (!config_file) {
        return 0;  // Default to silent if file doesn't exist
    }
    
    char line[256];
    while (fgets(line, sizeof(line), config_file)) {
        // Remove newline
        line[strcspn(line, "\n")] = '\0';
        
        // Skip empty lines and comments
        if (line[0] == '\0' || line[0] == '#') continue;
        
        // Parse key=value pairs
        char* equals = strchr(line, '=');
        if (equals) {
            *equals = '\0';
            char* key = line;
            char* value = equals + 1;
            
            // Set environment variable
            setenv(key, value, 1);
            
            // Set verbose level if this is the VERBOSE setting
            if (strcmp(key, "VERBOSE") == 0) {
                verbose_level = atoi(value);
            }
        }
    }
    
    fclose(config_file);
    return verbose_level;
}

// Security patterns for command analysis
static regex_t dangerous_patterns[10];
static regex_t sensitive_patterns[10];
static int dangerous_count = 0;
static int sensitive_count = 0;

void init_security_patterns(void) {
    // Dangerous patterns (high threat)
    regcomp(&dangerous_patterns[dangerous_count++], "rm\\s+-rf\\s+/", REG_EXTENDED);
    regcomp(&dangerous_patterns[dangerous_count++], "sudo\\s+rm\\s+-rf", REG_EXTENDED);
    regcomp(&dangerous_patterns[dangerous_count++], "dd\\s+if=/dev/urandom", REG_EXTENDED);
    regcomp(&dangerous_patterns[dangerous_count++], "mkfs\\s+", REG_EXTENDED);
    regcomp(&dangerous_patterns[dangerous_count++], "fdisk\\s+", REG_EXTENDED);
    
    // Sensitive patterns (medium threat)
    regcomp(&sensitive_patterns[sensitive_count++], "passwd\\s+", REG_EXTENDED);
    regcomp(&sensitive_patterns[sensitive_count++], "chmod\\s+777", REG_EXTENDED);
    regcomp(&sensitive_patterns[sensitive_count++], "chown\\s+", REG_EXTENDED);
    regcomp(&sensitive_patterns[sensitive_count++], "iptables\\s+", REG_EXTENDED);
    regcomp(&sensitive_patterns[sensitive_count++], "systemctl\\s+", REG_EXTENDED);
}

void cleanup_security_patterns(void) {
    for (int i = 0; i < dangerous_count; i++) {
        regfree(&dangerous_patterns[i]);
    }
    for (int i = 0; i < sensitive_count; i++) {
        regfree(&sensitive_patterns[i]);
    }
}

int validate_command(const char* command) {
    // Skip validation for system commands
    if (strncmp(command, "CWD:", 4) == 0 || strcmp(command, "STATUS") == 0 || 
        strncmp(command, "BASH_FAILED:", 12) == 0) {
        return 1; // Always allow system commands
    }
    
    // Check against dangerous patterns
    for (int i = 0; i < dangerous_count; i++) {
        if (regexec(&dangerous_patterns[i], command, 0, NULL, 0) == 0) {
            if (verbose_level >= 1) {
                fprintf(stderr, "🚫 SecurityAgent: BLOCKED dangerous command: %s\n", command);
            }
            return 0; // Block dangerous command
        }
    }
    
    // Check against sensitive patterns
    for (int i = 0; i < sensitive_count; i++) {
        if (regexec(&sensitive_patterns[i], command, 0, NULL, 0) == 0) {
            if (verbose_level >= 1) {
                fprintf(stderr, "🚫 SecurityAgent: BLOCKED sensitive command: %s\n", command);
            }
            return 0; // Block sensitive command
        }
    }
    
    // Additional checks
    if (strstr(command, "rm") && strstr(command, "-rf")) {
        if (verbose_level >= 1) {
            fprintf(stderr, "🚫 SecurityAgent: BLOCKED destructive rm command: %s\n", command);
        }
        return 0;
    }
    
    if (verbose_level >= 2) {
        fprintf(stderr, "✅ SecurityAgent: APPROVED command: %s\n", command);
    }
    return 1; // Allow command
}

int connect_to_backend(void) {
    // Connect to the actual backend
    const char* home = getenv("HOME");
    if (!home) return -1;
    
    snprintf(backend_socket_path, sizeof(backend_socket_path), 
             "%s/.awesh_backend.sock", home);
    
    backend_socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (backend_socket_fd < 0) {
        return -1;
    }
    
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, backend_socket_path, sizeof(addr.sun_path) - 1);
    
    if (connect(backend_socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(backend_socket_fd);
        backend_socket_fd = -1;
        return -1;
    }
    
    return 0;
}

int setup_frontend_socket(void) {
    // Setup socket for frontend to connect to (we act as backend)
    const char* home = getenv("HOME");
    if (!home) return -1;
    
    char frontend_socket_path[512];
    snprintf(frontend_socket_path, sizeof(frontend_socket_path), 
             "%s/.awesh.sock", home);  // Frontend connects to this
    
    // Remove existing socket
    unlink(frontend_socket_path);
    
    frontend_socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (frontend_socket_fd < 0) {
        return -1;
    }
    
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, frontend_socket_path, sizeof(addr.sun_path) - 1);
    
    if (bind(frontend_socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(frontend_socket_fd);
        return -1;
    }
    
    if (listen(frontend_socket_fd, 1) < 0) {
        close(frontend_socket_fd);
        return -1;
    }
    
    return 0;
}

void cleanup_and_exit(int sig __attribute__((unused))) {
    running = 0;
    
    if (frontend_socket_fd >= 0) {
        close(frontend_socket_fd);
    }
    if (backend_socket_fd >= 0) {
        close(backend_socket_fd);
    }
    
    cleanup_security_patterns();
    
    if (verbose_level >= 1) {
        fprintf(stderr, "SecurityAgent: Shutting down\n");
    }
    exit(0);
}

int main() {
    // Setup signal handlers
    signal(SIGINT, cleanup_and_exit);
    signal(SIGTERM, cleanup_and_exit);
    
    // Load configuration and set environment variables
    read_config_and_set_env();
    
    if (verbose_level >= 2) {
        fprintf(stderr, "SecurityAgent: Starting as transparent middleware proxy...\n");
    }
    
    // Initialize security patterns
    init_security_patterns();
    
    // Setup frontend socket (frontend connects here)
    if (setup_frontend_socket() != 0) {
        fprintf(stderr, "SecurityAgent: Failed to setup frontend socket\n");
        return 1;
    }
    
    if (verbose_level >= 2) {
        fprintf(stderr, "SecurityAgent: Frontend socket ready\n");
    }
    
    // Main proxy loop
    while (running) {
        // Wait for frontend connection
        struct sockaddr_un client_addr;
        socklen_t client_len = sizeof(client_addr);
        
        int client_fd = accept(frontend_socket_fd, (struct sockaddr*)&client_addr, &client_len);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            continue;
        }
        
        if (verbose_level >= 2) {
            fprintf(stderr, "SecurityAgent: Frontend connected\n");
        }
        
        // Connect to backend
        if (connect_to_backend() != 0) {
            if (verbose_level >= 1) {
                fprintf(stderr, "SecurityAgent: Failed to connect to backend\n");
            }
            close(client_fd);
            continue;
        }
        
        if (verbose_level >= 2) {
            fprintf(stderr, "SecurityAgent: Connected to backend\n");
        }
        
        // Proxy communication between frontend and backend
        while (running) {
            fd_set readfds;
            struct timeval timeout;
            int max_fd = (client_fd > backend_socket_fd) ? client_fd : backend_socket_fd;
            
            FD_ZERO(&readfds);
            FD_SET(client_fd, &readfds);
            FD_SET(backend_socket_fd, &readfds);
            
            timeout.tv_sec = 1;
            timeout.tv_usec = 0;
            
            int result = select(max_fd + 1, &readfds, NULL, NULL, &timeout);
            
            if (result < 0) {
                if (errno == EINTR) continue;
                perror("select");
                break;
            }
            
            if (result == 0) continue; // Timeout
            
            // Data from frontend to backend
            if (FD_ISSET(client_fd, &readfds)) {
                char buffer[4096];
                ssize_t bytes = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
                if (bytes <= 0) {
                    if (verbose_level >= 2) {
                        fprintf(stderr, "SecurityAgent: Frontend disconnected\n");
                    }
                    break;
                }
                
                buffer[bytes] = '\0';
                
                // Validate command before forwarding to backend
                if (validate_command(buffer)) {
                    // Forward to backend
                    if (send(backend_socket_fd, buffer, bytes, 0) < 0) {
                        if (verbose_level >= 1) {
                            fprintf(stderr, "SecurityAgent: Failed to forward to backend\n");
                        }
                        break;
                    }
                } else {
                    // Block command - send error response to frontend
                    const char* error_msg = "SECURITY_BLOCKED: Command blocked by security agent\n";
                    send(client_fd, error_msg, strlen(error_msg), 0);
                }
            }
            
            // Data from backend to frontend
            if (FD_ISSET(backend_socket_fd, &readfds)) {
                char buffer[4096];
                ssize_t bytes = recv(backend_socket_fd, buffer, sizeof(buffer) - 1, 0);
                if (bytes <= 0) {
                    if (verbose_level >= 2) {
                        fprintf(stderr, "SecurityAgent: Backend disconnected\n");
                    }
                    break;
                }
                
                buffer[bytes] = '\0';
                
                // Forward response to frontend (no validation needed for responses)
                if (send(client_fd, buffer, bytes, 0) < 0) {
                    if (verbose_level >= 1) {
                        fprintf(stderr, "SecurityAgent: Failed to forward to frontend\n");
                    }
                    break;
                }
            }
        }
        
        // Cleanup connection
        close(client_fd);
        if (backend_socket_fd >= 0) {
            close(backend_socket_fd);
            backend_socket_fd = -1;
        }
        
        if (verbose_level >= 2) {
            fprintf(stderr, "SecurityAgent: Connection closed, waiting for next client\n");
        }
    }
    
    cleanup_and_exit(0);
    return 0;
}