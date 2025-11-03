# awesh Architecture - Agent-Based System

## Overview

awesh uses an agent-based architecture where all operations flow through specialized agents. The system is designed with a coordinator pattern where the **Response Agent** routes AI responses to appropriate specialized agents.

## Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    Response Agent                            │
│              (Coordinator & Router)                          │
│                                                              │
│  - Analyzes AI responses                                     │
│  - Routes to specialized agents                              │
│  - Coordinates multi-agent workflows                        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬──────────────┐
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌───────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
│ File Editor   │  │ Execution    │  │ File Agent   │  │ TODO Agent  │
│ Agent         │  │ Agent        │  │              │  │             │
│               │  │              │  │              │  │             │
│ - Edit files  │  │ Routes to    │  │ - File       │  │ - Goal      │
│ - Create files│  │ Shell Agent  │  │   context    │  │   tracking  │
│ - File ops    │  │              │  │ - Detection  │  │ - Iterations│
└───────────────┘  └──────┬────────┘  └──────────────┘  └─────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ Shell Agent  │ ⚡
                  │ (C-based)     │
                  │               │
                  │ - Fast exec   │
                  │ - Validation  │
                  │ - Isolated    │
                  │ - PTY support │
                  └──────────────┘
```

## Complete System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Input                                   │
│                  (Natural Language or Commands)                      │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      C Frontend (awesh.c)                            │
│                                                                      │
│  - Readline interface                                                │
│  - Command detection                                                 │
│  - Route to AI or Bash                                                │
└─────────────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  Direct Bash     │    │   AI Backend      │
    │  (User commands) │    │   (Python)        │
    └──────────────────┘    └─────────┬────────┘
                                       │
                                       ▼
                        ┌──────────────────────────┐
                        │    AI Client            │
                        │    (OpenAI/Ollama/etc)  │
                        └─────────┬───────────────┘
                                  │
                                  ▼
                        ┌──────────────────────────┐
                        │    AI Response          │
                        └─────────┬───────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Response Agent                                   │
│                    (Process & Route)                                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ File Edit    │        │ awesh: cmd    │        │ Code Blocks  │
│ Blocks       │        │ detected      │        │ detected     │
└──────┬───────┘        └──────┬────────┘        └──────┬───────┘
       │                       │                         │
       ▼                       ▼                         ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│ File Editor  │        │ Execution    │        │ File Editor  │
│ Agent        │        │ Agent        │        │ Agent        │
└──────────────┘        └──────┬───────┘        └──────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ Shell Agent  │ ⚡
                        │ (C-based)    │
                        │ awesh_sandbox │
                        └──────┬───────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ Command      │
                        │ Execution    │
                        │ (Isolated)   │
                        └──────┬───────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ Results      │
                        │ Returned     │
                        └──────────────┘
```

## Agent Responsibilities

### Response Agent (Coordinator)
- **Location**: `awesh_backend/response_agent.py`
- **Role**: Analyzes AI responses and routes to specialized agents
- **Handles**:
  - Detecting file edit blocks (` ```edit:filename ``` `)
  - Detecting executable commands (`awesh: command`)
  - Detecting code blocks that should be files
  - Cleaning thinking process from responses
  - Coordinating multi-agent workflows

### File Editor Agent
- **Location**: `awesh_backend/file_editor.py`
- **Role**: Handles all file creation and editing operations
- **Handles**:
  - Parsing edit blocks from AI responses
  - Creating new files
  - Editing existing files with surgical precision
  - Creating backups
  - Handling code blocks that should be written to files

### Execution Agent
- **Location**: `awesh_backend/execution_agent.py`
- **Role**: Routes commands to Shell Agent for execution
- **Handles**:
  - Command routing to Shell Agent
  - Execution history tracking
  - Result formatting
  - AI iteration feedback loops

### Shell Agent (C-based)
- **Location**: `awesh_sandbox.c` (C implementation)
- **Role**: Fast command validation and execution
- **Why C**: Performance - provides quick response on shell commands
- **Handles**:
  - Command validation
  - Isolated execution environment
  - PTY support for interactive commands
  - Fast command execution
  - Result capture (stdout, stderr, exit codes)

### File Agent
- **Location**: `awesh_backend/file_agent.py`
- **Role**: File context injection for AI prompts
- **Handles**:
  - Detecting file references in user prompts
  - Extracting file content for context
  - Injecting file context into AI prompts
  - Fuzzy file matching

### TODO Agent
- **Location**: `awesh_backend/todo_agent.py`
- **Role**: Goal tracking and iterative workflows
- **Handles**:
  - Creating goals with subtasks
  - Tracking progress across iterations
  - Managing AI feedback loops (up to 10 iterations)
  - Goal completion detection

## Command Flow Examples

### Example 1: AI Suggests a Command

```
User: "check disk usage"
    ↓
AI Response: "awesh: df -h"
    ↓
Response Agent detects "awesh:" command
    ↓
Execution Agent receives command
    ↓
Shell Agent (C) validates and executes
    ↓
Results returned to user
```

### Example 2: AI Creates a File

```
User: "create a backup script"
    ↓
AI Response: "```edit:backup.sh\n<<<<<<< OLD\n=======\n#!/bin/sh\n...\n>>>>>>> NEW\n```"
    ↓
Response Agent detects file edit block
    ↓
File Editor Agent parses and creates file
    ↓
File created with backup
    ↓
Success message returned to user
```

### Example 3: AI Provides Information Only

```
User: "what is Kubernetes?"
    ↓
AI Response: "Kubernetes is a container orchestration platform..."
    ↓
Response Agent analyzes - no commands or files detected
    ↓
Response displayed as-is to user
```

## Key Design Principles

1. **All commands go through Shell Agent**: Every AI-suggested command must be validated and executed in the Shell Agent (C-based) before returning results.

2. **Agent coordination**: Response Agent coordinates all agents, ensuring proper routing and workflow.

3. **Performance**: Shell Agent is C-based for speed, critical for quick command validation and execution.

4. **Safety**: All commands are executed in isolated sandbox environment before user sees results.

5. **Separation of concerns**: Each agent has a clear, single responsibility.

6. **Backward compatibility**: Old execution paths are maintained but route through agents where possible.

## File Locations

- **Response Agent**: `awesh_backend/response_agent.py`
- **File Editor**: `awesh_backend/file_editor.py`
- **Execution Agent**: `awesh_backend/execution_agent.py`
- **Shell Agent (C)**: `awesh_sandbox.c`
- **File Agent**: `awesh_backend/file_agent.py`
- **TODO Agent**: `awesh_backend/todo_agent.py`
- **Server (main)**: `awesh_backend/server.py`
- **C Frontend**: `awesh.c`

## Agent Communication

```
Response Agent
    │
    ├─→ File Editor Agent (synchronous, direct calls)
    │
    ├─→ Execution Agent (async, await)
    │   └─→ Shell Agent (C, via Unix socket ~/.awesh_sandbox.sock)
    │
    ├─→ File Agent (already used in prompt processing)
    │
    └─→ TODO Agent (for iterative workflows)
```

## Notes

- **Shell Agent is specialized**: It's implemented in C (`awesh_sandbox.c`) for performance, not Python, making it a specialized agent optimized for speed.

- **User commands bypass agents**: Direct user commands (detected as shell syntax) execute immediately in Bash without going through agents.

- **AI commands use agents**: All AI-suggested commands go through the full agent chain: Response Agent → Execution Agent → Shell Agent.

- **File operations centralized**: All file creation/editing goes through File Editor Agent, ensuring consistency and backup creation.

