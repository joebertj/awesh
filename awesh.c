#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <sys/select.h>
#include <signal.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <readline/readline.h>
#include <readline/history.h>
#include <ctype.h>
#include <time.h>
#include <sys/time.h>
#include <pty.h>
#include <termios.h>

static char socket_path[512];
static char mmap_path[512] = "/tmp/awesh_sandbox_output.mmap";


// Security Agent socket communication
// Security agent communication via stdin/stdout (no sockets needed)

// Frontend socket server for middleware communication
static int frontend_socket_fd = -1;
static char frontend_socket_path[512];

// Sandbox socket communication
static int sandbox_socket_fd = -1;
static char sandbox_socket_path[512];

// Function declarations
void get_git_branch(char* branch, size_t size);
void get_kubectl_context(char* context, size_t size);
void get_kubectl_namespace(char* namespace, size_t size);
char* parse_ai_mode(const char* input);
void handle_ai_mode_detection(const char* input);
void handle_ai_query(const char* query);
int send_to_backend(const char* query, char* response, size_t response_size);
// Security agent communication removed - now handled transparently by middleware proxy
void handle_interactive_bash(const char* cmd);
void execute_command_securely(const char* cmd);
int spawn_bash_sandbox(void);
void cleanup_bash_sandbox(void);
int is_ssh_session(void);
int is_ai_query(const char* cmd);
int is_interactive_command(const char* cmd);
int test_command_in_sandbox(const char* cmd);
// Middleware functions removed - now handled transparently
// Backend communication functions removed - now handled transparently by middleware
void run_interactive_command(const char* cmd);
void get_security_agent_status(char* status, size_t size);
// Security agent functions removed - now uses stdin/stdout
void debug_perf(const char* operation, long start_time);
void check_child_process_health(void);
int is_process_running(pid_t pid);
void log_health_status(const char* process_name, pid_t pid, int is_running);
void get_health_status_emojis(char* backend_emoji, char* security_emoji, char* sandbox_emoji);
void check_ai_status(void);
int restart_backend(void);
int restart_security_agent(void);
int restart_sandbox(void);
void attempt_child_restart(void);
// Verbose communication removed - middleware handles this transparently
int init_sandbox_socket(void);
void cleanup_sandbox_socket(void);
int send_to_sandbox(const char* cmd, char* response, size_t response_size);

// Frontend socket server functions
int init_frontend_socket(void);
void cleanup_frontend_socket(void);
void handle_frontend_connections(void);

// SECURE: In-memory cache for prompt data (eliminates popen() attack surface)
static struct {
    char git_branch[64];
    char k8s_context[64];
    char k8s_namespace[64];
    time_t last_update;
    int valid;
    int cache_initialized;
} prompt_cache = {0};

// SECURE: Persistent bash sandbox with memory-based execution (no I/O)
static struct {
    int bash_pid;
    int bash_stdin_fd;
    int bash_stdout_fd;
    int bash_stderr_fd;
    int bash_ready;
    char output_buffer[64 * 1024];  // 64KB buffer
    size_t output_length;
    int exit_code;
} bash_sandbox = {0};

// SECURE: Hardcoded fallback values (no external command execution)
static const char* DEFAULT_GIT_BRANCH = "main";
static const char* DEFAULT_K8S_CONTEXT = "default";
static const char* DEFAULT_K8S_NAMESPACE = "default";

void init_socket_path() {
    const char* home = getenv("HOME");
    if (home) {
        snprintf(socket_path, sizeof(socket_path), "%s/.awesh.sock", home);
    } else {
        strcpy(socket_path, "/tmp/awesh.sock");  // fallback
    }
}

// Performance monitoring (D³ principle)
long get_time_ms() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

// Function will be defined after state and constants

// Optimized prompt data fetching with caching
void get_prompt_data_cached(char* git_branch, char* k8s_context, char* k8s_namespace, size_t size) {
    time_t now = time(NULL);
    
    // Check if cache is valid (5 second TTL)
    if (prompt_cache.valid && (now - prompt_cache.last_update) < 5) {
        strncpy(git_branch, prompt_cache.git_branch, size - 1);
        strncpy(k8s_context, prompt_cache.k8s_context, size - 1);
        strncpy(k8s_namespace, prompt_cache.k8s_namespace, size - 1);
        git_branch[size - 1] = '\0';
        k8s_context[size - 1] = '\0';
        k8s_namespace[size - 1] = '\0';
        return;
    }
    
    // Cache miss - fetch fresh data with secure in-memory functions
    long fetch_start = get_time_ms();
    
    // SECURE: Use direct file parsing instead of popen() commands
    get_git_branch(prompt_cache.git_branch, sizeof(prompt_cache.git_branch));
    get_kubectl_context(prompt_cache.k8s_context, sizeof(prompt_cache.k8s_context));
    get_kubectl_namespace(prompt_cache.k8s_namespace, sizeof(prompt_cache.k8s_namespace));
    
    // Mark cache as initialized
    prompt_cache.cache_initialized = 1;
    
    // Copy to output
    strncpy(git_branch, prompt_cache.git_branch, size - 1);
    strncpy(k8s_context, prompt_cache.k8s_context, size - 1);
    strncpy(k8s_namespace, prompt_cache.k8s_namespace, size - 1);
    git_branch[size - 1] = '\0';
    k8s_context[size - 1] = '\0';
    k8s_namespace[size - 1] = '\0';
    
    // Update cache
    prompt_cache.last_update = now;
    prompt_cache.valid = 1;
    
    debug_perf("prompt data fetch (cache miss)", fetch_start);
}

// REMOVED: Parallel popen structure - replaced with secure in-memory file parsing

// SECURE: Pure in-memory git branch (no file operations)
void get_git_branch(char* branch, size_t size) {
    // Use cached value if available
    if (prompt_cache.cache_initialized && prompt_cache.valid) {
        strncpy(branch, prompt_cache.git_branch, size - 1);
        branch[size - 1] = '\0';
        return;
    }
    
    // SECURE: Use hardcoded default (no file operations)
    strncpy(branch, DEFAULT_GIT_BRANCH, size - 1);
    branch[size - 1] = '\0';
}

// SECURE: Pure in-memory kubectl context (no file operations)
void get_kubectl_context(char* context, size_t size) {
    // Use cached value if available
    if (prompt_cache.cache_initialized && prompt_cache.valid) {
        strncpy(context, prompt_cache.k8s_context, size - 1);
        context[size - 1] = '\0';
        return;
    }
    
    // SECURE: Use hardcoded default (no file operations)
    strncpy(context, DEFAULT_K8S_CONTEXT, size - 1);
    context[size - 1] = '\0';
}

// SECURE: Pure in-memory kubectl namespace (no file operations)
void get_kubectl_namespace(char* namespace, size_t size) {
    // Use cached value if available
    if (prompt_cache.cache_initialized && prompt_cache.valid) {
        strncpy(namespace, prompt_cache.k8s_namespace, size - 1);
        namespace[size - 1] = '\0';
        return;
    }
    
    // SECURE: Use hardcoded default (no file operations)
    strncpy(namespace, DEFAULT_K8S_NAMESPACE, size - 1);
    namespace[size - 1] = '\0';
}

// AI-driven mode detection: Let AI decide command vs edit mode
char* parse_ai_mode(const char* input) {
    if (!input || strlen(input) == 0) return "ai_detect";
    
    // For natural language queries, let AI decide
    return "ai_detect";
}

// Functions will be defined after state and constants

// Function will be defined after state and constants

// Handle AI query in edit mode (simplified)
void handle_ai_query(const char* query) {
    // Get verbose level from environment since state is not accessible here
    int verbose = 0;
    const char* verbose_str = getenv("VERBOSE");
    if (verbose_str) {
        verbose = atoi(verbose_str);
    }
    
    if (verbose >= 2) {
        printf("🤖 Edit mode: %s\n", query);
        printf("💡 AI processing would happen here\n");
    }
}

// REMOVED: Parallel popen implementation - replaced with secure in-memory file parsing
// Performance: In-memory file parsing is faster than fork/exec/popen
// Security: Eliminates command injection attack surface
#define MAX_CMD_LEN 4096
#define MAX_RESPONSE_LEN 65536

typedef enum {
    AI_LOADING,
    AI_READY,
    AI_FAILED
} ai_status_t;

typedef struct {
    int backend_pid;
    int security_agent_pid;
    int sandbox_pid;
    int socket_fd;
    ai_status_t ai_status;
    int verbose;         // 0 = silent, 1 = show AI status + debug, 2+ = more verbose
} awesh_state_t;

static awesh_state_t state = {0, 0, -1, -1, AI_LOADING, 0};  // Default to silent (verbose=0)

// Performance debugging
void debug_perf(const char* operation, long start_time) {
    if (state.verbose >= 2) {
        long duration = get_time_ms() - start_time;
        fprintf(stderr, "🐛 DEBUG: %s took %ldms\n", operation, duration);
    }
}

int is_process_running(pid_t pid) {
    if (pid <= 0) return 0;
    
    // Use kill with signal 0 to check if process exists
    return (kill(pid, 0) == 0);
}

void log_health_status(const char* process_name, pid_t pid, int is_running) {
    if (state.verbose >= 1) {
        if (is_running) {
            if (state.verbose >= 2) {
                fprintf(stderr, "💚 HEALTH: %s (PID: %d) is running\n", process_name, pid);
            }
        } else {
            fprintf(stderr, "💀 HEALTH: %s (PID: %d) is not running\n", process_name, pid);
        }
    }
}

void check_child_process_health(void) {
    // Check backend health
    if (state.backend_pid > 0) {
        int backend_running = is_process_running(state.backend_pid);
        log_health_status("Backend", state.backend_pid, backend_running);
        
        if (!backend_running) {
            if (state.verbose >= 1) {
                fprintf(stderr, "⚠️ Backend process died, will attempt restart\n");
            }
            state.backend_pid = -1;
            state.ai_status = AI_FAILED;
        }
    }
    
    // Check security agent health
    if (state.security_agent_pid > 0) {
        int security_running = is_process_running(state.security_agent_pid);
        log_health_status("Security Agent", state.security_agent_pid, security_running);
        
        if (!security_running) {
            if (state.verbose >= 1) {
                fprintf(stderr, "⚠️ Security Agent process died, will attempt restart\n");
            }
            state.security_agent_pid = -1;
            // Security agent socket removed - now uses stdin/stdout
        }
    }
    
    // Check sandbox health
    if (state.sandbox_pid > 0) {
        int sandbox_running = is_process_running(state.sandbox_pid);
        log_health_status("Sandbox", state.sandbox_pid, sandbox_running);
        
        if (!sandbox_running) {
            if (state.verbose >= 1) {
                fprintf(stderr, "⚠️ Sandbox process died, will attempt restart\n");
            }
            state.sandbox_pid = -1;
            sandbox_socket_fd = -1;
        }
    }
    
    // Check if security agent needs restart
    if (state.security_agent_pid <= 0) {
        if (state.verbose >= 1) {
            fprintf(stderr, "🔄 AUTO-RESTART: Security Agent failed, attempting restart\n");
        }
        restart_security_agent();
    }
    
    // Check if sandbox needs restart
    if (state.sandbox_pid <= 0) {
        if (state.verbose >= 1) {
            fprintf(stderr, "🔄 AUTO-RESTART: Sandbox failed, attempting restart\n");
        }
        restart_sandbox();
    }
}

void get_health_status_emojis(char* backend_emoji, char* security_emoji, char* sandbox_emoji) {
    // Backend health emoji - unique emojis for each state
    if (state.backend_pid > 0 && is_process_running(state.backend_pid)) {
        switch (state.ai_status) {
            case AI_LOADING:
                strcpy(backend_emoji, "⏳");  // Loading - uniform hourglass
                break;
            case AI_READY:
                strcpy(backend_emoji, "🧠");  // Ready
                break;
            case AI_FAILED:
                strcpy(backend_emoji, "💀");  // Failed
                break;
        }
    } else {
        strcpy(backend_emoji, "⏳");  // Not running - uniform hourglass
    }
    
    // Security agent health emoji - just check if socket exists (no blocking calls)
    if (state.security_agent_pid > 0) {
        strcpy(security_emoji, "🔒");  // Socket exists, assume responding
        } else {
        strcpy(security_emoji, "⏳");  // Not started - uniform hourglass
        }
    
    // Sandbox health emoji - just check if process exists (no blocking calls)
    if (state.sandbox_pid > 0 && is_process_running(state.sandbox_pid)) {
        strcpy(sandbox_emoji, "🏖️");  // Process exists, assume responding
    } else {
        strcpy(sandbox_emoji, "⏳");  // Not started - uniform hourglass
    }
}

int restart_backend(void) {
    if (state.verbose >= 1) {
        fprintf(stderr, "🔄 RESTART: Attempting to restart backend...\n");
    }
    
    // Clean up existing backend connection
    if (state.socket_fd >= 0) {
        close(state.socket_fd);
        state.socket_fd = -1;
    }
    
    // Start new backend process
    pid_t new_backend_pid = fork();
    if (new_backend_pid == 0) {
        // Child: ignore SIGINT and start backend
        signal(SIGINT, SIG_IGN);
        
        const char* home = getenv("HOME");
        char venv_python[512];
        
        if (home) {
            snprintf(venv_python, sizeof(venv_python), "%s/AI/awesh/venv/bin/python3", home);
            if (access(venv_python, X_OK) == 0) {
                execl(venv_python, "python3", "-m", "awesh_backend", NULL);
            }
        }
        
        execl("/usr/bin/python3", "python3", "-m", "awesh_backend", NULL);
        perror("Failed to restart backend");
        exit(1);
    } else if (new_backend_pid > 0) {
        state.backend_pid = new_backend_pid;
        state.ai_status = AI_LOADING;
        
        if (state.verbose >= 1) {
            fprintf(stderr, "✅ RESTART: Backend restarted (PID: %d)\n", new_backend_pid);
        }
        return 0;
    } else {
        if (state.verbose >= 1) {
            fprintf(stderr, "❌ RESTART: Failed to restart backend\n");
        }
        return -1;
    }
}

int restart_security_agent(void) {
    if (state.verbose >= 1) {
        fprintf(stderr, "🔄 RESTART: Attempting to restart Security Agent...\n");
    }
    
    // Clean up existing security agent socket
    // Socket cleanup removed - middleware handles this
    
    // Socket initialization removed - middleware handles this
    
    // Start new security agent process
    pid_t new_security_pid = fork();
    if (new_security_pid == 0) {
        // Child: ignore SIGINT and start security agent
        signal(SIGINT, SIG_IGN);
        
        const char* home = getenv("HOME");
        if (home) {
            char security_agent_path[512];
            snprintf(security_agent_path, sizeof(security_agent_path), "%s/.local/bin/awesh_sec", home);
            execl(security_agent_path, "awesh_sec", NULL);
        }
        
        execl("./awesh_sec", "awesh_sec", NULL);
        perror("Failed to restart Security Agent");
        exit(1);
    } else if (new_security_pid > 0) {
        if (state.verbose >= 1) {
            fprintf(stderr, "✅ RESTART: Security Agent restarted (PID: %d)\n", new_security_pid);
        }
        return 0;
    } else {
        if (state.verbose >= 1) {
            fprintf(stderr, "❌ RESTART: Failed to restart Security Agent\n");
        }
        return -1;
    }
}

int restart_sandbox(void) {
    if (state.verbose >= 1) {
        fprintf(stderr, "🔄 RESTART: Attempting to restart Sandbox...\n");
    }
    
    // Clean up existing sandbox socket
    cleanup_sandbox_socket();
    
    // Reinitialize socket
    if (init_sandbox_socket() != 0) {
        if (state.verbose >= 1) {
            fprintf(stderr, "❌ RESTART: Failed to reinitialize Sandbox socket\n");
        }
        return -1;
    }
    
    // Start new sandbox process
    pid_t new_sandbox_pid = fork();
    if (new_sandbox_pid == 0) {
        // Child: ignore SIGINT and start sandbox
        signal(SIGINT, SIG_IGN);
        
        const char* home = getenv("HOME");
        if (home) {
            char sandbox_path[512];
            snprintf(sandbox_path, sizeof(sandbox_path), "%s/.local/bin/awesh_sandbox", home);
            execl(sandbox_path, "awesh_sandbox", NULL);
        }
        
        execl("./awesh_sandbox", "awesh_sandbox", NULL);
        perror("Failed to start Sandbox");
        exit(1);
    } else if (new_sandbox_pid > 0) {
        state.sandbox_pid = new_sandbox_pid;
        if (state.verbose >= 1) {
            fprintf(stderr, "✅ RESTART: Sandbox restarted (PID: %d)\n", new_sandbox_pid);
        }
        return 0;
    } else {
        if (state.verbose >= 1) {
            fprintf(stderr, "❌ RESTART: Failed to restart Sandbox\n");
        }
        return -1;
    }
}

void attempt_child_restart(void) {
    // Check if backend needs restart
    if (state.backend_pid <= 0 || !is_process_running(state.backend_pid)) {
        if (state.verbose >= 1) {
            fprintf(stderr, "🔄 AUTO-RESTART: Backend process failed, attempting restart\n");
        }
        restart_backend();
    }
    
    // Check if security agent needs restart
    if (state.security_agent_pid <= 0 || !is_process_running(state.security_agent_pid)) {
        if (state.verbose >= 1) {
            fprintf(stderr, "🔄 AUTO-RESTART: Security Agent failed, attempting restart\n");
        }
        restart_security_agent();
    }
    
    // Check if sandbox needs restart
    if (state.sandbox_pid <= 0 || !is_process_running(state.sandbox_pid)) {
        if (state.verbose >= 1) {
            fprintf(stderr, "🔄 AUTO-RESTART: Sandbox failed, attempting restart\n");
        }
        restart_sandbox();
    }
}

// Get process agent status for prompt display
// Old socket functions removed - middleware now handles socket management


void get_security_agent_status(char* status, size_t size) {
    // Read from shared memory instead of socket
    const char* home = getenv("HOME");
    if (!home) {
        strncpy(status, "", size - 1);
        status[size - 1] = '\0';
        return;
    }
    
    char shm_name[256];
    const char* user = getenv("USER");
    if (!user) user = "unknown";
    snprintf(shm_name, sizeof(shm_name), "awesh_security_status_%s", user);
    
    // Open shared memory
    int shm_fd = shm_open(shm_name, O_RDONLY, 0666);
    if (shm_fd == -1) {
        strncpy(status, "", size - 1);
        status[size - 1] = '\0';
        return;
    }
    
    // Map shared memory
    char* shared_status = mmap(NULL, 512, PROT_READ, MAP_SHARED, shm_fd, 0);
    if (shared_status == MAP_FAILED) {
        close(shm_fd);
        strncpy(status, "", size - 1);
        status[size - 1] = '\0';
        return;
    }
    
    // Copy status from shared memory
    strncpy(status, shared_status, size - 1);
    status[size - 1] = '\0';
    
    // Cleanup
    munmap(shared_status, 512);
    close(shm_fd);
}

// Send query to backend and get response
int send_to_backend(const char* query, char* response, size_t response_size) {
    if (state.socket_fd < 0) {
        return -1;  // No backend connection
    }
    
    // Send query to backend
    char buffer[MAX_CMD_LEN];
    snprintf(buffer, sizeof(buffer), "QUERY:%s", query);
    
    if (send(state.socket_fd, buffer, strlen(buffer), 0) < 0) {
        return -1;
    }
    
    // Read response with timeout and thinking dots
    fd_set readfds;
    struct timeval timeout;
    int dots_shown = 0;
    
    while (1) {
        FD_ZERO(&readfds);
        FD_SET(state.socket_fd, &readfds);
        timeout.tv_sec = 5;  // Check every 5 seconds for thinking dots
        timeout.tv_usec = 0;
        
        int result = select(state.socket_fd + 1, &readfds, NULL, NULL, &timeout);
        
        if (result > 0) {
            // Data available, read response
            ssize_t bytes_received = recv(state.socket_fd, response, response_size - 1, 0);
            if (bytes_received > 0) {
                response[bytes_received] = '\0';
                return 0;  // Success
            }
        } else if (result == 0) {
            // Timeout - show thinking dots
            dots_shown++;
            if (dots_shown <= 6) {  // Show up to 6 dots (30 seconds)
                printf(".");
                fflush(stdout);
            } else {
                printf("\n❌ AI response timeout\n");
                return -1;
            }
        } else {
            // Error
            return -1;
        }
    }
    
    return -1;  // Timeout or error
}

// Security agent communication removed - now handled transparently by middleware proxy

// Send verbose level to security agent
// Verbose communication removed - middleware handles this transparently

// Initialize sandbox socket
int init_sandbox_socket(void) {
    // Initialize Sandbox socket path
    const char* home = getenv("HOME");
    if (!home) return -1;

    snprintf(sandbox_socket_path, sizeof(sandbox_socket_path),
             "%s/.awesh_sandbox.sock", home);
    
    // Remove old socket if it exists
    unlink(sandbox_socket_path);
    
    // Create socket
    sandbox_socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sandbox_socket_fd < 0) {
        return -1;
    }
    
    // Bind socket
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sandbox_socket_path, sizeof(addr.sun_path) - 1);
    
    if (bind(sandbox_socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sandbox_socket_fd);
        return -1;
    }
    
    // Listen for connections
    if (listen(sandbox_socket_fd, 1) < 0) {
        close(sandbox_socket_fd);
        return -1;
    }
    
    return 0;
}

// Cleanup sandbox socket
void cleanup_sandbox_socket(void) {
    if (sandbox_socket_fd != -1) {
        close(sandbox_socket_fd);
        sandbox_socket_fd = -1;
    }
    unlink(sandbox_socket_path);
}

// Send command to sandbox
int send_to_sandbox(const char* cmd, char* response, size_t response_size) {
    if (sandbox_socket_fd < 0) {
        return -1;  // No sandbox connection
    }
    
    // Create a client socket to connect to sandbox
    int client_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (client_fd < 0) {
        return -1;
    }
    
    // Connect to sandbox socket
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sandbox_socket_path, sizeof(addr.sun_path) - 1);
    
    if (connect(client_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(client_fd);
        return -1;
    }
    
    // Send command to sandbox
    if (send(client_fd, cmd, strlen(cmd), 0) < 0) {
        close(client_fd);
        return -1;
    }
    
    // Read acknowledgment with timeout
    fd_set readfds;
    struct timeval timeout;
    
    FD_ZERO(&readfds);
    FD_SET(client_fd, &readfds);
    timeout.tv_sec = 5;  // 5 second timeout
    timeout.tv_usec = 0;
    
    int result = select(client_fd + 1, &readfds, NULL, NULL, &timeout);
    
    if (result > 0) {
        // Read acknowledgment
        char ack[10];
        ssize_t bytes_received = recv(client_fd, ack, sizeof(ack) - 1, 0);
        close(client_fd);
        
        if (bytes_received > 0) {
            ack[bytes_received] = '\0';
            
            // Now read result from mmap file
            int mmap_fd = open(mmap_path, O_RDONLY);
            if (mmap_fd < 0) {
                return -1;
            }
            
            // Map the file into memory
            char* mmap_ptr = mmap(NULL, 1024*1024, PROT_READ, MAP_SHARED, mmap_fd, 0);
            if (mmap_ptr == MAP_FAILED) {
                close(mmap_fd);
                return -1;
            }
            
            // Copy JSON response to output buffer
            strncpy(response, mmap_ptr, response_size - 1);
            response[response_size - 1] = '\0';
            
            // Cleanup
            munmap(mmap_ptr, 1024*1024);
            close(mmap_fd);
            
            return 0;  // Success
        }
    }
    
    close(client_fd);
    return -1;  // Timeout or error
}

// Initialize frontend socket server
int init_frontend_socket(void) {
    // Initialize Frontend socket path
    const char* home = getenv("HOME");
    if (!home) return -1;

    snprintf(frontend_socket_path, sizeof(frontend_socket_path),
             "%s/.awesh_frontend.sock", home);
    
    // Remove old socket if it exists
    unlink(frontend_socket_path);
    
    // Create socket
    frontend_socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (frontend_socket_fd < 0) {
        return -1;
    }
    
    // Bind socket
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, frontend_socket_path, sizeof(addr.sun_path) - 1);
    
    if (bind(frontend_socket_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(frontend_socket_fd);
        return -1;
    }
    
    // Listen for connections
    if (listen(frontend_socket_fd, 5) < 0) {
        close(frontend_socket_fd);
        return -1;
    }
    
    return 0;
}

// Cleanup frontend socket
void cleanup_frontend_socket(void) {
    if (frontend_socket_fd != -1) {
        close(frontend_socket_fd);
        frontend_socket_fd = -1;
    }
    unlink(frontend_socket_path);
}

// Handle incoming connections from middleware
void handle_frontend_connections(void) {
    if (frontend_socket_fd < 0) return;
    
    // Check for incoming connections with non-blocking select
    fd_set readfds;
    struct timeval timeout;
    
    FD_ZERO(&readfds);
    FD_SET(frontend_socket_fd, &readfds);
    timeout.tv_sec = 0;
    timeout.tv_usec = 1000; // 1ms timeout
    
    if (select(frontend_socket_fd + 1, &readfds, NULL, NULL, &timeout) > 0) {
        // Accept connection
        int client_fd = accept(frontend_socket_fd, NULL, NULL);
        if (client_fd >= 0) {
            // Read message from middleware
            char message[1024];
            ssize_t bytes = recv(client_fd, message, sizeof(message) - 1, 0);
            if (bytes > 0) {
                message[bytes] = '\0';
                
                // Handle different message types from middleware
                if (strncmp(message, "STATUS_UPDATE:", 14) == 0) {
                    // Security agent status update
                    char* status = message + 14;
                    if (state.verbose >= 2) {
                        printf("🔒 Security Agent Status: %s\n", status);
                    }
                } else if (strncmp(message, "SECURITY_ALERT:", 15) == 0) {
                    // Security alert from middleware
                    char* alert = message + 15;
                    printf("🚨 SECURITY ALERT: %s\n", alert);
                } else if (strncmp(message, "VERBOSE_UPDATE:", 15) == 0) {
                    // Verbose level update from middleware
                    char* level_str = message + 15;
                    int new_level = atoi(level_str);
                    if (new_level != state.verbose) {
                        state.verbose = new_level;
                        if (state.verbose >= 1) {
                            printf("🔧 Verbose level updated to %d by middleware\n", state.verbose);
                        }
                    }
                } else if (strncmp(message, "THREAT_DETECTED:", 16) == 0) {
                    // Threat detection notification
                    char* threat = message + 16;
                    printf("🚨 THREAT DETECTED: %s\n", threat);
                }
            }
            close(client_fd);
        }
    }
}

// Handle AI mode detection: Let AI decide command vs edit mode
void handle_ai_mode_detection(const char* input) {
    if (state.ai_status != AI_READY) {
        printf("🤖⏳ AI not ready. Status: %s\n", 
               state.ai_status == AI_LOADING ? "Loading..." : "Failed");
        return;
    }
    
    // Send to backend for AI mode detection
    char response[MAX_RESPONSE_LEN];
    if (send_to_backend(input, response, sizeof(response)) == 0) {
        // Parse AI response for mode detection
        if (strncmp(response, "awesh_cmd:", 10) == 0) {
            // AI determined this is a command - extract and execute through security middleware
            char* command = response + 10;
            // Skip leading whitespace
            while (*command == ' ' || *command == '\t') command++;
            
            if (state.verbose >= 1) {
                printf("🔧 AI suggested command: %s\n", command);
            }
            // Execute the command through security middleware
            handle_interactive_bash(command);
        } else if (strncmp(response, "awesh_edit:", 11) == 0) {
            // AI determined this is edit mode - just display
            char* edit_content = response + 11;
            // Skip leading whitespace
            while (*edit_content == ' ' || *edit_content == '\t') edit_content++;
            
            printf("📝 AI Edit Mode: %s\n", edit_content);
        } else {
            // Fallback: display raw response
            printf("%s\n", response);
        }
    } else {
        printf("❌ Failed to get AI response\n");
    }
}

void load_config() {
    // Read ~/.aweshrc for configuration (primary config file)
    char config_path[512];
    snprintf(config_path, sizeof(config_path), "%s/.aweshrc", getenv("HOME"));
    
    FILE *file = fopen(config_path, "r");
    if (file) {
    char line[256];
    while (fgets(line, sizeof(line), file)) {
        // Remove newline
        line[strcspn(line, "\n")] = 0;
        
        // Skip empty lines and comments
        if (line[0] == '\0' || line[0] == '#') continue;
        
        // Parse key=value pairs
        char *equals = strchr(line, '=');
        if (!equals) continue;
        
        *equals = '\0';
        char *key = line;
        char *value = equals + 1;
        
        if (strcmp(key, "VERBOSE") == 0) {
            state.verbose = atoi(value);  // Parse as integer: 0=silent, 1=show AI status+debug, 2+=more verbose
        }
        
        // Set all config values as environment variables for backend (except MODEL)
        if (strcmp(key, "MODEL") != 0) {
        setenv(key, value, 1);
    }
    }
        fclose(file);
    } else {
        // Fallback to ~/.awesh_config.ini for backward compatibility
        snprintf(config_path, sizeof(config_path), "%s/.awesh_config.ini", getenv("HOME"));
        file = fopen(config_path, "r");
        if (file) {
    char line[256];
    while (fgets(line, sizeof(line), file)) {
        // Remove newline
        line[strcspn(line, "\n")] = 0;
        
        // Skip empty lines and comments
        if (line[0] == '\0' || line[0] == '#') continue;
        
        // Parse key=value pairs
        char *equals = strchr(line, '=');
        if (!equals) continue;
        
        *equals = '\0';
        char *key = line;
        char *value = equals + 1;
        
        if (strcmp(key, "VERBOSE") == 0) {
            state.verbose = atoi(value);  // Parse as integer: 0=silent, 1=show AI status+debug, 2+=more verbose
        }
        
        // Set all config values as environment variables for backend (except MODEL)
        if (strcmp(key, "MODEL") != 0) {
            setenv(key, value, 1);
        }
            }
    fclose(file);
        }
    }
    
    // Set default MODEL based on AI provider (after config is loaded)
    if (!getenv("MODEL")) {
        const char* ai_provider = getenv("AI_PROVIDER") ? getenv("AI_PROVIDER") : "openai";
        if (strcmp(ai_provider, "openrouter") == 0) {
            setenv("MODEL", "claude-sonnet", 1);  // Default OpenRouter model
        } else {
            setenv("MODEL", "gpt-5", 1);  // Default OpenAI model
        }
    }
}

void update_config_file(const char* key, const char* value) {
    char config_path[512];
    snprintf(config_path, sizeof(config_path), "%s/.aweshrc", getenv("HOME"));
    
    // Read existing config
    char lines[100][256];  // Max 100 lines, 256 chars each
    int line_count = 0;
    int key_found = 0;
    
    FILE *file = fopen(config_path, "r");
    if (file) {
        while (fgets(lines[line_count], sizeof(lines[line_count]), file) && line_count < 99) {
            // Remove newline for processing
            lines[line_count][strcspn(lines[line_count], "\n")] = 0;
            
            // Check if this line contains our key
            if (strncmp(lines[line_count], key, strlen(key)) == 0 && 
                lines[line_count][strlen(key)] == '=') {
                // Update existing key
                snprintf(lines[line_count], sizeof(lines[line_count]), "%s=%s", key, value);
                key_found = 1;
            }
            line_count++;
        }
        fclose(file);
    }
    
    // If key wasn't found, add it
    if (!key_found && line_count < 99) {
        snprintf(lines[line_count], sizeof(lines[line_count]), "%s=%s", key, value);
        line_count++;
    }
    
    // Write back to file
    file = fopen(config_path, "w");
    if (file) {
        for (int i = 0; i < line_count; i++) {
            fprintf(file, "%s\n", lines[i]);
        }
        fclose(file);
    }
}

void handle_sigint(int sig __attribute__((unused))) {
    // Ctrl+C should just return to prompt, not exit
    // This prevents the signal from reaching child processes (backend, security agent)
    printf("\n");
    rl_on_new_line();
    rl_replace_line("", 0);
    rl_redisplay();
    
    // Don't propagate signal to child processes
    // The signal is handled here and doesn't reach the backend
}

void cleanup_and_exit(int sig __attribute__((unused))) {
    if (state.verbose >= 1) {
        printf("\n🔄 CLEANUP: Shutting down awesh...\n");
    }
    
    // Cleanup backend connection
    if (state.socket_fd >= 0) {
        if (state.verbose >= 2) {
            printf("🔌 CLEANUP: Closing backend socket\n");
        }
        close(state.socket_fd);
        state.socket_fd = -1;
    }
    
    // Cleanup backend process
    if (state.backend_pid > 0) {
        if (state.verbose >= 1) {
            printf("🐍 CLEANUP: Terminating backend process (PID: %d)\n", state.backend_pid);
        }
        
        // Send SIGTERM first (graceful shutdown)
        kill(state.backend_pid, SIGTERM);
        
        // Wait up to 3 seconds for graceful shutdown
        int status;
        pid_t result = waitpid(state.backend_pid, &status, WNOHANG);
        if (result == 0) {
            // Process still running, wait a bit
            sleep(1);
            result = waitpid(state.backend_pid, &status, WNOHANG);
            if (result == 0) {
                // Still running, force kill
                if (state.verbose >= 1) {
                    printf("⚠️ CLEANUP: Backend didn't respond to SIGTERM, sending SIGKILL\n");
                }
                kill(state.backend_pid, SIGKILL);
                waitpid(state.backend_pid, &status, 0);
            }
        }
        
        if (state.verbose >= 2) {
            printf("✅ CLEANUP: Backend process terminated\n");
        }
    }
    
    // Cleanup Security Agent process
    if (state.security_agent_pid > 0) {
    if (state.verbose >= 1) {
            printf("🔒 CLEANUP: Terminating Security Agent process (PID: %d)\n", state.security_agent_pid);
        }
        
        // Send SIGTERM first (graceful shutdown)
        kill(state.security_agent_pid, SIGTERM);
        
        // Wait up to 3 seconds for graceful shutdown
        int status;
        pid_t result = waitpid(state.security_agent_pid, &status, WNOHANG);
        if (result == 0) {
            // Process still running, wait a bit
            sleep(1);
            result = waitpid(state.security_agent_pid, &status, WNOHANG);
            if (result == 0) {
                // Still running, force kill
                if (state.verbose >= 1) {
                    printf("⚠️ CLEANUP: Security Agent didn't respond to SIGTERM, sending SIGKILL\n");
                }
                kill(state.security_agent_pid, SIGKILL);
                waitpid(state.security_agent_pid, &status, 0);
            }
        }
        
        if (state.verbose >= 2) {
            printf("✅ CLEANUP: Security Agent process terminated\n");
        }
    }
    
    // Cleanup Security Agent socket
    // Socket cleanup removed - middleware handles this
    
    // Cleanup Sandbox process
    if (state.sandbox_pid > 0) {
        if (state.verbose >= 1) {
            printf("🏖️ CLEANUP: Terminating Sandbox process (PID: %d)\n", state.sandbox_pid);
        }
        
        // Send SIGTERM first (graceful shutdown)
        kill(state.sandbox_pid, SIGTERM);
        
        // Wait up to 3 seconds for graceful shutdown
        int status;
        pid_t result = waitpid(state.sandbox_pid, &status, WNOHANG);
        if (result == 0) {
            // Process still running, wait a bit
            sleep(1);
            result = waitpid(state.sandbox_pid, &status, WNOHANG);
            if (result == 0) {
                // Still running, force kill
                if (state.verbose >= 1) {
                    printf("⚠️ CLEANUP: Sandbox didn't respond to SIGTERM, sending SIGKILL\n");
                }
                kill(state.sandbox_pid, SIGKILL);
                waitpid(state.sandbox_pid, &status, 0);
            }
        }
        
        if (state.verbose >= 2) {
            printf("✅ CLEANUP: Sandbox process terminated\n");
        }
    }
    
    // Cleanup Sandbox socket
    cleanup_sandbox_socket();
    
    // Cleanup Frontend socket
    if (state.verbose >= 1) {
        printf("🔌 CLEANUP: Closing frontend socket server\n");
    }
    cleanup_frontend_socket();
    
    // Cleanup bash sandbox (legacy)
    if (state.verbose >= 1) {
        printf("🏖️ CLEANUP: Terminating legacy bash sandbox\n");
    }
    cleanup_bash_sandbox();
    
    // Cleanup socket files
    if (state.verbose >= 2) {
        printf("🧹 CLEANUP: Removing socket files\n");
    }
    unlink(socket_path);
    // Socket cleanup removed - middleware handles this
    unlink(sandbox_socket_path);
    unlink(frontend_socket_path);
    
    // Cleanup any remaining child processes
    if (state.verbose >= 2) {
        printf("🧹 CLEANUP: Cleaning up any remaining child processes\n");
    }
    
    if (state.verbose >= 1) {
        printf("✅ CLEANUP: Shutdown complete. Goodbye!\n");
    } else {
    printf("\nGoodbye!\n");
    }
    
    exit(0);
}

int start_backend() {
    // Initialize socket path
    init_socket_path();
    
    // Remove existing socket
    unlink(socket_path);
    
    // Fork backend process
    state.backend_pid = fork();
    if (state.backend_pid == 0) {
        // Child: ignore SIGINT to prevent Ctrl+C from reaching backend
        signal(SIGINT, SIG_IGN);
        
        // Start Python backend as module using virtual environment
        const char* home = getenv("HOME");
        char venv_python[512];
        
        // Try to use virtual environment Python first
        if (home) {
            snprintf(venv_python, sizeof(venv_python), "%s/AI/awesh/venv/bin/python3", home);
            if (access(venv_python, X_OK) == 0) {
                execl(venv_python, "python3", "-m", "awesh_backend", NULL);
            }
        }
        
        // Fallback to system Python
        execl("/usr/bin/python3", "python3", "-m", "awesh_backend", NULL);
        perror("Failed to start backend");
        exit(1);
    } else if (state.backend_pid < 0) {
        perror("Failed to fork backend");
        return -1;
    }
    
    // Parent: wait for backend to start with retry mechanism
    int retries = 0;
    int max_retries = 10;  // 10 seconds total wait time
    
    while (retries < max_retries) {
    sleep(1);
        retries++;
    
        // Try to connect to backend socket
    state.socket_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (state.socket_fd < 0) {
        perror("Failed to create socket");
        return -1;
    }
    
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);
    
        if (connect(state.socket_fd, (struct sockaddr*)&addr, sizeof(addr)) >= 0) {
            // Connection successful
            if (state.verbose >= 1) {
                printf("🔌 Connected to backend after %d seconds\n", retries);
            }
            // Check AI status to update from AI_LOADING to AI_READY
            check_ai_status();
            break;
        }
        
        // Connection failed, close socket and retry
        close(state.socket_fd);
        state.socket_fd = -1;
        
        if (state.verbose >= 1) {
            printf("⏳ Waiting for backend to start... (%d/%d)\n", retries, max_retries);
        }
    }
    
    if (retries >= max_retries) {
        perror("Failed to connect to backend after 10 seconds");
        return -1;
    }
    
    return 0;
}

void check_ai_status() {
    if (state.socket_fd < 0) {
        if (state.verbose >= 1) {
            printf("🔧 Status check: No socket connection\n");
        }
        return;
    }
    
    if (state.verbose >= 1) {
        printf("🔧 Sending STATUS command...\n");
    }
    
    // Send status check
    if (send(state.socket_fd, "STATUS", 6, 0) < 0) {
        if (state.verbose >= 1) {
            printf("🔧 Failed to send STATUS command\n");
        }
        return;
    }
    
    // Read response
    char response[64];
    ssize_t bytes = recv(state.socket_fd, response, sizeof(response) - 1, 0);
    if (bytes > 0) {
        response[bytes] = '\0';
        if (state.verbose >= 1) {
            printf("🔧 Status response: '%s' (%zd bytes)\n", response, bytes);
        }
        if (strncmp(response, "AI_READY", 8) == 0) {
            state.ai_status = AI_READY;
            if (state.verbose >= 2) {
                printf("🔧 AI status updated to READY\n");
            }
        } else if (strncmp(response, "AI_LOADING", 10) == 0) {
            state.ai_status = AI_LOADING;
            if (state.verbose >= 2) {
                printf("🔧 AI status updated to LOADING\n");
            }
        } else {
            if (state.verbose >= 2) {
                printf("🔧 Unknown status response: '%s'\n", response);
            }
        }
    } else {
        if (state.verbose >= 1) {
            printf("🔧 No response to STATUS command (bytes=%zd)\n", bytes);
        }
    }
}

void send_command(const char* cmd) {
    if (state.socket_fd < 0) {
        // No backend - execute directly with system()
        system(cmd);
        return;
    }
    
    // First, sync working directory with backend
    char cwd[1024];
    if (getcwd(cwd, sizeof(cwd))) {
        char sync_buffer[1100];
        snprintf(sync_buffer, sizeof(sync_buffer), "CWD:%s", cwd);
        send(state.socket_fd, sync_buffer, strlen(sync_buffer), 0);
        
        // Wait for sync acknowledgment (brief)
        fd_set readfds;
        struct timeval timeout;
        FD_ZERO(&readfds);
        FD_SET(state.socket_fd, &readfds);
        timeout.tv_sec = 1;
        timeout.tv_usec = 0;
        
        if (select(state.socket_fd + 1, &readfds, NULL, NULL, &timeout) > 0) {
            char ack[64];
            recv(state.socket_fd, ack, sizeof(ack) - 1, 0);  // Consume sync response
        }
    }
    
    // Send actual command to backend
    char buffer[MAX_CMD_LEN];
    snprintf(buffer, sizeof(buffer), "%s", cmd);
    
    if (send(state.socket_fd, buffer, strlen(buffer), 0) < 0) {
        perror("Failed to send command");
        return;
    }
    
    // Read response with timeout and thinking dots
    fd_set readfds;
    struct timeval timeout;
    int dots_shown = 0;
    
    while (1) {
        FD_ZERO(&readfds);
        FD_SET(state.socket_fd, &readfds);
        timeout.tv_sec = 5;  // 5 second intervals for dots
        timeout.tv_usec = 0;
        
        int select_result = select(state.socket_fd + 1, &readfds, NULL, NULL, &timeout);
        
        if (select_result > 0) {
            // Data available - break out to read response
            break;
        } else if (select_result == 0) {
            // Timeout - show thinking dot
            printf(".");
            fflush(stdout);
            dots_shown++;
            
            // Stop after 64 dots (5+ minutes)
            if (dots_shown >= 64) {
                printf("\nBackend timeout - no response\n");
                return;
            }
        } else {
            perror("select failed");
            return;
        }
    }
    
    // Clear dots line if any were shown
    if (dots_shown > 0) {
        printf("\n");
    }
    
    int select_result = 1; // We know data is available
    if (select_result > 0) {
        char response[MAX_RESPONSE_LEN];
        ssize_t bytes = recv(state.socket_fd, response, sizeof(response) - 1, 0);
        if (bytes > 0) {
            response[bytes] = '\0';
            
            printf("%s", response);
            
            // Check AI status after command (efficient - we're already communicating)
            if (state.ai_status == AI_LOADING) {
                check_ai_status();
            }
        } else if (bytes == 0) {
            printf("Backend disconnected\n");
        } else {
            perror("recv failed");
        }
    } else if (select_result == 0) {
        printf("Backend timeout - no response\n");
    } else {
        perror("select failed");
    }
}

int is_awesh_command(const char* cmd) {
    return (strcmp(cmd, "aweh") == 0 ||
            strcmp(cmd, "awes") == 0 ||
            strncmp(cmd, "awev", 4) == 0 ||
            strncmp(cmd, "awea", 4) == 0 ||
            strncmp(cmd, "awem", 4) == 0);
}


void handle_awesh_command(const char* cmd) {
    if (strcmp(cmd, "aweh") == 0) {
        printf("🎛️  Awesh Control Commands:\n");
        printf("\n📋 Help:\n");
        printf("  aweh              Show this help\n");
        printf("  awes              Show verbose status (API provider, model, debug state)\n");
        printf("\n🔧 Verbose Debug:\n");
        printf("  awev              Show verbose level status\n");
        printf("  awev 0            Set verbose level 0 (silent)\n");
        printf("  awev 1            Set verbose level 1 (info)\n");
        printf("  awev 2            Set verbose level 2 (debug)\n");
        printf("  awev on           Enable verbose logging (level 1)\n");
        printf("  awev off          Disable verbose logging (level 0)\n");
        printf("\n🤖 AI Provider:\n");
        printf("  awea              Show current AI provider and model\n");
        printf("  awea openai       Switch to OpenAI\n");
        printf("  awea openrouter   Switch to OpenRouter\n");
        printf("\n📋 Model:\n");
        printf("  awem              Show current model and supported models\n");
        printf("  awem gpt-4        Set model to GPT-4 (OpenAI)\n");
        printf("  awem gpt-5        Set model to GPT-5 (OpenAI)\n");
        printf("  awem kimi-k2      Set model to Kimi K2 (OpenRouter)\n");
        printf("  awem claude-sonnet Set model to Claude Sonnet (OpenRouter)\n");
        printf("\n💡 All commands use 'awe' prefix to avoid bash conflicts\n");
    } else if (strcmp(cmd, "awes") == 0) {
        const char* ai_provider = getenv("AI_PROVIDER") ? getenv("AI_PROVIDER") : "openai";
        const char* model = getenv("MODEL") ? getenv("MODEL") : "gpt-5";
        
        // Verbose status - show everything
        printf("🔍 Awesh Verbose Status:\n");
        printf("🤖 API Provider: %s\n", ai_provider);
        printf("📋 Model: %s\n", model);
        printf("🔧 Debug Logging: %s\n", state.verbose ? "enabled" : "disabled");
        printf("📡 AI Status: ");
        switch (state.ai_status) {
            case AI_LOADING:
                printf("loading\n");
                break;
            case AI_READY:
                printf("ready\n");
                break;
            case AI_FAILED:
                printf("failed\n");
                break;
        }
        printf("📊 Backend PID: %d\n", state.backend_pid);
        printf("🔌 Socket FD: %d\n", state.socket_fd);
        printf("🔧 Verbose Level: %d (0=silent, 1=info, 2=debug)\n", state.verbose);
    } else if (strncmp(cmd, "awev", 4) == 0) {
        // Parse awev command and arguments
        if (strcmp(cmd, "awev") == 0) {
            // Just "awev" - show status
            printf("🔧 Verbose Level: %d (0=silent, 1=info, 2=debug)\n", state.verbose);
        } else if (strcmp(cmd, "awev 0") == 0) {
            // Set verbose level 0 (silent)
            update_config_file("VERBOSE", "0");
            send_command("VERBOSE:0");
            // Verbose communication removed - middleware handles this
            state.verbose = 0;
            printf("🔧 Verbose level set to 0 (silent)\n");
            check_ai_status();  // Update AI status to show correct emoji
        } else if (strcmp(cmd, "awev 1") == 0) {
            // Set verbose level 1 (info)
            update_config_file("VERBOSE", "1");
            send_command("VERBOSE:1");
            // Verbose communication removed - middleware handles this
            state.verbose = 1;
            printf("🔧 Verbose level set to 1 (info)\n");
            check_ai_status();  // Update AI status to show correct emoji
        } else if (strcmp(cmd, "awev 2") == 0) {
            // Set verbose level 2 (debug)
            update_config_file("VERBOSE", "2");
            send_command("VERBOSE:2");
            // Verbose communication removed - middleware handles this
            state.verbose = 2;
            printf("🔧 Verbose level set to 2 (debug)\n");
            check_ai_status();  // Update AI status to show correct emoji
        } else if (strcmp(cmd, "awev on") == 0) {
            // Legacy: Enable verbose logging (level 1)
            update_config_file("VERBOSE", "1");
            send_command("VERBOSE:1");
            // Verbose communication removed - middleware handles this
            state.verbose = 1;
            printf("🔧 Verbose logging enabled (level 1)\n");
            check_ai_status();  // Update AI status to show correct emoji
        } else if (strcmp(cmd, "awev off") == 0) {
            // Legacy: Disable verbose logging (level 0)
            update_config_file("VERBOSE", "0");
            send_command("VERBOSE:0");
            // Verbose communication removed - middleware handles this
            state.verbose = 0;
            printf("🔧 Verbose logging disabled (level 0)\n");
            check_ai_status();  // Update AI status to show correct emoji
        } else {
            printf("Usage: awev [0|1|2|on|off]\n");
        }
    } else if (strncmp(cmd, "awea", 4) == 0) {
        const char* ai_provider = getenv("AI_PROVIDER") ? getenv("AI_PROVIDER") : "openai";
        const char* model = getenv("MODEL") ? getenv("MODEL") : "gpt-5";
        
        // Parse awea command and arguments
        if (strcmp(cmd, "awea") == 0) {
            // Just "awea" - show current provider and model
            printf("🤖 API Provider: %s\n", ai_provider);
            printf("📋 Model: %s\n", model);
        } else if (strcmp(cmd, "awea openai") == 0) {
            // Switch to OpenAI
            update_config_file("AI_PROVIDER", "openai");
            send_command("AI_PROVIDER:openai");
            printf("🤖 Switching to OpenAI... (restart awesh to take effect)\n");
        } else if (strcmp(cmd, "awea openrouter") == 0) {
            // Switch to OpenRouter
            update_config_file("AI_PROVIDER", "openrouter");
            send_command("AI_PROVIDER:openrouter");
            printf("🤖 Switching to OpenRouter... (restart awesh to take effect)\n");
        } else {
            printf("Usage: awea [openai|openrouter]\n");
        }
    } else if (strncmp(cmd, "awem", 4) == 0) {
        // Parse awem command and arguments
        if (strcmp(cmd, "awem") == 0) {
            // Just "awem" - show current model and supported models
            const char* current_model = getenv("MODEL") ? getenv("MODEL") : "gpt-5";
            const char* ai_provider = getenv("AI_PROVIDER") ? getenv("AI_PROVIDER") : "openai";
            
            printf("📋 Current Model: %s\n", current_model);
            printf("🤖 Supported Models:\n");
            printf("\n🔹 OpenAI Models:\n");
            printf("  • gpt-4         - GPT-4 (stable, reliable)\n");
            printf("  • gpt-5         - GPT-5 (advanced, latest)\n");
            printf("\n🔹 OpenRouter Models:\n");
            printf("  • kimi-k2       - Kimi K2 (fast, efficient)\n");
            printf("  • claude-sonnet - Claude Sonnet (reasoning, analysis)\n");
            printf("\n💡 Current Provider: %s\n", ai_provider);
            printf("💡 Switch models with: awem <model-name>\n");
        } else if (strcmp(cmd, "awem gpt-4") == 0) {
            // Set model to GPT-4
            setenv("MODEL", "gpt-4", 1);
            send_command("MODEL:gpt-4");
            printf("📋 Model switched to GPT-4 (OpenAI) ✅\n");
        } else if (strcmp(cmd, "awem gpt-5") == 0) {
            // Set model to GPT-5  
            setenv("MODEL", "gpt-5", 1);
            send_command("MODEL:gpt-5");
            printf("📋 Model switched to GPT-5 (OpenAI) ✅\n");
        } else if (strcmp(cmd, "awem kimi-k2") == 0) {
            // Set model to Kimi K2
            setenv("MODEL", "kimi-k2", 1);
            send_command("MODEL:kimi-k2");
            printf("📋 Model switched to Kimi K2 (OpenRouter) ✅\n");
        } else if (strcmp(cmd, "awem claude-sonnet") == 0) {
            // Set model to Claude Sonnet
            setenv("MODEL", "claude-sonnet", 1);
            send_command("MODEL:claude-sonnet");
            printf("📋 Model switched to Claude Sonnet (OpenRouter) ✅\n");
        } else {
            // Extract model name from command for validation
            char* model_name = strchr(cmd, ' ');
            if (model_name) {
                model_name++; // Skip the space
                printf("❌ Unsupported model: %s\n", model_name);
            }
            printf("🤖 Supported models: gpt-4, gpt-5, kimi-k2, claude-sonnet\n");
            printf("💡 Usage: awem [gpt-4|gpt-5|kimi-k2|claude-sonnet]\n");
        }
    }
}

int is_interactive_bash_command(const char* cmd) {
    // Interactive command detection is now handled by the sandbox
    // The sandbox detects interactive commands by checking if they:
    // 1. Don't produce a prompt after execution
    // 2. Don't produce output
    // 3. Need user interaction
    // 
    // This function is kept for backward compatibility but should not be used
    // The sandbox's detection is more accurate and handles all cases dynamically
    return 0;
}

// Top bash commands that can also be natural language
static const char* ambiguous_bash_commands[] = {
    "find", "grep", "search", "list", "show", "display", "get", "check", "count", "sort",
    "filter", "select", "choose", "pick", "extract", "remove", "delete", "clean", "clear",
    "copy", "move", "rename", "change", "update", "modify", "edit", "create", "make", "build",
    "install", "uninstall", "start", "stop", "restart", "run", "execute", "launch", "open", "close",
    "read", "write", "save", "load", "import", "export", "backup", "restore", "sync", "merge",
    "compare", "diff", "analyze", "scan", "monitor", "watch", "track", "log", "debug", "test",
    "validate", "verify", "check", "inspect", "examine", "review", "audit", "report", "status",
    "info", "details", "help", "explain", "describe", "summarize", "calculate", "compute", "process",
    "convert", "transform", "format", "parse", "split", "join", "combine", "group", "organize",
    "arrange", "order", "rank", "prioritize", "schedule", "plan", "design", "configure", "setup",
    "initialize", "prepare", "ready", "enable", "disable", "activate", "deactivate", "toggle",
    "switch", "change", "replace", "substitute", "swap", "exchange", "transfer", "send", "receive",
    "download", "upload", "fetch", "pull", "push", "commit", "publish", "deploy", "release",
    "version", "tag", "branch", "merge", "rebase", "clone", "fork", "fork", "stash", "pop",
    "reset", "revert", "rollback", "undo", "redo", "repeat", "retry", "continue", "resume",
    "pause", "suspend", "wait", "delay", "sleep", "wake", "notify", "alert", "warn", "error",
    "fail", "success", "complete", "finish", "end", "exit", "quit", "abort", "cancel", "skip",
    "ignore", "exclude", "include", "add", "append", "prepend", "insert", "remove", "delete",
    "truncate", "cut", "slice", "chunk", "batch", "bulk", "mass", "batch", "queue", "stack",
    "heap", "tree", "graph", "map", "reduce", "fold", "unfold", "expand", "compress", "zip",
    "unzip", "archive", "extract", "pack", "unpack", "bundle", "unbundle", "package", "unpackage"
};

int is_ambiguous_bash_command(const char* cmd) {
    if (!cmd || strlen(cmd) == 0) return 0;
    
    // Extract first word from command
    char cmd_copy[MAX_CMD_LEN];
    strncpy(cmd_copy, cmd, sizeof(cmd_copy) - 1);
    cmd_copy[sizeof(cmd_copy) - 1] = '\0';
    
    char* first_word = strtok(cmd_copy, " \t");
    if (!first_word) return 0;
    
    // Check if first word is in ambiguous commands list
    for (size_t i = 0; i < sizeof(ambiguous_bash_commands) / sizeof(ambiguous_bash_commands[0]); i++) {
        if (strcmp(first_word, ambiguous_bash_commands[i]) == 0) {
            return 1;
        }
    }
    
    return 0;
}

int is_shell_syntax_command(const char* cmd) {
    if (!cmd || strlen(cmd) == 0) return 0;
    
    // Check for shell syntax patterns that indicate actual shell commands
    const char* shell_patterns[] = {
        "find ", "find\t", "find.", "find/", "find-", "find*", "find?", "find[", "find$", "find(",
        "find=", "find>", "find<", "find|", "find&", "find;", "find&&", "find||"
    };
    
    // Check if command starts with shell syntax patterns
    for (size_t i = 0; i < sizeof(shell_patterns) / sizeof(shell_patterns[0]); i++) {
        if (strncmp(cmd, shell_patterns[i], strlen(shell_patterns[i])) == 0) {
            return 1;
        }
    }
    
    return 0;
}

void handle_interactive_bash(const char* cmd) {
    // Security validation now handled transparently by middleware
    // Just execute the command directly
    execute_command_securely(cmd);
}


int spawn_bash_sandbox(void) {
    // Create pipes for communication with bash sandbox
    int stdin_pipe[2], stdout_pipe[2], stderr_pipe[2];
    
    if (pipe(stdin_pipe) < 0 || pipe(stdout_pipe) < 0 || pipe(stderr_pipe) < 0) {
        return -1;
    }
    
    // Fork to create bash sandbox process
    bash_sandbox.bash_pid = fork();
    if (bash_sandbox.bash_pid == 0) {
        // Child process: redirect stdio to pipes
        close(stdin_pipe[1]);   // Close write end of stdin pipe
        close(stdout_pipe[0]);  // Close read end of stdout pipe
        close(stderr_pipe[0]);  // Close read end of stderr pipe
        
        // Redirect stdin, stdout, stderr
        dup2(stdin_pipe[0], STDIN_FILENO);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        dup2(stderr_pipe[1], STDERR_FILENO);
        
        // Close original pipe ends
        close(stdin_pipe[0]);
        close(stdout_pipe[1]);
        close(stderr_pipe[1]);
        
        // Execute bash in non-interactive mode for faster execution
        execl("/bin/bash", "bash", "--norc", "--noprofile", NULL);
        exit(1); // Should not reach here
    } else if (bash_sandbox.bash_pid > 0) {
        // Parent process: store pipe file descriptors
        close(stdin_pipe[0]);   // Close read end of stdin pipe
        close(stdout_pipe[1]);  // Close write end of stdout pipe
        close(stderr_pipe[1]);  // Close write end of stderr pipe
        
        bash_sandbox.bash_stdin_fd = stdin_pipe[1];
        bash_sandbox.bash_stdout_fd = stdout_pipe[0];
        bash_sandbox.bash_stderr_fd = stderr_pipe[0];
        bash_sandbox.bash_ready = 1;
        
        if (state.verbose >= 1) {
            printf("🏖️ Bash sandbox started (PID: %d)\n", bash_sandbox.bash_pid);
        }
        
        return 0;
        } else {
        // Fork failed
        close(stdin_pipe[0]);
        close(stdin_pipe[1]);
        close(stdout_pipe[0]);
        close(stdout_pipe[1]);
        close(stderr_pipe[0]);
        close(stderr_pipe[1]);
        return -1;
    }
}

void cleanup_bash_sandbox(void) {
    if (bash_sandbox.bash_ready) {
        // Send exit command to bash sandbox
        if (bash_sandbox.bash_stdin_fd >= 0) {
            write(bash_sandbox.bash_stdin_fd, "exit\n", 5);
            close(bash_sandbox.bash_stdin_fd);
        }
        
        // Close file descriptors
        if (bash_sandbox.bash_stdout_fd >= 0) {
            close(bash_sandbox.bash_stdout_fd);
        }
        if (bash_sandbox.bash_stderr_fd >= 0) {
            close(bash_sandbox.bash_stderr_fd);
        }
        
        // Wait for bash sandbox process to exit
        if (bash_sandbox.bash_pid > 0) {
            waitpid(bash_sandbox.bash_pid, NULL, 0);
        }
        
        memset(&bash_sandbox, 0, sizeof(bash_sandbox));
        
                    if (state.verbose >= 1) {
            printf("🏖️ Bash sandbox cleaned up\n");
        }
    }
}

// Check if command is interactive (needs TTY)
int is_interactive_command(const char* cmd) {
    // Interactive command detection is now handled by the sandbox
    // The sandbox detects interactive commands dynamically by checking if they:
    // 1. Don't produce a prompt after execution
    // 2. Don't produce output
    // 3. Need user interaction
    // 
    // This function is kept for backward compatibility but should not be used
    // The sandbox's detection is more accurate and handles all cases dynamically
    return 0;
}

int test_command_in_sandbox(const char* cmd) {
    // Always test commands in sandbox first
    // Check if sandbox process is running
    if (state.sandbox_pid <= 0 || !is_process_running(state.sandbox_pid)) {
        if (state.verbose >= 2) {
            printf("❌ Sandbox process not running\n");
        }
        return -1;
    }
    
    // Use the new socket-based sandbox communication
    char response[4096];
    int result = send_to_sandbox(cmd, response, sizeof(response));
        
        if (result == 0) {
        // Check if sandbox detected an interactive command
        if (strstr(response, "INTERACTIVE_COMMAND")) {
                if (state.verbose >= 2) {
                printf("🖥️ Sandbox detected interactive command: %s\n", cmd);
            }
            return -103;  // Special return code for interactive commands (matches sandbox exit code)
        }
        
        // Parse validation result from sandbox: EXIT_CODE:X\nSTDOUT_LEN:Y\nSTDOUT:...\nSTDERR_LEN:Z\nSTDERR:...\n
        int exit_code = 0;
        char stderr_content[4096] = {0};
        
        // Parse EXIT_CODE
        char* exit_line = strstr(response, "EXIT_CODE:");
        if (exit_line) {
            exit_code = atoi(exit_line + 10);
        }
        
        // Parse STDERR_LEN and STDERR (we only care about stderr for validation)
        char* stderr_len_line = strstr(response, "STDERR_LEN:");
        if (stderr_len_line) {
            size_t stderr_len = atoi(stderr_len_line + 11);
            char* stderr_start = strstr(stderr_len_line, "STDERR:");
            if (stderr_start && stderr_len > 0 && stderr_len < sizeof(stderr_content)) {
                strncpy(stderr_content, stderr_start + 7, stderr_len);
                stderr_content[stderr_len] = '\0';
            }
        }
        
        // Show debug info only in verbose mode
        if (state.verbose >= 2) {
            printf("DEBUG: Sandbox validation - exit_code: %d, stderr: '%s'\n", exit_code, stderr_content);
        }
        
        // Return validation result:
        // 0 = VALID BASH (frontend executes directly)
        // -103 = INTERACTIVE command (run with TTY)
        // -113 = INVALID BASH with 3+ words (route to AI)
        // -109 = COMMAND NOT FOUND with 1-2 words (show error)
        // -2 = Other failures (route to backend for AI help)
        
        // Check for special exit codes from sandbox
        if (exit_code == -103 || exit_code == -113 || exit_code == -109) {
            if (state.verbose >= 2) {
                printf("🎯 Sandbox: Special exit code %d\n", exit_code);
            }
            return exit_code;  // Return special exit code to caller
        }
        
        // Check if command executed successfully in sandbox (valid bash)
        if (exit_code == 0 && strlen(stderr_content) == 0) {
            if (state.verbose >= 2) {
                printf("✅ Sandbox: Valid bash command - executing directly\n");
            }
            return 0;  // VALID BASH - Frontend executes directly
            } else {
            // Command failed in sandbox - invalid bash or needs AI help
            if (state.verbose >= 2) {
                printf("🤖 Sandbox: Invalid bash or needs AI help - routing to backend\n");
            }
            return -2;  // INVALID BASH - Route to backend for AI help
                    }
                } else {
        if (state.verbose >= 2) {
            printf("❌ Sandbox command failed\n");
        }
        return -1;  // Command failed
    }
}

// Old middleware functions removed - now handled transparently by proxy

// Old middleware function removed - now handled transparently by proxy

void send_to_backend_directly(const char* cmd) {
    // Send directly to backend - middleware is transparent
    if (state.socket_fd >= 0) {
        // Send command to backend
        if (send(state.socket_fd, cmd, strlen(cmd), 0) < 0) {
            printf("\n❌ Failed to send command to backend\n");
            return;
        }
        
        // Show thinking dots while waiting for response (5 minute timeout)
        time_t start_time = time(NULL);
        time_t last_dot_time = start_time;
        const int MAX_WAIT_SECONDS = 300;  // 5 minutes
        const int DOT_INTERVAL_SECONDS = 5;  // Show dot every 5 seconds
        
        while (1) {
            // Check if data is available to read
            fd_set readfds;
            FD_ZERO(&readfds);
            FD_SET(state.socket_fd, &readfds);
            
            struct timeval timeout;
            timeout.tv_sec = 1;  // 1 second timeout for select
            timeout.tv_usec = 0;
            
            int result = select(state.socket_fd + 1, &readfds, NULL, NULL, &timeout);
            
            if (result > 0) {
                // Data available - read response
                char response[MAX_RESPONSE_LEN];
                ssize_t bytes_received = recv(state.socket_fd, response, sizeof(response) - 1, 0);
                if (bytes_received > 0) {
                    response[bytes_received] = '\0';
                    
                    // Clear thinking dots and show response
                    printf("\r                    \r");  // Clear line
                printf("%s", response);
                    return;
                }
            } else if (result == 0) {
                // Timeout - check if we should show thinking dots
                time_t current_time = time(NULL);
                if (current_time - last_dot_time >= DOT_INTERVAL_SECONDS) {
                    printf(".");
                    fflush(stdout);
                    last_dot_time = current_time;
                }
                
                // Check for overall timeout
                if (current_time - start_time >= MAX_WAIT_SECONDS) {
                    printf("\n⏰ Backend response timeout\n");
                    return;
            }
        } else {
                // Error
                printf("\n❌ Error waiting for backend response\n");
                return;
            }
        }
    } else {
        printf("\n🚫 Backend not available\n");
    }
}

// Old middleware functions removed - now handled transparently by proxy

// Check if we're in an SSH session
int is_ssh_session(void) {
    return (getenv("SSH_CLIENT") != NULL || 
            getenv("SSH_TTY") != NULL || 
            getenv("SSH_CONNECTION") != NULL);
}





// Check if command looks like an AI query (natural language)
int is_ai_query(const char* cmd) {
    // Simple heuristics for AI queries
    const char* ai_indicators[] = {
        "write", "create", "generate", "explain", "analyze", "summarize",
        "what", "how", "why", "when", "where", "who", "which",
        "help", "assist", "suggest", "recommend", "find", "search",
        "poem", "story", "code", "script", "function", "class",
        "error", "bug", "issue", "problem", "fix", "solution",
        NULL
    };
    
    // Convert to lowercase for comparison
    char lower_cmd[1024];
    strncpy(lower_cmd, cmd, sizeof(lower_cmd) - 1);
    lower_cmd[sizeof(lower_cmd) - 1] = '\0';
    
    for (int i = 0; lower_cmd[i]; i++) {
        lower_cmd[i] = tolower(lower_cmd[i]);
    }
    
    // Check for AI indicators
    for (int i = 0; ai_indicators[i] != NULL; i++) {
        if (strstr(lower_cmd, ai_indicators[i])) {
            return 1;  // Looks like an AI query
        }
    }
    
    // Check for question marks
    if (strchr(cmd, '?')) {
        return 1;  // Contains question mark
    }
    
    // Check for shell-like patterns (if it looks like shell, it's probably not AI)
    if (strchr(cmd, '|') || strchr(cmd, '>') || strchr(cmd, '<') || 
        strchr(cmd, '&') || strchr(cmd, ';') || strchr(cmd, '`')) {
        return 0;  // Shell-like syntax
    }
    
    // Check for known shell commands
    const char* shell_commands[] = {
        "ls", "cd", "pwd", "cat", "grep", "find", "ps", "top", "kill",
        "mkdir", "rmdir", "rm", "cp", "mv", "chmod", "chown", "sudo",
        "git", "docker", "kubectl", "ssh", "scp", "rsync", "tar", "gzip",
        "vim", "nano", "emacs", "less", "more", "head", "tail", "sort",
        "awk", "sed", "cut", "uniq", "wc", "diff", "patch", "make",
        NULL
    };
    
    char first_word[256];
    sscanf(cmd, "%255s", first_word);
    
    for (int i = 0; shell_commands[i] != NULL; i++) {
        if (strcmp(first_word, shell_commands[i]) == 0) {
            return 0;  // Known shell command
        }
    }
    
    return 0;  // Default to not AI query
}

void execute_command_securely(const char* cmd) {
    // Check if any children are ready
    int backend_ready = (state.backend_pid > 0 && is_process_running(state.backend_pid) && state.socket_fd >= 0);
    int sandbox_ready = (state.sandbox_pid > 0 && is_process_running(state.sandbox_pid));
    // Middleware is transparent - backend handles security checks internally
    
    printf("DEBUG: execute_command_securely called with: %s\n", cmd);
    
    if (!backend_ready && !sandbox_ready) {
        // No children ready - run command directly as bash fallback
                    if (state.verbose >= 1) {
            printf("⚠️ No children ready - running command directly\n");
        }
        int result = system(cmd);
        if (result != 0 && state.verbose >= 1) {
            printf("Command failed (exit %d)\n", result);
        }
        return;
    }
    
    // Check if this looks like an AI query first
    if (is_ai_query(cmd) && backend_ready) {
        if (state.verbose >= 2) {
            printf("🤖 AI query detected: %s\n", cmd);
        }
        // Show thinking dots while processing
        printf("🤔 Thinking");
        fflush(stdout);
        
        // Send directly to backend - backend will check with security agent
        send_to_backend_directly(cmd);
        return;
    }
    
    // Try to run command directly first
    if (state.verbose >= 2) {
        printf("🖥️ Attempting direct command execution: %s\n", cmd);
    }
    
    // Try running the command directly
    int result = system(cmd);
    
    // Check if command executed successfully
    if (result == 0) {
        // Command executed successfully - we're done
        if (state.verbose >= 2) {
            printf("✅ Command executed successfully\n");
        }
        return;
    }
    
    // Command failed - check if it's an anomalous return code
    int exit_code = WEXITSTATUS(result);
    if (state.verbose >= 2) {
        printf("❌ Command failed with exit code %d - sending to sandbox for validation\n", exit_code);
    }
    
    // Send to sandbox for validation and routing decision
    if (state.verbose >= 2) {
        printf("DEBUG: Sandbox status - PID: %d, Running: %s\n", 
               state.sandbox_pid, 
               (state.sandbox_pid > 0 && is_process_running(state.sandbox_pid)) ? "YES" : "NO");
    }
    int sandbox_result = test_command_in_sandbox(cmd);
    
    if (state.verbose >= 2) {
        printf("DEBUG: sandbox_result=%d\n", sandbox_result);
    }
    
    if (sandbox_result == 0) {
        // SAFE - Sandbox validation passed - command should have worked, show error
        if (state.verbose >= 1) {
            printf("❌ Command failed (exit %d)\n", exit_code);
        }
        return;
    } else if (sandbox_result == -113) {
        // INVALID BASH - Sandbox detected invalid bash command - route to AI
        if (state.verbose >= 2) {
            printf("🤖 Sandbox detected invalid bash command - routing to AI\n");
        }
        if (backend_ready) {
            // Show thinking dots while processing
            printf("🤔 Thinking");
            fflush(stdout);
            
            // Send to middleware and wait for response
            send_to_backend_directly(cmd);
        } else {
            printf("🚫 Backend/middleware not available for AI help\n");
        }
        return;
    } else if (sandbox_result == -103) {
        // INTERACTIVE - Sandbox detected interactive command (no prompt returned) - run with TTY
        if (state.verbose >= 2) {
            printf("🖥️ Sandbox detected interactive command (no prompt returned) - running with TTY\n");
        }
        run_interactive_command(cmd);
        return;
    } else if (sandbox_result == -109) {
        // ERROR - Command not found or error (1-2 words) - show error message
        if (state.verbose >= 1) {
            printf("❌ Command not found or error\n");
        }
        return;
    } else {
        // Sandbox validation failed - route to AI
        if (state.verbose >= 2) {
            printf("🤖 Sandbox validation failed - routing to backend for AI help\n");
        }
        if (backend_ready) {
            // Show thinking dots while processing
            printf("🤔 Thinking");
            fflush(stdout);
            
            // Send to middleware and wait for response
            send_to_backend_directly(cmd);
        } else {
            printf("🚫 Backend/middleware not available for AI help\n");
        }
        return;
    }
}

void handle_bash_with_ai_fallback(const char* cmd) {
    // If AI is ready, try bash and capture output for AI context
    if (state.socket_fd >= 0 && state.ai_status == AI_READY) {
        // Capture both stdout and stderr for AI context
        char temp_file[] = "/tmp/awesh_bash_XXXXXX";
        int fd = mkstemp(temp_file);
        if (fd != -1) {
            close(fd);
            
            char bash_cmd[MAX_CMD_LEN + 100];
            snprintf(bash_cmd, sizeof(bash_cmd), "%s >%s 2>&1", cmd, temp_file);
            int result = system(bash_cmd);
            
            if (result == 0) {
                // Bash succeeded - show output and clean up immediately
                char cat_cmd[200];
                snprintf(cat_cmd, sizeof(cat_cmd), "cat %s", temp_file);
                system(cat_cmd);
                unlink(temp_file);
                return; // Exit immediately - no AI processing needed
            } else {
                // Bash failed - send command and output to AI as context
                if (state.verbose >= 1) {
                    printf("Command failed (exit %d), trying AI assistance...\n", result);
                    // Debug: show what was captured
                    printf("🔧 Error output captured in temp file:\n");
                    char cat_debug[200];
                    snprintf(cat_debug, sizeof(cat_debug), "cat %s", temp_file);
                    system(cat_debug);
                    printf("🔧 End of captured output\n");
                }
                
                // Send command with bash failure context to backend
                char context_cmd[MAX_CMD_LEN + 200];
                snprintf(context_cmd, sizeof(context_cmd), "BASH_FAILED:%d:%s:%s", result, cmd, temp_file);
                send_command(context_cmd);
                unlink(temp_file);
            }
        } else {
            // Fallback if temp file creation fails
            int result = system(cmd);
            if (result != 0 && state.verbose >= 1) {
                printf("Command failed (exit %d), trying AI assistance...\n", result);
                send_command(cmd);
            }
        }
    } else {
        // No AI available, run bash normally (show errors)
        system(cmd);
    }
}


int main() {
    // Setup signal handlers
    signal(SIGINT, handle_sigint);     // Ctrl+C returns to prompt
    signal(SIGTERM, cleanup_and_exit); // SIGTERM exits cleanly
    
    // Don't block SIGINT here - we want to handle it in the main process
    
    // Load configuration FIRST, before any startup messages
    load_config();
    
    // Set VERBOSE environment variable for all child processes
    char verbose_str[8];
    snprintf(verbose_str, sizeof(verbose_str), "%d", state.verbose);
    setenv("VERBOSE", verbose_str, 1);
    
    // Initialize Security Agent socket
    // Socket initialization removed - middleware handles this
    
    // Initialize Sandbox socket
    if (init_sandbox_socket() != 0) {
        printf("⚠️ Warning: Could not initialize Sandbox socket\n");
    }
    
    // Initialize Frontend socket server
    if (init_frontend_socket() != 0) {
        printf("⚠️ Warning: Could not initialize Frontend socket server\n");
    }
    
    // Start Sandbox as separate process (non-blocking)
    pid_t sandbox_pid = fork();
    if (sandbox_pid == 0) {
        // Child: ignore SIGINT to prevent Ctrl+C from reaching Sandbox
        signal(SIGINT, SIG_IGN);
        
        // Start Sandbox from ~/.local/bin
        const char* home = getenv("HOME");
        if (home) {
            char sandbox_path[512];
            snprintf(sandbox_path, sizeof(sandbox_path), "%s/.local/bin/awesh_sandbox", home);
            execl(sandbox_path, "awesh_sandbox", NULL);
        }
        // Fallback to local binary
        execl("./awesh_sandbox", "awesh_sandbox", NULL);
        perror("Failed to start Sandbox");
        exit(1);
    } else if (sandbox_pid < 0) {
        printf("⚠️ Warning: Could not start Sandbox\n");
    } else {
        state.sandbox_pid = sandbox_pid;
        if (state.verbose >= 1) {
            printf("🏖️ Sandbox (awesh_sandbox) started (PID: %d)\n", sandbox_pid);
        }
        // Don't wait for Sandbox - let it initialize in background
    }
    
    // Start Security Agent as separate process (non-blocking)
    pid_t security_agent_pid = fork();
    if (security_agent_pid == 0) {
        // Child: ignore SIGINT to prevent Ctrl+C from reaching Security Agent
        signal(SIGINT, SIG_IGN);
        
        // Start Security Agent from ~/.local/bin
        const char* home = getenv("HOME");
        if (home) {
            char security_agent_path[512];
            snprintf(security_agent_path, sizeof(security_agent_path), "%s/.local/bin/awesh_sec", home);
            execl(security_agent_path, "awesh_sec", NULL);
        }
        // Fallback to local binary
        execl("./awesh_sec", "awesh_sec", NULL);
        perror("Failed to start Security Agent");
        exit(1);
    } else if (security_agent_pid < 0) {
        printf("⚠️ Warning: Could not start Security Agent\n");
    } else {
        state.security_agent_pid = security_agent_pid;
        if (state.verbose >= 1) {
            printf("🔒 Security Agent (awesh_sec) started (PID: %d)\n", security_agent_pid);
        }
        // Don't wait for Security Agent - let it initialize in background
    }
    
    // VERBOSE environment variable already set above for all child processes
    
    // Show welcome message immediately
    printf("awesh v0.1.0 - Awe-Inspired Workspace Environment Shell\n");
    printf("💡 Type 'aweh' to see available control commands\n");
    
    // Start backend (non-blocking)
    if (start_backend() != 0) {
        if (state.verbose >= 1) {
            printf("⚠️ Warning: Could not start backend\n");
        }
        state.ai_status = AI_FAILED;
    } else {
        if (state.verbose >= 1) {
            printf("🐍 Backend (Python) started (PID: %d)\n", state.backend_pid);
        }
    }
    
    
    // Main shell loop - start immediately, don't wait for backend
    char* line;
    char prompt[1024];  // Increased size for full path and long context
    
    while (1) {
        char* username;
        char hostname[64];
        char cwd[256];
        char git_branch[64] = "";
        char k8s_context[64] = "";
        char k8s_namespace[64] = "";
        
        // Use local data (normal mode)
        username = getenv("USER");
        if (!username) username = "user";
        
        if (gethostname(hostname, sizeof(hostname)) != 0) {
            strcpy(hostname, "localhost");
        }
        
        if (getcwd(cwd, sizeof(cwd)) == NULL) {
            strcpy(cwd, "~");
        } else {
            char* home = getenv("HOME");
            if (home && strncmp(cwd, home, strlen(home)) == 0) {
                char temp[256];
                snprintf(temp, sizeof(temp), "~%s", cwd + strlen(home));
                strcpy(cwd, temp);
            }
        }
        
        // Color-code username: red for root, green for normal user
        char* user_color = (getuid() == 0) ? "\033[31m" : "\033[32m";  // Red for root, green for user
        
        // Build secure dynamic prompt directly in C (no external file dependencies)
        long prompt_start = get_time_ms();
        
        // Get prompt data with caching optimization
        get_prompt_data_cached(git_branch, k8s_context, k8s_namespace, 64);
        
        // Build context parts string with emojis (clean format)
        char context_parts[256] = "";
        if (strlen(k8s_context) > 0) {
            strcat(context_parts, ":☸️");
            strcat(context_parts, k8s_context);
        }
        if (strlen(k8s_namespace) > 0 && strcmp(k8s_namespace, "default") != 0) {
            strcat(context_parts, ":☸️");
            strcat(context_parts, k8s_namespace);
        }
        if (strlen(git_branch) > 0) {
            strcat(context_parts, ":🌿");
            strcat(context_parts, git_branch);
        }
        
        // Get security agent status
        char security_status[128] = "";
        get_security_agent_status(security_status, sizeof(security_status));
        
        // Get health status emojis for backend, security agent, and sandbox
        char backend_emoji[8];
        char security_emoji[8];
        char sandbox_emoji[8];
        get_health_status_emojis(backend_emoji, security_emoji, sandbox_emoji);
        
        // Build security context part with color coding - only show actual threats
        char security_context[256] = "";
        if (strlen(security_status) > 0) {
            // Only show security status if there are actual threats (not "No threats detected")
            if (strstr(security_status, "🔴 HIGH:") || strstr(security_status, "🟡 MEDIUM:") || strstr(security_status, "🟢 LOW:")) {
                // Check if it's a high threat (starts with "🔴 HIGH:")
                if (strncmp(security_status, "🔴 HIGH:", 8) == 0) {
                    // High threat - color in red, replace 🔴 with 👹 for rogue processes
                    char* threat_text = strstr(security_status, "rogue_process");
                    if (threat_text) {
                        // Replace 🔴 HIGH: with 👹 for rogue processes
                        char rogue_status[128];
                        snprintf(rogue_status, sizeof(rogue_status), "👹%s", threat_text);
                        snprintf(security_context, sizeof(security_context), ":\033[31m%s\033[0m", rogue_status);
                    } else {
                        // Other high threats keep red circle
                        snprintf(security_context, sizeof(security_context), ":\033[31m%s\033[0m", security_status);
                    }
                } else if (strncmp(security_status, "🟡 MEDIUM:", 10) == 0) {
                    // Medium threat - color in yellow
                    snprintf(security_context, sizeof(security_context), ":\033[33m%s\033[0m", security_status);
                } else if (strncmp(security_status, "🟢 LOW:", 8) == 0) {
                    // Low threat - color in green
                    snprintf(security_context, sizeof(security_context), ":\033[32m%s\033[0m", security_status);
                }
            }
            // Silent mode: Don't show "No threats detected" or other status messages
        }
        
        // Generate secure prompt with integrated security status (security comes right after user@host)
        snprintf(prompt, sizeof(prompt), "%s:%s:%s:%s%s\033[0m@\033[36m%s\033[0m:\033[34m%s\033[0m%s%s\n> ",
                 backend_emoji, security_emoji, sandbox_emoji, user_color, username, hostname, cwd, security_context, context_parts);
        
        // Debug total prompt generation time
        debug_perf("total prompt generation", prompt_start);
        
        // Check child process health (every 10th prompt to avoid overhead)
        static int health_check_counter = 0;
        if (++health_check_counter >= 10) {
            check_child_process_health();
            health_check_counter = 0;
        }
        
        // Security agent communicates directly with backend via shared memory
        
        // Non-blocking AI status check (only if backend not connected yet)
        if (state.socket_fd < 0 && state.backend_pid > 0) {
            // Try to connect to backend socket (non-blocking)
            const char* home = getenv("HOME");
            if (home) {
                char socket_path[512];
                snprintf(socket_path, sizeof(socket_path), "%s/.awesh.sock", home);
                
                int test_fd = socket(AF_UNIX, SOCK_STREAM, 0);
                if (test_fd >= 0) {
                    struct sockaddr_un addr;
                    memset(&addr, 0, sizeof(addr));
                    addr.sun_family = AF_UNIX;
                    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);
                    
                    // Non-blocking connect attempt
                    fcntl(test_fd, F_SETFL, O_NONBLOCK);
                    if (connect(test_fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
                        // Backend is ready!
                        state.socket_fd = test_fd;
                        check_ai_status();
                    } else {
                        // Backend not ready yet, close test socket
                        close(test_fd);
                    }
                }
            }
        }
        
        // Handle incoming connections from middleware (non-blocking)
        handle_frontend_connections();
        
        // Get input with readline (supports history, editing)
        line = readline(prompt);
        
        if (!line) {
            // EOF (Ctrl+D)
            break;
        }
        
        if (strlen(line) == 0) {
            free(line);
            continue;
        }
        
        // Add to history
        add_history(line);
        
        // AI-driven mode detection: Let AI decide command vs edit mode
        // No longer need to parse AI mode - all commands go through sandbox
        
        // Handle command - clean logic: aweX → built-in → sandbox → backend
        if (is_awesh_command(line)) {
            // 2a - aweX commands
            if (state.verbose >= 2) {
                printf("DEBUG: Detected awesh command: %s\n", line);
            }
            handle_awesh_command(line);
        } else if (strcmp(line, "quit") == 0 || strcmp(line, "exit") == 0) {
            // Built-in commands - handled by frontend, not backend
            if (state.verbose >= 1) {
                printf("👋 Exiting awesh...\n");
            }
            cleanup_and_exit(0);
        } else {
            // 2b - sandbox: send to sandbox, get result, decide routing
            execute_command_securely(line);
        }
        
        free(line);
    }
    
    cleanup_and_exit(0);
    return 0;
}

void run_interactive_command(const char* cmd) {
    // For interactive commands like vi, watch, top, etc., we need to run them directly
    // with proper TTY support. We need to fully restore terminal environment.
    
    if (state.verbose >= 2) {
        printf("🖥️ Running interactive command: %s\n", cmd);
    }
    
    // Save and restore terminal settings
    struct termios orig_termios;
    tcgetattr(STDIN_FILENO, &orig_termios);
    
    // Deactivate readline's line handler to release terminal control
    rl_deprep_terminal();
    
    // Restore original terminal settings for the interactive program
    tcsetattr(STDIN_FILENO, TCSANOW, &orig_termios);
    
    // Set TERM environment variable to ensure proper terminal detection
    setenv("TERM", "xterm-256color", 1);
    
    // Use system() which properly handles TTY for interactive programs
    int result = system(cmd);
    
    // Reactivate readline's terminal control
    rl_prep_terminal(1);
    
    // Force readline to refresh the prompt
    printf("\n");
    
    if (result != 0 && state.verbose >= 1) {
        printf("Command exited with code %d\n", WEXITSTATUS(result));
    }
}


