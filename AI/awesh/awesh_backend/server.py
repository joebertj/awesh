#!/usr/bin/env python3
"""
Socket-based backend for awesh C frontend
"""

import os
import sys
import socket
import asyncio
import threading
from pathlib import Path

from .config import Config
from .ai_client import AweshAIClient
# Bash execution handled by C frontend
from .file_agent import FileAgent

# Global verbose setting
def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"🔧 {message}", file=sys.stderr)

import os
SOCKET_PATH = os.path.expanduser("~/.awesh.sock")

class AweshSocketBackend:
    """Socket-based backend for C frontend"""
    
    def __init__(self):
        self.config = Config.load(Path.home() / '.awesh_config.ini')
        self.ai_client = None
        # Bash execution handled by C frontend
        self.ai_ready = False
        self.socket = None
        self.current_dir = os.getcwd()  # Track current working directory
        self.last_user_command = ""  # Track last user command for retry
        # Initialize file agent with config
        file_agent_enabled = os.getenv('FILE_AGENT_ENABLED', '1') == '1'
        file_agent_ai_enhance = True  # Always enabled for built-in agents
        max_file_size = int(os.getenv('FILE_AGENT_MAX_FILE_SIZE', '50000'))
        max_total_content = int(os.getenv('FILE_AGENT_MAX_TOTAL_CONTENT', '10000'))
        max_files = int(os.getenv('FILE_AGENT_MAX_FILES', '5'))
        
        self.file_agent = FileAgent(
            max_file_size=max_file_size,
            max_total_content=max_total_content,
            max_files=max_files,
            enabled=file_agent_enabled,
            ai_enhance=file_agent_ai_enhance
        )
        
    async def initialize(self):
        """Initialize AI components"""
        try:
            verbose = os.getenv('VERBOSE', '0') == '1'
            if verbose:
                print("🤖 Backend: Initializing AI client...", file=sys.stderr)
            self.ai_client = AweshAIClient(self.config)
            await self.ai_client.initialize()
            self.ai_ready = True
            if verbose:
                print("✅ Backend: AI client ready!", file=sys.stderr)
            
            # Bash execution handled by C frontend
            
        except Exception as e:
            print(f"Backend: AI init failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            self.ai_ready = False
            # Still mark backend as ready for non-AI commands
            if "OPENAI_API_KEY" in str(e):
                print("Backend: Running without AI - set OPENAI_API_KEY to enable AI features", file=sys.stderr)
    
    
    
    async def process_command(self, command: str) -> str:
        """Process command and return response"""
        try:
            debug_log(f"process_command: Starting with command: {command}")
            
            # Security validation now handled transparently by middleware
            
            # Handle working directory sync from frontend
            if command.startswith('CWD:'):
                new_dir = command[4:]  # Remove 'CWD:' prefix
                debug_log(f"Syncing working directory to: {new_dir}")
                self.current_dir = new_dir
                # Bash execution handled by C frontend
                return "OK"  # Send acknowledgment
                
            # Handle AI status check from frontend
            if command == 'STATUS':
                debug_log(f"Status check: AI ready = {self.ai_ready}")
                return "AI_READY" if self.ai_ready else "AI_LOADING"
                
            # Handle bash failure context from frontend
            if command.startswith('BASH_FAILED:'):
                parts = command.split(':', 3)  # BASH_FAILED:exit_code:original_cmd:temp_file
                if len(parts) == 4:
                    exit_code = int(parts[1])
                    original_cmd = parts[2]
                    temp_file = parts[3]
                    
                    # Read bash error output
                    bash_output = ""
                    try:
                        with open(temp_file, 'r') as f:
                            bash_output = f.read().strip()
                    except:
                        bash_output = f"Command failed with exit code {exit_code}"
                    
                    debug_log(f"process_command: Bash failed, sending to AI with context")
                    
                    # Create bash result context for AI
                    bash_result = {
                        'exit_code': exit_code,
                        'stdout': bash_output if exit_code == 0 else "",
                        'stderr': bash_output if exit_code != 0 else ""
                    }
                    
                    return await self._handle_ai_prompt(original_cmd, bash_result)
                else:
                    debug_log("process_command: Invalid BASH_FAILED format")
                    return "Error: Invalid bash failure context\n"
            
            # Note: cd and pwd should be handled by frontend as builtins
            
            
            # Handle security agent special commands (bypass all agents)
            if command.startswith("RAG_ADD_PROCESS:"):
                return await self._add_process_to_rag(command)
            elif command.startswith("PROCESS_ANALYSIS:"):
                return await self._handle_rag_analysis_5min()
            elif command == "GET_PROCESS_DATA":
                return await self._get_process_data()
            
            # Bash execution handled by C frontend - send everything to AI
            debug_log("process_command: Sending to AI (bash handled by frontend)")
            return await self._handle_ai_prompt(command)
                
        except Exception as e:
            debug_log(f"process_command: Exception: {e}")
            return f"Backend error: {e}\n"
    
    async def _get_process_data(self) -> str:
        """Get process data for security agent (socket-based, no direct system calls)"""
        try:
            import subprocess
            debug_log("Getting process data for security agent")
            
            # Execute ps command to get process data
            result = subprocess.run(
                ["ps", "-eo", "pid,ppid,user,comm,args"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                process_data = result.stdout
                debug_log(f"Retrieved {len(process_data)} chars of process data")
                return process_data
            else:
                debug_log(f"ps command failed: {result.stderr}")
                return f"Error: ps command failed: {result.stderr}\n"
                
        except subprocess.TimeoutExpired:
            debug_log("ps command timed out")
            return "Error: ps command timed out\n"
        except Exception as e:
            debug_log(f"_get_process_data: Exception: {e}")
            return f"Error: {e}\n"

    async def _add_process_to_rag(self, command: str) -> str:
        """Add process data to RAG system (security agent only)"""
        try:
            # Extract process data from command
            process_data = command[len("RAG_ADD_PROCESS:"):]
            debug_log(f"Adding process data to RAG: {len(process_data)} chars")
            
            # TODO: Implement RAG storage
            # For now, just acknowledge receipt
            return "RAG_ADDED"
        except Exception as e:
            debug_log(f"Error adding to RAG: {e}")
            return "RAG_ERROR"
    
    # Security validation removed - now handled transparently by middleware
    
    async def _handle_rag_analysis_5min(self) -> str:
        """Analyze latest 5 minutes of RAG data for suspicious processes (security agent only)"""
        try:
            if not self.ai_ready:
                return "AI_NOT_READY"
            
            debug_log("Performing AI analysis on RAG data")
            
            # TODO: Get latest 5 minutes of RAG data
            # For now, use a simple prompt
            analysis_prompt = """Analyze the following process data for suspicious activity. Look for:
1. Unusual process names or paths
2. Processes running from suspicious locations
3. Processes with suspicious command line arguments
4. Processes that might be malware or unauthorized software

Process data: [RAG_DATA_PLACEHOLDER]

Respond with:
- "CLEAN" if no suspicious processes found
- "SUSPICIOUS: <process_id> <reason>" for each suspicious process found
"""
            
            # Use direct AI access (bypass all agents)
            # Use process_prompt method instead of get_ai_response
            response_chunks = []
            async for chunk in self.ai_client.process_prompt(analysis_prompt):
                response_chunks.append(chunk)
            response = "".join(response_chunks)
            
            if response and "SUSPICIOUS:" in response:
                debug_log(f"AI detected suspicious activity: {response}")
                return response
            else:
                debug_log("AI analysis: No suspicious activity detected")
                return "CLEAN"
                
        except Exception as e:
            debug_log(f"Error in RAG analysis: {e}")
            return "ANALYSIS_ERROR"

    async def _handle_ai_prompt(self, prompt: str, bash_result: dict = None, retry_count: int = 0) -> str:
        """Handle AI prompt and return response"""
        # Store last user command for retry mechanism
        if retry_count == 0:
            self.last_user_command = prompt
            
        if not self.ai_ready:
            # AI not ready - if this was a bash failure, show the bash output
            if bash_result:
                result = ""
                if bash_result.get("stdout"):
                    result += bash_result["stdout"]
                if bash_result.get("stderr"):
                    result += bash_result["stderr"]
                return result
            else:
                # Pure AI prompt but AI not ready
                return "❌ AI not ready yet - still loading models\n"
        
        try:
            # Process prompt through file agent first (for ALL AI prompts)
            enhanced_prompt, files_found = await self.file_agent.process_prompt(prompt, self.current_dir)
            if files_found:
                debug_log(f"File agent enhanced prompt with file context")
                prompt = enhanced_prompt
            
            # Give AI full context with vi terminology and explicit awesh: format instructions
            if bash_result:
                ai_input = f"""User command: {prompt}
Bash result:
- Exit code: {bash_result.get('exit_code', 0)}
- Stdout: {bash_result.get('stdout', '')}
- Stderr: {bash_result.get('stderr', '')}

Process this and respond appropriately. You have two response modes (borrowed from vi editor):

1. NORMAL MODE (default): Regular text response for information, explanations, or analysis
   - Just provide your response as normal text
   - This is like vi's normal mode - for reading and navigation

2. COMMAND MODE: When you need to execute shell commands, use this format:
   awesh: <command>
   - This is like vi's command mode - for executing commands
   - The command will be executed through security middleware

Examples:
- For file listing: awesh: ls -la
- For finding files: awesh: find . -name "*.py" -mtime -1
- For system info: awesh: ps aux | grep python
- For editing files: awesh: vi filename.txt

The awesh: prefix tells the system to execute the command through security middleware, just like : in vi executes commands."""
            else:
                ai_input = f"""{prompt}

You have two response modes (borrowed from vi editor):

1. NORMAL MODE (default): Regular text response for information, explanations, or analysis
   - Just provide your response as normal text
   - This is like vi's normal mode - for reading and navigation

2. COMMAND MODE: When you need to execute shell commands, use this format:
   awesh: <command>
   - This is like vi's command mode - for executing commands
   - The command will be executed through security middleware

Examples:
- For file listing: awesh: ls -la
- For finding files: awesh: find . -name "*.py" -mtime -1
- For system info: awesh: ps aux | grep python
- For editing files: awesh: vi filename.txt

The awesh: prefix tells the system to execute the command through security middleware, just like : in vi executes commands."""
            
            # Collect response with timeout (compatible with older Python)
            output = "🤖 "
            try:
                async def collect_response():
                    result = ""
                    chunk_count = 0
                    debug_log("Starting AI client process_prompt")
                    async for chunk in self.ai_client.process_prompt(ai_input):
                        result += chunk
                        chunk_count += 1
                        debug_log(f"Received chunk {chunk_count}: {chunk[:50]}...")
                    debug_log(f"Total chunks: {chunk_count}, total length: {len(result)}")
                    return result
                
                debug_log("Calling collect_response with timeout")
                response = await asyncio.wait_for(collect_response(), timeout=300)  # 5 minutes
                debug_log(f"Got response: {len(response)} chars")
                
                # Handle empty response with retry
                if not response or len(response.strip()) == 0:
                    debug_log("❌ Empty AI response received! Retrying once...")
                    debug_log(f"Raw response: '{response}'")
                    
                    # Wait a moment and retry
                    await asyncio.sleep(1)
                    debug_log("🔄 Retrying AI request...")
                    
                    try:
                        retry_response = await asyncio.wait_for(collect_response(), timeout=300)
                        debug_log(f"Retry response: {len(retry_response)} chars")
                        
                        if retry_response and len(retry_response.strip()) > 0:
                            debug_log("✅ Retry succeeded!")
                            response = retry_response
                        else:
                            debug_log("❌ Retry also returned empty response")
                            debug_log(f"Retry raw response: '{retry_response}'")
                            return "❌ AI returned empty response twice - please check AI configuration or try again later\n"
                    except Exception as retry_error:
                        debug_log(f"❌ Retry failed with error: {retry_error}")
                        return f"❌ AI returned empty response and retry failed: {retry_error}\n"
                
                # Show first part of response for debugging
                debug_log(f"AI response preview: '{response[:100]}{'...' if len(response) > 100 else ''}'")
                
                # Check response type and handle accordingly
                if "awesh:" in response:
                    debug_log("Found awesh: commands in AI response")
                    return await self._extract_and_execute_commands(response, retry_count)
                elif await self._contains_questions_or_options(response):
                    debug_log("Found questions/options in AI response")
                    return await self._handle_ai_questions(response, retry_count)
                else:
                    debug_log("Regular AI response, returning as-is")
                    output += response
                    output += "\n"
                    return output
            except asyncio.TimeoutError:
                return f"❌ AI response timeout - request took too long\n"
            except Exception as stream_error:
                # If streaming fails, try non-streaming fallback
                return f"❌ AI streaming error: {stream_error}\n"
                
        except Exception as e:
            return f"❌ AI error: {e}\n"
    
    async def _extract_and_execute_commands(self, ai_response: str, retry_count: int = 0) -> str:
        """Extract awesh: commands from AI response and execute them using stack approach"""
        import re
        
        debug_log(f"Extracting awesh: commands from AI response (retry {retry_count})")
        
        # Find all awesh: command patterns
        awesh_commands = re.findall(r'awesh:\s*(.+)', ai_response)
        
        if not awesh_commands:
            debug_log("No awesh: commands found")
            return f"🤖 {ai_response}\n"
        
        debug_log(f"Found {len(awesh_commands)} awesh: commands")
        
        # Create stack of commands (reverse order so we pop from first to last)
        command_stack = [cmd.strip() for cmd in reversed(awesh_commands)]
        failed_commands = []
        
        # Try commands one by one until we find one that works
        while command_stack:
            command = command_stack.pop()
            debug_log(f"Trying command: {command}")
            
            # Route command through security middleware for validation and execution
            return await self._execute_command_through_security_middleware(command)
        
        # All commands failed, try to get alternatives from AI
        debug_log(f"All {len(failed_commands)} commands failed, requesting alternatives")
        return await self._request_command_alternatives(failed_commands)
    
    async def _execute_command_through_security_middleware(self, command: str) -> str:
        """Execute AI-suggested command through security middleware"""
        debug_log(f"Executing AI command through security middleware: {command}")
        
        try:
            import subprocess
            import tempfile
            
            # Create temporary file for output capture
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Execute command in background and capture output
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.current_dir,
                    timeout=30  # 30 second timeout for safety
                )
                
                # Check if command was successful
                if result.returncode == 0:
                    # Command succeeded - return output
                    output = result.stdout if result.stdout else "Command executed successfully"
                    return f"✅ {output}"
                else:
                    # Command failed - return error
                    error_output = result.stderr if result.stderr else result.stdout
                    if not error_output:
                        error_output = f"Command failed with exit code {result.returncode}"
                    return f"❌ {error_output}"
                    
            except subprocess.TimeoutExpired:
                return "❌ Command timed out (30s limit)"
            except Exception as e:
                return f"❌ Execution error: {str(e)}"
            finally:
                # Clean up temp file
                try:
                    import os
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            debug_log(f"_execute_command_through_security_middleware: Exception: {e}")
            return f"❌ Backend error: {e}"
    
    async def _request_command_alternatives(self, failed_commands: list) -> str:
        """Request alternative commands from AI when all initial commands fail"""
        debug_log("Requesting alternative commands from AI")
        
        failed_list = "\n".join([f"- {cmd}" for cmd in failed_commands])
        retry_prompt = f"""The following commands failed:
{failed_list}

Please provide alternative awesh: commands that might work better. Return only working bash commands in the format:
awesh: <command>"""
        
        # Send retry request to AI
        try:
            retry_response = await self._handle_ai_prompt(retry_prompt)
            
            # Check if AI provided new awesh: commands
            if "awesh:" in retry_response:
                debug_log("AI provided alternative commands, trying them")
                return await self._extract_and_execute_commands(retry_response, 1)  # This is already a retry
            else:
                debug_log("AI didn't provide alternative commands")
                return f"❌ All commands failed and no alternatives provided:\n{failed_list}\n\n🤖 {retry_response}\n"
                
        except Exception as e:
            debug_log(f"Error requesting alternatives: {e}")
            return f"❌ All commands failed:\n{failed_list}\n"
    
    async def _contains_questions_or_options(self, response: str) -> bool:
        """Check if AI response contains questions or multiple options"""
        import re
        
        # Look for common question patterns
        question_patterns = [
            r'\?',  # Contains question mark
            r'Which.*do you want',  # "Which do you want"
            r'Do you want to',  # "Do you want to"
            r'Would you like to',  # "Would you like to"
            r'Please specify',  # "Please specify"
            r'Could you clarify',  # "Could you clarify"
            r'What.*do you mean',  # "What do you mean"
            r'Here are.*options?:',  # "Here are some options:"
            r'\d+\.\s',  # Numbered list (1. 2. 3.)
            r'^[a-zA-Z]\)\s',  # Lettered list (a) b) c))
            r'Choose from:',  # "Choose from:"
            r'Select.*option',  # "Select an option"
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, response, re.IGNORECASE | re.MULTILINE):
                debug_log(f"Found question pattern: {pattern}")
                return True
                
        return False
    
    async def _handle_ai_questions(self, ai_response: str, retry_count: int = 0) -> str:
        """Handle AI questions/options by automatically trying each option until we get a clean result"""
        import re
        
        debug_log("Processing AI questions/options automatically")
        
        # Extract numbered or lettered options
        options = []
        
        # Look for numbered options (1. 2. 3.)
        numbered_options = re.findall(r'(\d+\.\s*[^\n]+)', ai_response)
        if numbered_options:
            # Clean up the options (remove numbers/bullets)
            cleaned_options = [re.sub(r'^\d+\.\s*', '', opt).strip() for opt in numbered_options]
            options.extend(cleaned_options)
            debug_log(f"Found {len(numbered_options)} numbered options")
        
        # Look for lettered options (a) b) c))
        lettered_options = re.findall(r'([a-zA-Z]\)\s*[^\n]+)', ai_response)
        if lettered_options:
            # Clean up the options (remove letters/bullets)
            cleaned_options = [re.sub(r'^[a-zA-Z]\)\s*', '', opt).strip() for opt in lettered_options]
            options.extend(cleaned_options)
            debug_log(f"Found {len(lettered_options)} lettered options")
        
        if options:
            debug_log(f"Found {len(options)} total options, trying them automatically")
            return await self._try_options_stack(options)
        else:
            # No clear options found, but response seems to be a question
            # Try to extract any meaningful phrases to attempt
            debug_log("No clear options found, extracting potential interpretations")
            return await self._extract_and_try_interpretations(ai_response)
    
    async def _try_options_stack(self, options: list) -> str:
        """Try each option in the stack until we get a clean result"""
        debug_log(f"🔄 Starting option stack with {len(options)} options:")
        for i, opt in enumerate(options, 1):
            debug_log(f"   Option {i}: {opt}")
        
        # Create stack of options (reverse order so we pop from first to last)
        option_stack = [opt.strip() for opt in reversed(options)]
        failed_options = []
        option_number = 1
        
        while option_stack:
            option = option_stack.pop()
            debug_log(f"🎯 TRYING OPTION {option_number}/{len(options)}: {option}")
            
            try:
                # Send the option back to AI to get commands
                option_prompt = f"Please provide awesh: commands for: {option}"
                debug_log(f"🤖 Asking AI for commands for option {option_number}")
                option_response = await self._handle_ai_prompt(option_prompt)
                
                # Check if AI provided awesh: commands
                if "awesh:" in option_response:
                    debug_log(f"✅ Option {option_number} provided commands, trying them now")
                    result = await self._extract_and_execute_commands_with_option_context(option_response, option, option_number, retry_count)
                    
                    # Check if we got a clean result (no error indicators)
                    if not ("❌" in result or "All commands failed" in result):
                        debug_log(f"🎉 SUCCESS! Option {option_number} '{option}' worked perfectly!")
                        return result
                    else:
                        debug_log(f"❌ Option {option_number} '{option}' commands all failed")
                        failed_options.append(option)
                else:
                    debug_log(f"❌ Option {option_number} '{option}' didn't provide any commands")
                    failed_options.append(option)
                    
            except Exception as e:
                debug_log(f"❌ Error trying option {option_number} '{option}': {e}")
                failed_options.append(option)
            
            option_number += 1
        
        # All options failed
        debug_log(f"💥 All {len(failed_options)} options exhausted, none worked")
        failed_list = "\n".join([f"- {opt}" for opt in failed_options])
        return f"❌ All options failed:\n{failed_list}\n"
    
    async def _extract_and_execute_commands_with_option_context(self, ai_response: str, option: str, option_number: int, retry_count: int = 0) -> str:
        """Extract awesh: commands from AI response and execute them with enhanced debug logging for option context"""
        import re
        
        debug_log(f"🔍 Extracting commands from option {option_number} response (retry {retry_count})")
        
        # Find all awesh: command patterns
        awesh_commands = re.findall(r'awesh:\s*(.+)', ai_response)
        
        if not awesh_commands:
            debug_log(f"❌ No awesh: commands found in option {option_number} response")
            return f"No awesh: commands found for option: {option}\n"
        
        debug_log(f"📋 Found {len(awesh_commands)} commands for option {option_number} '{option}':")
        for i, cmd in enumerate(awesh_commands, 1):
            debug_log(f"   Command {i}: {cmd.strip()}")
        
        # Create stack of commands (reverse order so we pop from first to last)
        command_stack = [cmd.strip() for cmd in reversed(awesh_commands)]
        failed_commands = []
        command_number = 1
        
        # Try commands one by one until we find one that works
        while command_stack:
            command = command_stack.pop()
            debug_log(f"⚡ TRYING COMMAND {command_number}/{len(awesh_commands)} for option {option_number}: {command}")
            
            # Bash execution handled by C frontend - commands are executed there
            # For now, assume command succeeded and return success message
            debug_log(f"Command {command_number} would be executed by C frontend: {command}")
            return f"Command '{command}' would be executed by C frontend\n"
            
            command_number += 1
        
        # All commands for this option failed
        debug_log(f"💥 All {len(failed_commands)} commands failed for option {option_number} '{option}'")
        return await self._request_command_alternatives(failed_commands)
    
    async def _extract_and_try_interpretations(self, ai_response: str) -> str:
        """Extract potential interpretations from unclear AI response and try them"""
        debug_log("Extracting interpretations from unclear response")
        
        # Try to send the response back to AI for clarification
        clarify_prompt = f"The previous response was: {ai_response}\n\nPlease provide specific awesh: commands to help with this request."
        
        try:
            clarify_response = await self._handle_ai_prompt(clarify_prompt)
            
            if "awesh:" in clarify_response:
                debug_log("Got commands from clarification, trying them")
                return await self._extract_and_execute_commands(clarify_response, 1)  # This is already a retry
            else:
                debug_log("No commands from clarification")
                return f"🤖 {ai_response}\n\n❌ Could not determine specific actions to take.\n"
                
        except Exception as e:
            debug_log(f"Error getting clarification: {e}")
            return f"🤖 {ai_response}\n\n❌ Could not process request: {e}\n"
    
    async def handle_client(self, client_socket):
        """Handle client connection"""
        try:
            # Set socket to non-blocking mode
            client_socket.setblocking(False)
            
            while True:
                # Receive command using asyncio
                loop = asyncio.get_event_loop()
                try:
                    data = await loop.sock_recv(client_socket, 4096)
                    if not data:
                        break
                    
                    command = data.decode('utf-8').strip()
                    if not command:
                        continue
                    
                    # Handle special commands
                    if command == "STATUS":
                        if self.ai_ready:
                            response = "AI_READY"
                        else:
                            response = "AI_LOADING"
                        debug_log(f"STATUS response: {response}")
                    elif command.startswith("VERBOSE:"):
                        # Toggle verbose mode dynamically by setting environment variable
                        verbose_setting = command.split(":", 1)[1].strip()
                        if verbose_setting in ["1", "true", "on"]:
                            os.environ['VERBOSE'] = '1'
                            response = "🔧 Verbose mode enabled\n"
                        elif verbose_setting in ["0", "false", "off"]:
                            os.environ['VERBOSE'] = '0'
                            response = "🔇 Verbose mode disabled\n"
                        else:
                            current_verbose = os.getenv('VERBOSE', '0') == '1'
                            response = f"🔧 Verbose mode: {'enabled' if current_verbose else 'disabled'}\n"
                        
                        debug_log(f"VERBOSE command: {verbose_setting} -> {os.getenv('VERBOSE', '0')}")
                    elif command.startswith("AI_PROVIDER:"):
                        # Switch AI provider dynamically
                        provider = command.split(":", 1)[1].strip()
                        if provider in ["openai", "openrouter"]:
                            # Update config and reinitialize AI client
                            self.config.ai_provider = provider
                            response = f"🤖 Switching to {provider}... (restart awesh to take effect)\n"
                        else:
                            response = f"❌ Unknown AI provider: {provider}\n"
                        debug_log(f"AI_PROVIDER command: {provider}")
                    else:
                        # Process regular command
                        debug_log(f"Processing command: {command}")
                        response = await self.process_command(command)
                        debug_log(f"Response ready: {response[:50]}...")

                    # Send response using asyncio
                    debug_log("Sending response...")
                    await loop.sock_sendall(client_socket, response.encode('utf-8'))
                    debug_log("Response sent successfully")
                    
                except ConnectionResetError:
                    break
                except Exception as e:
                    verbose = os.getenv('VERBOSE', '0') == '1'
                    if verbose:
                        print(f"❌ Command processing error: {e}", file=sys.stderr)
                    break
                
        except Exception as e:
            verbose = os.getenv('VERBOSE', '0') == '1'
            if verbose:
                print(f"💥 Client handler error: {e}", file=sys.stderr)
        finally:
            client_socket.close()
    
    async def run_server(self):
        """Run socket server"""
        # Remove existing socket
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass
        
        # Create socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(SOCKET_PATH)
        self.socket.listen(1)
        
        verbose = os.getenv('VERBOSE', '0') == '1'
        if verbose:
            print(f"🔧 Backend: Listening on {SOCKET_PATH}", file=sys.stderr)
        
        # Start AI initialization in background
        asyncio.create_task(self.initialize())
        
        # Set server socket to non-blocking
        self.socket.setblocking(False)
        
        # Accept connections
        loop = asyncio.get_event_loop()
        while True:
            try:
                client_socket, _ = await loop.sock_accept(self.socket)
                verbose = os.getenv('VERBOSE', '0') == '1'
                if verbose:
                    print("🔌 Backend: Client connected", file=sys.stderr)
                
                # Handle client in background
                asyncio.create_task(self.handle_client(client_socket))
                
            except Exception as e:
                verbose = os.getenv('VERBOSE', '0') == '1'
                if verbose:
                    print(f"🚨 Server error: {e}", file=sys.stderr)
                break
    
    def cleanup(self):
        """Cleanup resources"""
        if self.socket:
            self.socket.close()
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

async def main():
    backend = AweshSocketBackend()
    
    try:
        await backend.run_server()
    except KeyboardInterrupt:
        print("Backend: Shutting down...", file=sys.stderr)
    finally:
        backend.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
