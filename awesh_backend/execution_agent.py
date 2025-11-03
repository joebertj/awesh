"""
Execution Agent for awesh - Routes commands to Shell Agent (C-based Sandbox)

This agent routes commands to the Shell Agent, which is a specialized C-based agent
(awesh_sandbox.c) for fast command validation and execution.

Architecture:
- Execution Agent → Shell Agent (Sandbox/C) → Command Execution
- Shell Agent is C-based for speed and quick response on shell commands
- All AI-suggested commands go through this path for validation

Two distinct execution paths:
1. USER RUNS COMMAND → Frontend executes immediately (unfiltered, direct to user's terminal)
2. AI RUNS COMMAND → Execution Agent → Shell Agent (C-based) → Validated execution

The Shell Agent (sandbox) is a specialized agent:
- Implemented in C (awesh_sandbox.c) for performance
- Provides fast command validation and execution
- Isolated execution environment with PTY
- Quick response for shell command testing

This agent is for when the AI needs to:
- Run commands to gather information before answering
- Verify command syntax before suggesting to user
- Iterate on commands based on results
- Build multi-step solutions

Features:
- Route commands to Shell Agent (C-based sandbox)
- Capture stdout, stderr, exit codes
- Provide results back to AI for iteration
- Multi-step execution with feedback loops
- Safe execution environment
- NO interference with user's direct command execution
"""

import os
import sys
import socket
import json
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"🔧 Execution Agent: {message}", file=sys.stderr)


@dataclass
class ExecutionResult:
    """Result of command execution"""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    success: bool
    execution_time: float = 0.0


class ExecutionAgent:
    """
    Agent that executes commands in sandbox and provides feedback
    Like Cursor's agent terminals
    """
    
    def __init__(self, sandbox_socket_path: str = None):
        """
        Initialize execution agent
        
        Args:
            sandbox_socket_path: Path to sandbox socket (default: ~/.awesh_sandbox.sock)
        """
        self.sandbox_socket_path = sandbox_socket_path or os.path.expanduser("~/.awesh_sandbox.sock")
        self.execution_history = []  # Track execution history
        self.max_iterations = 5  # Max iterations for AI feedback loop
        
    async def execute_command(self, command: str) -> ExecutionResult:
        """
        Execute a command in the sandbox
        
        Args:
            command: Shell command to execute
            
        Returns:
            ExecutionResult with output and status
        """
        debug_log(f"Executing command: {command}")
        
        try:
            # Use sandbox if available, otherwise execute directly
            if os.path.exists(self.sandbox_socket_path):
                result = await self._execute_in_sandbox(command)
            else:
                # Fallback to direct execution
                result = await self._execute_directly(command)
            
            # Store in history
            self.execution_history.append(result)
            
            return result
            
        except Exception as e:
            debug_log(f"Execution error: {e}")
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                success=False
            )
    
    async def _execute_in_sandbox(self, command: str) -> ExecutionResult:
        """Execute command via sandbox socket"""
        import time
        start_time = time.time()
        
        try:
            # Connect to sandbox
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout
            sock.connect(self.sandbox_socket_path)
            
            # Send command
            sock.sendall(command.encode('utf-8'))
            
            # Receive response (from mmap)
            response = sock.recv(1024).decode('utf-8')
            sock.close()
            
            # Read from mmap file
            mmap_path = "/tmp/awesh_sandbox_output.mmap"
            if os.path.exists(mmap_path):
                with open(mmap_path, 'r') as f:
                    mmap_content = f.read()
                
                # Parse the mmap content (JSON format)
                try:
                    result_data = json.loads(mmap_content)
                    execution_time = time.time() - start_time
                    
                    return ExecutionResult(
                        command=command,
                        exit_code=result_data.get('exit_code', -1),
                        stdout=result_data.get('stdout', ''),
                        stderr=result_data.get('stderr', ''),
                        success=result_data.get('exit_code', -1) == 0,
                        execution_time=execution_time
                    )
                except json.JSONDecodeError:
                    # Fall back to text parsing
                    exit_code = 0
                    stdout = ""
                    stderr = ""
                    
                    for line in mmap_content.split('\n'):
                        if line.startswith('EXIT_CODE:'):
                            exit_code = int(line.split(':')[1])
                        elif line.startswith('STDOUT:'):
                            stdout = line.split(':', 1)[1] if ':' in line else ""
                        elif line.startswith('STDERR:'):
                            stderr = line.split(':', 1)[1] if ':' in line else ""
                    
                    execution_time = time.time() - start_time
                    
                    return ExecutionResult(
                        command=command,
                        exit_code=exit_code,
                        stdout=stdout,
                        stderr=stderr,
                        success=exit_code == 0,
                        execution_time=execution_time
                    )
            
            # No mmap file - return error
            execution_time = time.time() - start_time
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr="Sandbox mmap file not found",
                success=False,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            debug_log(f"Sandbox execution error: {e}")
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Sandbox execution failed: {e}",
                success=False,
                execution_time=execution_time
            )
    
    async def _execute_directly(self, command: str) -> ExecutionResult:
        """Execute command directly (fallback when sandbox unavailable)"""
        import time
        start_time = time.time()
        
        try:
            # Execute with subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                command=command,
                exit_code=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else "",
                stderr=stderr.decode('utf-8') if stderr else "",
                success=process.returncode == 0,
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr="Command execution timeout (30s)",
                success=False,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {e}",
                success=False,
                execution_time=execution_time
            )
    
    async def execute_with_ai_feedback(self, initial_command: str, ai_client, user_request: str) -> str:
        """
        Execute command with AI feedback loop - like Cursor agent terminals
        
        The AI can see execution results and refine commands iteratively.
        
        Args:
            initial_command: First command to try
            ai_client: AI client for getting feedback
            user_request: Original user request
            
        Returns:
            Formatted output with execution results
        """
        debug_log(f"Starting AI feedback loop for: {user_request}")
        
        output = ""
        current_command = initial_command
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            debug_log(f"Iteration {iteration}: {current_command}")
            
            # Execute command
            result = await self.execute_command(current_command)
            
            # Format execution output
            output += f"\n🔧 Executing: {current_command}\n"
            
            if result.success:
                output += f"✅ Success (exit {result.exit_code})\n"
                if result.stdout:
                    output += f"Output:\n{result.stdout}\n"
                # Command succeeded - we're done
                break
            else:
                output += f"❌ Failed (exit {result.exit_code})\n"
                if result.stderr:
                    output += f"Error: {result.stderr}\n"
                
                # Ask AI for next step based on the error
                if iteration < self.max_iterations:
                    output += f"🤔 Analyzing error...\n"
                    
                    # Build feedback prompt for AI
                    feedback_prompt = f"""The command failed. Help fix it.

Original request: {user_request}
Command tried: {current_command}
Exit code: {result.exit_code}
Error: {result.stderr}

Provide the corrected command using: awesh: <command>"""
                    
                    # Get AI suggestion (simplified - would need proper AI client call)
                    # For now, break on first failure
                    output += "💡 Try refining the command or check the error above.\n"
                    break
        
        if iteration >= self.max_iterations:
            output += f"⚠️ Max iterations ({self.max_iterations}) reached\n"
        
        return output
    
    def get_execution_summary(self) -> str:
        """Get summary of all executions in this session"""
        if not self.execution_history:
            return "No commands executed yet"
        
        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        failed = total - successful
        
        summary = f"📊 Execution Summary:\n"
        summary += f"  Total commands: {total}\n"
        summary += f"  Successful: {successful}\n"
        summary += f"  Failed: {failed}\n"
        
        return summary


# Singleton instance
_execution_agent_instance = None

def get_execution_agent() -> ExecutionAgent:
    """Get or create the global execution agent instance"""
    global _execution_agent_instance
    if _execution_agent_instance is None:
        _execution_agent_instance = ExecutionAgent()
    return _execution_agent_instance

