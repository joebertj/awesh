# awesh Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                awesh System Architecture                        │
│                          "AI by default, Bash when I mean Bash"                │
│                             4-Component Architecture                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Input    │    │  C Frontend     │    │ Security Agent  │    │ Python Backend  │
│                 │    │   (awesh.c)     │    │ (awesh_sec)     │    │ (awesh_backend) │
│ • Natural Lang  │───▶│                 │───▶│                 │───▶│                 │
│ • Shell Commands│    │ • Readline UI   │    │ • Middleware    │    │ • AI Processing │
│ • Mixed Input   │    │ • Command Route │    │ • Security Gate │    │ • MCP Tools     │
└─────────────────┘    │ • Socket Client │    │ • RAG Analysis  │    │ • File Agent    │
                       │ • PTY Support   │    │ • Socket Server │    │ • Socket Server │
                       └─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │                        │
                                │                        │                        │
                                ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Bash Sandbox    │    │  Unix Sockets   │    │   AI Provider   │    │  Config Files   │
│ (awesh_sandbox) │    │                 │    │                 │    │                 │
│                 │    │ • ~/.awesh_sandbox.sock│ • OpenAI API    │    │ • ~/.aweshrc    │
│ • Bash Validation│    │ • ~/.awesh_security_agent.sock│ • OpenRouter    │    │ • ~/.awesh_config.ini│
│ • Syntax Check  │    │ • ~/.awesh.sock │    │ • GPT-4/5       │    │ • Verbose Control│
│ • Return Codes  │    │ • Status Sync   │    │ • Streaming     │    │ • AI Settings   │
│ • No Execution  │    │ • Command Flow  │    │ • Tool Calling  │    │ • Security Rules│
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Component Details

### 1. C Frontend (awesh.c)
```
┌─────────────────────────────────────────────────────────────────┐
│                        C Frontend (awesh.c)                    │
├─────────────────────────────────────────────────────────────────┤
│ • Interactive Shell with Readline Support                      │
│ • Smart Command Routing (Sandbox → AI → Direct)                │
│ • Built-in Commands: cd, pwd, exit, quit                       │
│ • Socket Communication with Backend & Sandbox                  │
│ • Security Agent Integration                                   │
│ • Dynamic Prompt Generation (0ms)                              │
│ • Process Health Monitoring & Auto-restart                     │
│ • PTY Support for Interactive Commands                         │
│ • Independent Operation (works as regular bash)                │
└─────────────────────────────────────────────────────────────────┘

Key Functions:
├── Command Routing Logic
│   ├── is_awesh_command() - Control commands (aweh, awes, awev, awea)
│   ├── is_builtin() - Built-in shell commands
│   ├── test_command_in_sandbox() - Sandbox command testing
│   ├── is_interactive_command() - Interactive command detection
│   └── execute_command_securely() - Main command execution
│
├── Communication
│   ├── send_to_backend() - Backend socket communication
│   ├── send_to_sandbox() - Sandbox socket communication
│   ├── send_to_security_agent() - Security agent communication
│   └── init_frontend_socket() - Frontend socket server
│
├── Process Management
│   ├── restart_backend() - Backend process restart
│   ├── restart_security_agent() - Security agent restart
│   ├── restart_sandbox() - Sandbox process restart
│   └── attempt_child_restart() - Auto-restart failed processes
│
└── Security Integration
    ├── get_security_agent_status() - Threat status
    ├── get_health_status_emojis() - Process health (🧠:🔒:🏖️)
    └── Config file reading (~/.aweshrc)
```

### 2. Python Backend (awesh_backend)
```
┌─────────────────────────────────────────────────────────────────┐
│                    Python Backend (awesh_backend)              │
├─────────────────────────────────────────────────────────────────┤
│ • Socket Server (Unix Domain Sockets)                          │
│ • AI Client Integration (OpenAI/OpenRouter)                    │
│ • MCP (Model Context Protocol) Tool Execution                  │
│ • File Agent for File Operations                               │
│ • RAG (Retrieval Augmented Generation) System                  │
│ • Security Integration                                         │
└─────────────────────────────────────────────────────────────────┘

Components:
├── AweshSocketBackend (server.py)
│   ├── Socket Server (~/.awesh.sock)
│   ├── Command Processing
│   ├── AI Client Management
│   └── File Agent Integration
│
├── AweshAIClient (ai_client.py)
│   ├── OpenAI/OpenRouter Integration
│   ├── Streaming Responses
│   ├── System Prompt Management
│   └── Tool Function Calling
│
└── FileAgent (file_agent.py)
    ├── File Reading Operations
    ├── Content Filtering
    └── AI-Enhanced File Analysis
```

### 3. Security Agent (awesh_sec)
```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Agent (awesh_sec)                  │
├─────────────────────────────────────────────────────────────────┤
│ • Process Monitoring (Every 5 seconds)                         │
│ • AI-Powered Threat Detection (Every 5 minutes)                │
│ • Pattern-Based Security Filtering                             │
│ • Config File Reading (~/.aweshrc)                             │
│ • RAG Data Collection & Analysis                               │
│ • Isolated Operation (no socket server)                        │
└─────────────────────────────────────────────────────────────────┘

Security Features:
├── Process Scanning
│   ├── Backend API calls for process data
│   ├── RAG Data Collection (Every 5s)
│   └── AI Analysis (Every 5min)
│
├── Pattern Detection
│   ├── Dangerous Commands (rm -rf /, dd, mkfs, etc.)
│   ├── Sensitive Data (passwords, keys, tokens)
│   └── Regex-based Filtering
│
└── Communication
    ├── Backend Socket Connection (security analysis only)
    ├── Config File Reading (verbose control)
    └── Threat Alert Propagation
```

### 4. Bash Sandbox (awesh_sandbox)
```
┌─────────────────────────────────────────────────────────────────┐
│                    Bash Sandbox (awesh_sandbox)                │
├─────────────────────────────────────────────────────────────────┤
│ • PTY-based Bash Environment                                   │
│ • Command Testing & Execution                                  │
│ • Interactive Command Detection                                │
│ • Socket Communication with Frontend                           │
│ • Automatic Cleanup on Interactive Commands                    │
└─────────────────────────────────────────────────────────────────┘

Sandbox Features:
├── Command Execution
│   ├── PTY Support for proper TTY
│   ├── 2-second timeout for command testing
│   ├── Bash prompt detection
│   └── Interactive command cleanup (Ctrl+C)
│
├── Communication
│   ├── Unix Domain Socket (~/.awesh_sandbox.sock)
│   ├── Command/Response Protocol
│   └── INTERACTIVE_COMMAND detection
│
└── Process Management
    ├── Persistent bash process
    ├── Automatic cleanup on exit
    └── Error handling and recovery
```

## Data Flow

### 1. Command Processing Flow (4-Component Architecture)
```
User Input → C Frontend → Command Routing Decision
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            Built-in Commands   Sandbox Test    AI Processing
                    │               │               │
                    │               ▼               │
                    │        Valid Bash?            │
                    │               │               │
                    │        ┌──────┼──────┐       │
                    │        │      │      │       │
                    │        ▼      ▼      ▼       │
                    │   Direct     AI    Middleware│
                    │ Execution    Route  Route    │
                    │        │      │      │       │
                    │        │      │      ▼       │
                    │        │      │   Security   │
                    │        │      │   Analysis   │
                    │        │      │      │       │
                    │        │      │      ▼       │
                    │        │      │  Backend     │
                    │        │      │  AI Query    │
                    │        │      │      │       │
                    │        │      │      ▼       │
                    │        │      │  Results     │
                    │        │      │ Display      │
                    │        │      │      │       │
                    └────────┼──────┼──────┼───────┘
                             │      │      │
                             ▼      ▼      ▼
                        User Output
```

### 2. AI Response Modes (vi-inspired)
```
AI Response → Mode Detection
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
  Normal Mode   Command Mode   Display Mode
  (default)     awesh: cmd    (text only)
        │           │           │
        │           ▼           │
        │    Security Check     │
        │           │           │
        │           ▼           │
        │    Command Execute    │
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
              User Output
```

### 2. Security Monitoring Flow
```
Security Agent → Process Scanning (5s) → RAG Data Collection
                                        │
                                        ▼
                               Backend RAG Storage
                                        │
                                        ▼
                               AI Analysis (5min) → Threat Detection
                                        │
                                        ▼
                               Shared Memory Update
                                        │
                                        ▼
                               Frontend Status Display
```

## Communication Protocols

### 1. Frontend ↔ Backend (Unix Sockets)
```
Protocol: ~/.awesh.sock (Unix Domain Socket)

Commands:
├── STATUS - AI readiness check
├── CWD:<path> - Working directory sync
├── QUERY:<prompt> - AI query
├── BASH_FAILED:<code>:<cmd>:<file> - Bash failure context
├── VERBOSE:<level> - Verbose level update
├── AI_PROVIDER:<provider> - Provider switch
└── GET_PROCESS_DATA - Process data for security agent

Responses:
├── AI_READY / AI_LOADING - Status response
├── OK - Acknowledgment
└── <AI Response> - Streaming AI output
```

### 2. Frontend ↔ Sandbox (Unix Sockets)
```
Protocol: ~/.awesh_sandbox.sock (Unix Domain Socket)

Commands:
├── <command> - Any shell command to validate

Responses:
├── EXIT_CODE:0\nSTDOUT_LEN:Y\nSTDOUT:...\nSTDERR_LEN:Z\nSTDERR:...\n - Valid bash
└── EXIT_CODE:-2\nSTDOUT_LEN:0\nSTDOUT:\nSTDERR_LEN:0\nSTDERR:\n - Invalid bash (AI query)
```

### 3. Backend ↔ Security Agent
```
Protocol: ~/.awesh.sock (Same socket, different messages)

Security Messages:
├── GET_PROCESS_DATA - Request process data from backend
├── RAG_ADD_PROCESS:<data> - Process data for RAG
├── PROCESS_ANALYSIS:ANALYZE_RAG_5MIN - AI analysis request
└── RAG_CLEAR_PROCESS_DATA - Clear RAG data after analysis

Responses:
├── <process_data> - Process information from ps command
├── <AI Analysis Result> - Threat analysis
└── OK - Acknowledgment
```

### 4. Security Agent ↔ Frontend
```
Protocol: Config File (~/.aweshrc)

Status Updates:
├── VERBOSE=<level> - Verbose level control
├── AI_PROVIDER=<provider> - AI provider setting
└── Other configuration settings

Note: Security agent reads config file directly, no socket communication
```

## Configuration

### 1. Frontend Configuration (~/.aweshrc)
```
VERBOSE=0                    # 0=silent, 1=info, 2=debug
AI_PROVIDER=openai          # openai or openrouter
MODEL=gpt-5                 # AI model to use
OPENAI_API_KEY=sk-...       # API key
OPENROUTER_API_KEY=sk-...   # OpenRouter key
```

### 2. System Prompts
```
~/.awesh_system.txt         # Custom AI behavior
Default: Operations-focused prompt for infrastructure management
```

## Key Features

### 1. Smart Command Routing
- **Sandbox Validation**: All commands validated in sandbox first (bash syntax check)
- **Direct Execution**: Valid bash commands executed directly by frontend
- **AI Routing**: Invalid bash commands routed to backend via middleware
- **Built-in Commands**: aweh, awes, awev, awea, awem (handled by frontend)
- **Synchronous Communication**: Frontend waits for backend responses with 5-minute timeout

### 2. Security Integration
- **Real-time Monitoring**: Process scanning every 5 seconds
- **AI Threat Detection**: Analysis every 5 minutes
- **Pattern Filtering**: Dangerous commands and sensitive data
- **Visual Indicators**: Emoji-based status in prompt (🧠:🔒:🏖️)
- **Isolated Security**: Security agent reads config, no socket server

### 3. Performance Optimizations
- **Instant Prompt**: 0ms prompt generation (no blocking calls)
- **Non-blocking**: All children start in background
- **Streaming**: Real-time AI responses
- **Health Monitoring**: Automatic process restart
- **Independent Operation**: Works as regular bash when needed

### 4. PTY Support
- **Interactive Commands**: vi, top, ssh, python, etc. work properly
- **TTY Detection**: Sandbox detects interactive commands automatically
- **Clean State**: Sandbox cleaned up after interactive detection
- **Direct Execution**: Interactive commands run in frontend with proper TTY

### 5. MCP Integration
- **Tool Execution**: Secure tool calling through MCP
- **File Operations**: FileAgent for file reading/analysis
- **Safety**: No direct shell execution from AI
- **Audit**: Configurable logging and monitoring

## Installation & Usage

### Quick Start
```bash
cd awesh/
./install.sh
export OPENAI_API_KEY=your_key
awesh
```

### Example Session
```bash
🧠:🔒:🏖️:joebert@maximaal:~:☸️default:🌿main
> ls -la                              # → Sandbox validation → Direct execution
> vi file.txt                         # → Sandbox validation → Direct execution
> what files are here?                # → Sandbox validation → AI query via middleware
> find . -name "*.py"                 # → Sandbox validation → Direct execution  
> top                                 # → Sandbox validation → Direct execution
> explain this error                  # → Sandbox validation → AI query via middleware
> cat file.txt | grep error           # → Sandbox validation → Direct execution
> summarize this directory structure  # → Sandbox validation → AI query via middleware
> awev off                            # → Built-in command (verbose off)
> awem gpt-4                          # → Built-in command (set model)
> exit                                # → Built-in command (clean exit)
```

### Status Emojis
- **🧠** = Backend ready (AI available)
- **⏳** = Backend loading/not ready
- **💀** = Backend failed
- **🔒** = Security agent ready
- **⏳** = Security agent not ready
- **🏖️** = Sandbox ready
- **⏳** = Sandbox not ready

This architecture provides a robust, secure, and intelligent shell environment that seamlessly blends traditional command-line operations with AI assistance while maintaining the performance and security requirements of operations professionals.
