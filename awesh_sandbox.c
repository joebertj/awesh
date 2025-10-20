#define _POSIX_C_SOURCE 200809L
#define _DEFAULT_SOURCE
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
#include <time.h>
#include <sys/time.h>
#include <pty.h>
#include <utmp.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/mman.h>

#define MAX_CMD_LEN 1024
#define MAX_RESPONSE_LEN 65536
#define MMAP_SIZE (1024 * 1024)  // 1MB mmap file

static char socket_path[512];
static char sandbox_root[512] = "/tmp/awesh_sandbox_root";
static char mmap_path[512] = "/tmp/awesh_sandbox_output.mmap";
static int sandbox_fs_setup = 0;
static int mmap_fd = -1;
static char* mmap_ptr = NULL;

// Setup mmap file for output communication
int setup_mmap_file(void) {
    if (mmap_fd >= 0) {
        return 0; // Already setup
    }
    
    // Create mmap file
    mmap_fd = open(mmap_path, O_CREAT | O_RDWR | O_TRUNC, 0644);
    if (mmap_fd < 0) {
        perror("Failed to create mmap file");
        return -1;
    }
    
    // Set file size
    if (ftruncate(mmap_fd, MMAP_SIZE) < 0) {
        perror("Failed to set mmap file size");
        close(mmap_fd);
        mmap_fd = -1;
        return -1;
    }
    
    // Map the file into memory
    mmap_ptr = mmap(NULL, MMAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, mmap_fd, 0);
    if (mmap_ptr == MAP_FAILED) {
        perror("Failed to mmap file");
        close(mmap_fd);
        mmap_fd = -1;
        return -1;
    }
    
    // Initialize with empty simple structure
    strcpy(mmap_ptr, "EXIT_CODE:0\nSTDOUT:\nSTDERR:\n");
    
    return 0;
}

// Cleanup mmap file
void cleanup_mmap_file(void) {
    if (mmap_ptr && mmap_ptr != MAP_FAILED) {
        munmap(mmap_ptr, MMAP_SIZE);
        mmap_ptr = NULL;
    }
    if (mmap_fd >= 0) {
        close(mmap_fd);
        mmap_fd = -1;
    }
    unlink(mmap_path);
}

// Write command result to mmap file
void write_result_to_mmap(int exit_code, const char* stdout_content, const char* stderr_content) {
    if (!mmap_ptr || mmap_ptr == MAP_FAILED) {
        return;
    }
    
    // Clear the mmap area
    memset(mmap_ptr, 0, MMAP_SIZE);
    
    // Write simple format result with proper escaping
    // Use a more robust format that handles special characters
    char* ptr = mmap_ptr;
    int remaining = MMAP_SIZE - 1;
    
    // Write EXIT_CODE
    int written = snprintf(ptr, remaining, "EXIT_CODE:%d\n", exit_code);
    if (written > 0 && written < remaining) {
        ptr += written;
        remaining -= written;
    }
    
    // Write STDOUT with length prefix to handle special characters
    const char* stdout_str = stdout_content ? stdout_content : "";
    size_t stdout_len = strlen(stdout_str);
    written = snprintf(ptr, remaining, "STDOUT_LEN:%zu\nSTDOUT:", stdout_len);
    if (written > 0 && written < remaining) {
        ptr += written;
        remaining -= written;
        
        // Write stdout content directly (no formatting to avoid issues with special chars)
        if (stdout_len > 0 && (int)stdout_len < remaining) {
            memcpy(ptr, stdout_str, stdout_len);
            ptr += stdout_len;
            remaining -= (int)stdout_len;
        }
        if (remaining > 0) {
            *ptr++ = '\n';
            remaining--;
        }
    }
    
    // Write STDERR with length prefix
    const char* stderr_str = stderr_content ? stderr_content : "";
    size_t stderr_len = strlen(stderr_str);
    written = snprintf(ptr, remaining, "STDERR_LEN:%zu\nSTDERR:", stderr_len);
    if (written > 0 && written < remaining) {
        ptr += written;
        remaining -= written;
        
        // Write stderr content directly
        if (stderr_len > 0 && (int)stderr_len < remaining) {
            memcpy(ptr, stderr_str, stderr_len);
            ptr += stderr_len;
            remaining -= (int)stderr_len;
        }
        if (remaining > 0) {
            *ptr++ = '\n';
            remaining--;
        }
    }
    
    // Ensure null termination
    *ptr = '\0';
}

// Setup sandbox with read-only mount of entire root filesystem
int setup_sandbox_filesystem(void) {
    if (sandbox_fs_setup) {
        return 0; // Already setup
    }
    
    // Create sandbox root directory
    if (mkdir(sandbox_root, 0755) != 0 && errno != EEXIST) {
        perror("Failed to create sandbox root");
        return -1;
    }
    
    // Bind mount entire root filesystem as read-only
    // This gives sandbox access to everything user can see, but read-only
    if (mount("/", sandbox_root, NULL, MS_BIND | MS_RDONLY, NULL) != 0) {
        // If bind mount fails, try alternative approach
        perror("Failed to bind mount root filesystem");
        
        // Fallback: create symlinks to essential directories
        const char* essential_dirs[] = {"/bin", "/usr", "/lib", "/lib64", "/etc", "/opt", "/sbin"};
        
        for (size_t i = 0; i < sizeof(essential_dirs) / sizeof(essential_dirs[0]); i++) {
            char target_path[1024];
            snprintf(target_path, sizeof(target_path), "%s%s", sandbox_root, essential_dirs[i]);
            
            // Create symlink to original directory
            symlink(essential_dirs[i], target_path);
        }
        
        // Create writable directories
        const char* writable_dirs[] = {"/tmp", "/var", "/home"};
        for (size_t i = 0; i < sizeof(writable_dirs) / sizeof(writable_dirs[0]); i++) {
            char target_path[1024];
            snprintf(target_path, sizeof(target_path), "%s%s", sandbox_root, writable_dirs[i]);
            mkdir(target_path, 0755);
        }
    }
    
    sandbox_fs_setup = 1;
    return 0;
}

// Cleanup sandbox filesystem
void cleanup_sandbox_filesystem(void) {
    if (!sandbox_fs_setup) {
        return;
    }
    
    // Unmount the bind mount
    umount(sandbox_root); // Ignore errors
    
    // Remove sandbox root (recursive)
    char cleanup_cmd[1024];
    snprintf(cleanup_cmd, sizeof(cleanup_cmd), "rm -rf %s", sandbox_root);
    system(cleanup_cmd);
    
    sandbox_fs_setup = 0;
}

// Bash sandbox process with PTY support
static struct {
    int bash_pid;
    int master_fd;      // PTY master
    int slave_fd;       // PTY slave
    int bash_ready;
} bash_sandbox = {0};

int spawn_bash_sandbox(void) {
    // Create PTY for proper TTY support
    char slave_name[256];
    
    if (openpty(&bash_sandbox.master_fd, &bash_sandbox.slave_fd, slave_name, NULL, NULL) < 0) {
        perror("Failed to create PTY");
        return -1;
    }
    
    // Fork to create bash sandbox process
    bash_sandbox.bash_pid = fork();
    if (bash_sandbox.bash_pid == 0) {
        // Child process: use PTY slave as stdio
        close(bash_sandbox.master_fd);  // Close master in child
        
        // Redirect stdin, stdout, stderr to PTY slave (keep output for capture)
        dup2(bash_sandbox.slave_fd, STDIN_FILENO);
        dup2(bash_sandbox.slave_fd, STDOUT_FILENO);
        dup2(bash_sandbox.slave_fd, STDERR_FILENO);
        
        // Close slave fd (now duplicated)
        close(bash_sandbox.slave_fd);
        
        // Set TERM environment variable for proper terminal support
        setenv("TERM", "xterm-256color", 1);
        
        // Ensure HOME is set for tilde expansion
        const char* home = getenv("HOME");
        if (home) {
            setenv("HOME", home, 1);
        }
        
        // Disable command echo in bash
        setenv("PS1", "$ ", 1);
        
        // Setup sandbox filesystem (read-only mount of entire root)
        if (setup_sandbox_filesystem() == 0) {
            // Change root to sandbox (chroot)
            if (chroot(sandbox_root) == 0) {
                // Change to the current working directory
                char* cwd = getenv("PWD");
                if (cwd && chdir(cwd) != 0) {
                    // If PWD fails, try to get current directory
                    char current_dir[1024];
                    if (getcwd(current_dir, sizeof(current_dir)) != NULL) {
                        chdir(current_dir);
                    }
                }
            }
        }
        
        // Execute bash with echo disabled
        execl("/bin/bash", "bash", "--norc", "--noprofile", "-c", "stty -echo; exec bash", NULL);
        exit(1); // Should not reach here
    } else if (bash_sandbox.bash_pid > 0) {
        // Parent process: close slave fd, keep master
        close(bash_sandbox.slave_fd);
        bash_sandbox.bash_ready = 1;
        
        return 0;
    } else {
        // Fork failed
        close(bash_sandbox.master_fd);
        close(bash_sandbox.slave_fd);
        return -1;
    }
}

void cleanup_bash_sandbox(void) {
    if (bash_sandbox.bash_ready) {
        // Send exit command to bash sandbox
        if (bash_sandbox.master_fd >= 0) {
            write(bash_sandbox.master_fd, "exit\n", 5);
            close(bash_sandbox.master_fd);
        }
        
        // Wait for bash sandbox process to exit
        if (bash_sandbox.bash_pid > 0) {
            waitpid(bash_sandbox.bash_pid, NULL, 0);
        }
        
        memset(&bash_sandbox, 0, sizeof(bash_sandbox));
    }
}

int execute_command_in_sandbox(const char* cmd, char* stdout_buf, char* stderr_buf, int* exit_code) {
    if (!bash_sandbox.bash_ready) {
        return -1;
    }
    
    // Clear output buffers
    memset(stdout_buf, 0, MAX_RESPONSE_LEN);
    memset(stderr_buf, 0, MAX_RESPONSE_LEN);
    *exit_code = 0;
    
    // Clear any existing output from PTY before sending command
    fd_set readfds;
    struct timeval clear_timeout;
    FD_ZERO(&readfds);
    FD_SET(bash_sandbox.master_fd, &readfds);
    clear_timeout.tv_sec = 0;
    clear_timeout.tv_usec = 10000;  // 10ms
    
    char clear_buffer[1024];
    while (select(bash_sandbox.master_fd + 1, &readfds, NULL, NULL, &clear_timeout) > 0) {
        read(bash_sandbox.master_fd, clear_buffer, sizeof(clear_buffer) - 1);
        FD_ZERO(&readfds);
        FD_SET(bash_sandbox.master_fd, &readfds);
        clear_timeout.tv_sec = 0;
        clear_timeout.tv_usec = 10000;  // 10ms
    }
    
    // Send command to bash sandbox via PTY master with shell expansion
    char full_cmd[MAX_CMD_LEN + 50];
    snprintf(full_cmd, sizeof(full_cmd), "bash -c '%s'; echo \"EXIT_CODE:$?\"\n", cmd);
    
    if (write(bash_sandbox.master_fd, full_cmd, strlen(full_cmd)) < 0) {
        return -1;
    }
    
    // First, get the actual PS1 prompt from the sandbox
    char ps1_prompt[256] = {0};
    
    // Send command to get PS1
    write(bash_sandbox.master_fd, "echo \"PS1_PROMPT:$PS1\"\n", 23);
    
    // Read PS1 prompt
    FD_ZERO(&readfds);
    FD_SET(bash_sandbox.master_fd, &readfds);
    struct timeval ps1_timeout;
    ps1_timeout.tv_sec = 1;
    ps1_timeout.tv_usec = 0;
    
    if (select(bash_sandbox.master_fd + 1, &readfds, NULL, NULL, &ps1_timeout) > 0) {
        char ps1_buffer[512];
        ssize_t ps1_bytes = read(bash_sandbox.master_fd, ps1_buffer, sizeof(ps1_buffer) - 1);
        if (ps1_bytes > 0) {
            ps1_buffer[ps1_bytes] = '\0';
            
            // Extract PS1 from the output
            char* ps1_start = strstr(ps1_buffer, "PS1_PROMPT:");
            if (ps1_start) {
                ps1_start += 11; // Skip "PS1_PROMPT:"
                char* ps1_end = strchr(ps1_start, '\n');
                if (ps1_end) {
                    size_t ps1_len = ps1_end - ps1_start;
                    if (ps1_len < sizeof(ps1_prompt)) {
                        strncpy(ps1_prompt, ps1_start, ps1_len);
                        ps1_prompt[ps1_len] = '\0';
                    }
                }
            }
        }
    }
    
    // If we couldn't get PS1, use a default
    if (strlen(ps1_prompt) == 0) {
        strcpy(ps1_prompt, "$ ");
    }
    
    // Now run the actual command and check if PS1 appears at the end
    // Read output with timeout from PTY master
    char buffer[1024];
    int total_len = 0;
    int prompt_detected = 0;
    int max_attempts = 50;  // Increased attempts to capture all output (5 seconds total)
    int attempts = 0;
    int consecutive_empty_reads = 0;
    
    // Set up select for reading from PTY master
    FD_ZERO(&readfds);
    FD_SET(bash_sandbox.master_fd, &readfds);
    
    struct timeval timeout;
    timeout.tv_sec = 0;
    timeout.tv_usec = 100000;  // 100ms timeout per read
    
    while (attempts < max_attempts) {
        int result = select(bash_sandbox.master_fd + 1, &readfds, NULL, NULL, &timeout);
        
        if (result > 0) {
            // Read from PTY master (contains both stdout and stderr)
            ssize_t bytes_read = read(bash_sandbox.master_fd, buffer, sizeof(buffer) - 1);
            if (bytes_read > 0) {
                buffer[bytes_read] = '\0';
                if (total_len + bytes_read < MAX_RESPONSE_LEN - 1) {
                    memcpy(stdout_buf + total_len, buffer, bytes_read);
                    total_len += bytes_read;
                }
                
                // Reset consecutive empty reads counter
                consecutive_empty_reads = 0;
                
                // Check if the actual PS1 prompt is present (indicates command completed)
                if (strstr(buffer, ps1_prompt)) {
                    prompt_detected = 1;
                    // Don't break immediately - wait a bit more for any error output
                    attempts++;
                    continue;
                }
            } else {
                consecutive_empty_reads++;
                if (consecutive_empty_reads >= 10) {
                    break;  // No more data after multiple empty reads
                }
            }
        } else {
            // Timeout - check if we have any output
            if (total_len > 0 && prompt_detected) {
                break;  // We have output and prompt detected, command completed
            }
            attempts++;
        }
        
        // Reset select for next iteration
        FD_ZERO(&readfds);
        FD_SET(bash_sandbox.master_fd, &readfds);
        timeout.tv_sec = 0;
        timeout.tv_usec = 100000;  // 100ms
    }
    
    // Null-terminate the output
    stdout_buf[total_len] = '\0';
    
    // Filter out command echo and bash prompt from output
    // Remove any lines that match the command or common bash prompts
    char* line_start = stdout_buf;
    char* filtered_buf = stdout_buf;
    int filtered_len = 0;
    
    while (line_start && *line_start) {
        char* line_end = strchr(line_start, '\n');
        if (!line_end) {
            line_end = line_start + strlen(line_start);
        }
        
        // Extract current line
        size_t line_len = line_end - line_start;
        char current_line[256];
        if (line_len < sizeof(current_line)) {
            strncpy(current_line, line_start, line_len);
            current_line[line_len] = '\0';
            
            // Remove trailing newline for comparison
            if (current_line[line_len - 1] == '\n') {
                current_line[line_len - 1] = '\0';
            }
            
            // Skip lines that are command echo or bash prompts
            // Also skip lines that start with the command (in case of partial echo)
            if (strcmp(current_line, cmd) != 0 && 
                strncmp(current_line, cmd, strlen(cmd)) != 0 &&
                strstr(current_line, "$ ") == NULL &&
                strstr(current_line, "# ") == NULL &&
                strstr(current_line, "> ") == NULL &&
                strlen(current_line) > 0) {
                
                // Keep this line
                memmove(filtered_buf, line_start, line_len);
                filtered_buf += line_len;
                filtered_len += line_len;
            }
        }
        
        // Move to next line
        line_start = line_end;
        if (*line_start == '\n') {
            line_start++;
        }
    }
    
    // Null-terminate filtered output
    *filtered_buf = '\0';
    total_len = filtered_len;
    
    // Filter out terminal control characters (ANSI escape sequences)
    char* clean_ptr = stdout_buf;
    int in_escape = 0;
    
    for (int i = 0; i < total_len; i++) {
        if (stdout_buf[i] == '\033') {
            in_escape = 1;
            continue;
        }
        if (in_escape) {
            if (stdout_buf[i] == 'm' || stdout_buf[i] == 'l' || stdout_buf[i] == 'h' || 
                stdout_buf[i] == 'J' || stdout_buf[i] == 'K' || stdout_buf[i] == 'H') {
                in_escape = 0;
            }
            continue;
        }
        *clean_ptr++ = stdout_buf[i];
    }
    *clean_ptr = '\0';
    total_len = clean_ptr - stdout_buf;
    
    // Debug: Print what we detected (only in verbose mode)
    // Note: We can't access frontend verbose level from sandbox, so we'll check environment
    const char* verbose_str = getenv("VERBOSE");
    int verbose = verbose_str ? atoi(verbose_str) : 0;
    if (verbose >= 2) {
        fprintf(stderr, "DEBUG: prompt_detected=%d, total_len=%d, ps1='%s', cmd='%s'\n", prompt_detected, total_len, ps1_prompt, cmd);
    }
    
    // If no prompt detected, command is likely interactive
    if (!prompt_detected) {
        // Command is interactive - clean up sandbox state
        // Send Ctrl+C to interrupt the command and return to prompt
        write(bash_sandbox.master_fd, "\003", 1);  // Ctrl+C
        
        // Wait a bit for the interrupt to take effect
        usleep(100000);  // 100ms
        
        // Clear any remaining output
        FD_ZERO(&readfds);
        FD_SET(bash_sandbox.master_fd, &readfds);
        struct timeval cleanup_timeout;
        cleanup_timeout.tv_sec = 0;
        cleanup_timeout.tv_usec = 50000;  // 50ms
        
        char cleanup_buffer[1024];
        if (select(bash_sandbox.master_fd + 1, &readfds, NULL, NULL, &cleanup_timeout) > 0) {
            read(bash_sandbox.master_fd, cleanup_buffer, sizeof(cleanup_buffer) - 1);
        }
        
        // Send special response indicating interactive command
        strcpy(stdout_buf, "INTERACTIVE_COMMAND");
        *exit_code = -103;  // Negative prime number for interactive commands (fits in 8-bit)
        return 0;
    }
    
    // Check for error indicators (invalid bash commands that need AI help)
    if (strstr(stdout_buf, "command not found") || 
        strstr(stdout_buf, "Permission denied") ||
        strstr(stdout_buf, "No such file or directory") ||
        strstr(stdout_buf, "bash:") ||
        strstr(stdout_buf, "sh:") ||
        strstr(stdout_buf, "error:") ||
        strstr(stdout_buf, "Error:")) {
        
        // Only route to AI if command has 3+ words (natural language queries)
        int word_count = 0;
        char cmd_copy_for_token[MAX_CMD_LEN];
        strncpy(cmd_copy_for_token, cmd, sizeof(cmd_copy_for_token) - 1);
        cmd_copy_for_token[sizeof(cmd_copy_for_token) - 1] = '\0';
        char* word = strtok(cmd_copy_for_token, " \t");
        while (word && word_count < 10) { // Limit word count to prevent buffer overflow
            word_count++;
            word = strtok(NULL, " \t");
        }
        
        if (word_count >= 3) {
            *exit_code = -113;  // Invalid bash command with 3+ words - route to AI
        } else {
            *exit_code = -109;  // Command not found or error (1-2 words) - show error
        }
        return 0;
    }
    
    // For PTY, we can't easily separate stdout/stderr, so put everything in stdout
    // Look for the explicit EXIT_CODE we echoed
    char* exit_code_line = strstr(stdout_buf, "EXIT_CODE:");
    if (exit_code_line) {
        int actual_exit_code = atoi(exit_code_line + 10);
        *exit_code = actual_exit_code;
        
        // Remove the EXIT_CODE line from output for cleaner display
        // Find the start of the EXIT_CODE line (go back to beginning of line)
        char* line_start = exit_code_line;
        while (line_start > stdout_buf && *(line_start - 1) != '\n') {
            line_start--;
        }
        
        // Find the end of the EXIT_CODE line
        char* line_end = strchr(exit_code_line, '\n');
        if (line_end) {
            line_end++;  // Include the newline
        } else {
            line_end = exit_code_line + strlen(exit_code_line);
        }
        
        // Remove the entire EXIT_CODE line
        size_t line_len = line_end - line_start;
        memmove(line_start, line_end, strlen(line_end) + 1);
        
        // Update total_len
        total_len -= line_len;
    } else {
        *exit_code = 0;    // Success (no explicit exit code found)
    }
    
    return 0;  // Success
}

// Send request to middleware
int send_to_middleware(const char* request, char* response, size_t response_size) {
    // Connect to middleware socket
    int middleware_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (middleware_fd < 0) {
        return -1;
    }
    
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    
    // Use the same socket path as the security agent
    const char* home = getenv("HOME");
    if (!home) {
        close(middleware_fd);
        return -1;
    }
    
    char middleware_socket_path[512];
    snprintf(middleware_socket_path, sizeof(middleware_socket_path), "%s/.awesh_security_agent.sock", home);
    strncpy(addr.sun_path, middleware_socket_path, sizeof(addr.sun_path) - 1);
    
    if (connect(middleware_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(middleware_fd);
        return -1;
    }
    
    // Send request
    if (send(middleware_fd, request, strlen(request), 0) < 0) {
        close(middleware_fd);
        return -1;
    }
    
    // Read response with timeout
    fd_set readfds;
    struct timeval timeout;
    
    FD_ZERO(&readfds);
    FD_SET(middleware_fd, &readfds);
    timeout.tv_sec = 5;
    timeout.tv_usec = 0;
    
    int result = select(middleware_fd + 1, &readfds, NULL, NULL, &timeout);
    
    if (result > 0) {
        ssize_t bytes_received = recv(middleware_fd, response, response_size - 1, 0);
        close(middleware_fd);
        if (bytes_received > 0) {
            response[bytes_received] = '\0';
            return 0;
        }
    }
    
    close(middleware_fd);
    return -1;
}

// Send command execution result to frontend
void execute_and_send_to_frontend(const char* command) {
    // Execute command and capture output
    FILE* pipe = popen(command, "r");
    if (pipe) {
        char buffer[1024];
        char output[4096] = {0};
        while (fgets(buffer, sizeof(buffer), pipe)) {
            strncat(output, buffer, sizeof(output) - strlen(output) - 1);
        }
        int exit_code = pclose(pipe);
        
        // Send result to frontend via mmap
        write_result_to_mmap(exit_code, output, "");
    } else {
        write_result_to_mmap(-1, "", "Failed to execute command");
    }
}

// Send AI response to frontend
void send_ai_response_to_frontend(const char* ai_output) {
    write_result_to_mmap(0, ai_output, "");
}

// Send error to frontend
void send_error_to_frontend(const char* error) {
    write_result_to_mmap(-1, "", error);
}

void handle_client_request(int client_fd) {
    char cmd[MAX_CMD_LEN];
    char stdout_buf[MAX_RESPONSE_LEN];
    char stderr_buf[MAX_RESPONSE_LEN];
    int exit_code;
    
    // Read command from client (frontend)
    ssize_t bytes_received = recv(client_fd, cmd, sizeof(cmd) - 1, 0);
    if (bytes_received <= 0) {
        return;
    }
    cmd[bytes_received] = '\0';
    
    // Execute command in sandbox for validation
    if (execute_command_in_sandbox(cmd, stdout_buf, stderr_buf, &exit_code) == 0) {
        // Write result to mmap file for frontend to read
        write_result_to_mmap(exit_code, stdout_buf, stderr_buf);
        
        // Send simple acknowledgment to client
        char ack[] = "OK";
        send(client_fd, ack, strlen(ack), 0);
    } else {
        // Write error result to mmap file
        write_result_to_mmap(-1, "", "Sandbox execution failed");
        
        // Send simple acknowledgment to client
        char ack[] = "ERROR";
        send(client_fd, ack, strlen(ack), 0);
    }
}

int main() {
    // Setup socket path
    const char* home = getenv("HOME");
    if (!home) {
        fprintf(stderr, "Error: HOME environment variable not set\n");
        return 1;
    }
    
    snprintf(socket_path, sizeof(socket_path), "%s/.awesh_sandbox.sock", home);
    
    // Remove existing socket
    unlink(socket_path);
    
    // Create socket
    int server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("Failed to create socket");
        return 1;
    }
    
    // Bind socket
    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);
    
    if (bind(server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("Failed to bind socket");
        close(server_fd);
        return 1;
    }
    
    // Listen for connections
    if (listen(server_fd, 5) < 0) {
        perror("Failed to listen on socket");
        close(server_fd);
        return 1;
    }
    
    // Setup mmap file for output communication
    if (setup_mmap_file() != 0) {
        fprintf(stderr, "Failed to setup mmap file\n");
        close(server_fd);
        return 1;
    }
    
    // Spawn bash sandbox
    if (spawn_bash_sandbox() != 0) {
        fprintf(stderr, "Failed to spawn bash sandbox\n");
        cleanup_mmap_file();
        close(server_fd);
        return 1;
    }
    
    // Main server loop
    while (1) {
        int client_fd = accept(server_fd, NULL, NULL);
        if (client_fd < 0) {
            perror("Failed to accept connection");
            continue;
        }
        
        handle_client_request(client_fd);
        close(client_fd);
    }
    
    // Cleanup
    cleanup_bash_sandbox();
    cleanup_sandbox_filesystem();
    cleanup_mmap_file();
    close(server_fd);
    unlink(socket_path);
    
    return 0;
}
