"""
AI client for awesh - handles OpenAI API interactions
"""

import os
import sys
import asyncio
from typing import Optional, AsyncGenerator, Dict, Any
from pathlib import Path

# Lazy imports - only import when needed
openai = None
AsyncOpenAI = None

from .config import Config

# Global verbose setting - same as server.py
def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"🔧 AI Client: {message}", file=sys.stderr)


class AweshAIClient:
    """AI client for handling OpenAI API interactions"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.system_prompt = None
        
    async def initialize(self):
        """Initialize the AI client and load system prompt"""
        debug_log("Starting AI client initialization...")
        
        # Import OpenAI when actually needed
        global AsyncOpenAI
        if AsyncOpenAI is None:
            debug_log("Importing AsyncOpenAI...")
            from openai import AsyncOpenAI
            
        # Initialize OpenAI client (supports OpenRouter, Ollama)
        ai_provider = os.getenv('AI_PROVIDER', 'openai')
        debug_log(f"AI Provider: {ai_provider}")
        debug_log(f"Model from config: {self.config.model}")
        debug_log(f"MODEL env var: {os.getenv('MODEL', 'not set')}")
        
        if ai_provider == 'openrouter':
            # Using OpenRouter
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable not set")
            base_url = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
            debug_log(f"Creating OpenRouter client with base_url: {base_url}")
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            debug_log("OpenRouter client created successfully")
        elif ai_provider == 'ollama':
            # Using local Ollama
            base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434/v1')
            api_key = os.getenv('OLLAMA_API_KEY', 'ollama')  # Ollama doesn't require a key, but some setups use it
            debug_log(f"Creating Ollama client with base_url: {base_url}")
            self.client = AsyncOpenAI(
                api_key=api_key,  # Ollama typically doesn't require a real key
                base_url=base_url
            )
            debug_log("Ollama client created successfully")
        elif ai_provider == 'perplexity':
            # Using Perplexity
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if not api_key:
                raise ValueError("PERPLEXITY_API_KEY environment variable not set")
            base_url = os.getenv('PERPLEXITY_BASE_URL', 'https://api.perplexity.ai')
            debug_log(f"Creating Perplexity client with base_url: {base_url}")
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            debug_log("Perplexity client created successfully")
        else:
            # Using standard OpenAI
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                debug_log("Warning: OPENAI_API_KEY not set - AI will not be available")
                self.client = None
                return  # Skip initialization, but don't crash
            debug_log("Creating OpenAI client...")
            self.client = AsyncOpenAI(api_key=api_key)
            debug_log("OpenAI client created successfully")
        
        # Load system prompt (this can be slow if creating default)
        debug_log("Loading system prompt...")
        await self._load_system_prompt()
        debug_log("System prompt loaded")
        
        debug_log("AI client initialization completed")
        
    async def _load_system_prompt(self):
        """Load system prompt from configured file"""
        prompt_file = self.config.system_prompt_file
        
        if prompt_file.exists():
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    self.system_prompt = f.read().strip()
            except Exception as e:
                print(f"Warning: Could not load system prompt from {prompt_file}: {e}")
                self.system_prompt = self._get_default_system_prompt()
        else:
            # Use default system prompt (don't block on file creation)
            self.system_prompt = self._get_default_system_prompt()
            debug_log("Using default system prompt")
            # Skip file creation to avoid any I/O blocking
            
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for awesh - based on proven Claude/Cursor approach"""
        return """You are an expert shell assistant with agentic capabilities like Cursor/Claude.

<your_capabilities>
You can:
1. Create and track goals with multiple subtasks
2. Iterate up to 10 times to achieve a goal
3. Run commands internally in sandbox to gather information
4. Create and edit files directly
5. Learn from execution results and refine approach
6. Ask user to continue if you need more iterations

You have access to:
- Execution Agent: Run commands in sandbox, see results, iterate
- File Editor: Create/modify files with surgical precision
- File Agent: Read file contents for context
- TODO Agent: Track goal progress across iterations

You CANNOT:
- See the user's screen directly (unless they share output)
- Access commands the user runs directly (those bypass you for speed)
</your_capabilities>

<agentic_loop>
When user gives you a COMPLEX goal (multiple steps), you should:

1. Break it into subtasks (mentally or explicitly)
2. Execute each subtask
3. Check results
4. Iterate if needed (up to 10 times total)
5. Report completion or ask user to continue

Example complex goal:
User: "deploy nginx to kubernetes with monitoring"

Your approach:
Iteration 1: Create deployment.yaml → File edit
Iteration 2: Apply deployment → Suggest: awesh: kubectl apply -f deployment.yaml
Iteration 3: Create monitoring config → File edit
Iteration 4: Apply monitoring → Suggest: awesh: kubectl apply -f monitoring.yaml
DONE ✅

For SIMPLE requests, just respond directly (no iterations needed).
</agentic_loop>

<response_format>
THREE response modes based on user intent:

1. **COMMAND MODE** - User wants to execute something:
   awesh: <command>
   
   The user will see this command executed in their terminal.
   Use for: check, show, list, find, monitor, deploy, delete, etc.

2. **FILE EDIT MODE** - User wants to create or modify files:
   ```edit:path/to/file
   <<<<<<< OLD
   exact old content (leave empty for new files)
   =======
   new content here
   >>>>>>> NEW
   ```
   
   The file will be created/edited automatically with backup.
   Use for: create script, update config, fix code, write file, etc.

   When creating scripts:
   - Always make the script print/output results (e.g., echo "$var")
   - Use portable POSIX sh if possible (#!/bin/sh)
   - Prefer non-interactive commands
   - After the edit block, include a single awesh: line to run the script now

3. **NORMAL MODE** - User wants information:
   Plain text response with clear, concise information.
   
   Use for: what/how/why questions, explanations.
</response_format>

<examples>
User: "create a script to check all open ports"
You: 
```edit:check_ports.sh
<<<<<<< OLD
=======
#!/bin/sh
# Check all open listening ports (comma-separated)
open_ports=$(netstat -tuln 2>/dev/null | awk '/^tcp|^udp/ {print $4}' | sed 's/.*://g' | sort -un | paste -sd, -)
echo "$open_ports"
>>>>>>> NEW
```
awesh: sh check_ports.sh

➡️  Next steps:
- Run once: sh check_ports.sh
- Or make executable and run: chmod +x check_ports.sh && ./check_ports.sh

User: "find large files over 100MB"
You: awesh: find . -type f -size +100M -exec ls -lh {} \;

User: "what's the difference between netstat and ss?"
You: ss is the modern replacement for netstat. It's faster and provides more detailed socket information. Use ss -tulpn for listening ports (same flags as netstat).

User: "check disk space"  
You: awesh: df -h

User: "change debug to true in config.py"
You:
```edit:config.py
<<<<<<< OLD
DEBUG = False
=======
DEBUG = True
>>>>>>> NEW
```
</examples>

<iteration_control>
After each response, add ONE of these markers on the last line:

- ✅ GOAL_COMPLETE — you finished the user's goal
- 🔄 CONTINUE_ITERATION — continue with the next internal step
- ❓ NEED_USER_INPUT — you need the user to choose/confirm something

This controls awesh's loop (max 10 iterations per goal).
</iteration_control>

<critical_rules>
- User's request is SUPREME - do EXACTLY what they ask
- Be DIRECT - no apologies, hedging, warnings, or "let me help you"
- Give the solution IMMEDIATELY - no preambles
- Trust the user knows their environment
- One response = one solution (no alternatives unless asked)
- Brevity over verbosity
- For SIMPLE tasks: respond once and mark COMPLETE
- For COMPLEX tasks: iterate and mark CONTINUE until done
</critical_rules>"""
        
    async def _create_default_system_prompt_file(self, prompt_file: Path):
        """Create default system prompt file"""
        try:
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(self.system_prompt)
            print(f"Created default system prompt at {prompt_file}")
        except Exception as e:
            print(f"Warning: Could not create system prompt file at {prompt_file}: {e}")
            
    async def process_prompt(self, user_prompt: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """
        Process a user prompt and yield streaming response
        
        Args:
            user_prompt: The user's input prompt
            context: Optional context information (current directory, last command, etc.)
            
        Yields:
            String chunks of the AI response
        """
        if not self.client:
            yield "❌ AI not available - OPENAI_API_KEY not set"
            return
            
        messages = []
        
        # Add system prompt
        if self.system_prompt:
            messages.append({
                "role": "system", 
                "content": self.system_prompt
            })
            
        # Add context if provided
        if context:
            context_str = self._format_context(context)
            if context_str:
                messages.append({
                    "role": "system",
                    "content": f"Current context:\n{context_str}"
                })
        
        # Add user prompt
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        try:
            # Prepare API parameters - handle different model constraints
            # Use MODEL environment variable if set, otherwise fall back to config
            model_name = os.getenv('MODEL', self.config.model)
            api_params = {
                "model": model_name,
                "messages": messages,
            }
            
            # Handle model-specific parameters
            if model_name.startswith('o1'):
                # O1 models use max_completion_tokens and don't support temperature
                api_params["max_completion_tokens"] = self.config.max_tokens
                # Don't set temperature - o1 models don't support it
            elif model_name.startswith('gpt-4o'):
                # GPT-4o supports standard parameters
                api_params["max_tokens"] = self.config.max_tokens
                api_params["temperature"] = self.config.temperature
            else:
                # Other models support standard parameters
                api_params["max_tokens"] = self.config.max_tokens
                api_params["temperature"] = self.config.temperature
            
            # Try streaming first, fall back to non-streaming if needed
            try_streaming = self.config.streaming
            
            if try_streaming:
                try:
                    # Streaming response
                    api_params["stream"] = True
                    debug_log(f"Starting streaming request with model {model_name}")
                    stream = await self.client.chat.completions.create(**api_params)
                    
                    chunk_count = 0
                    content_chunks = 0
                    async for chunk in stream:
                        chunk_count += 1
                        if chunk.choices[0].delta.content:
                            content_chunks += 1
                            debug_log(f"Yielding chunk {content_chunks}: '{chunk.choices[0].delta.content[:50]}...'")
                            yield chunk.choices[0].delta.content
                        else:
                            debug_log(f"Empty chunk {chunk_count} (no content)")
                    
                    debug_log(f"Streaming complete - {chunk_count} total chunks, {content_chunks} with content")
                    return
                    
                except Exception as e:
                    error_msg = str(e)
                    # For Ollama, don't fallback - fail clearly if streaming fails
                    ai_provider = os.getenv('AI_PROVIDER', 'openai')
                    if ai_provider == 'ollama':
                        yield f"❌ Ollama streaming error: {e}\n"
                        yield f"💡 Check that Ollama is running and model '{os.getenv('MODEL', self.config.model)}' is available\n"
                        return
                    # For other providers, check for organization verification error
                    if "organization must be verified" in error_msg.lower() or "unsupported_value" in error_msg:
                        # Fall back to non-streaming
                        pass
                    else:
                        # Other errors should be reported
                        yield f"❌ Error processing prompt: {e}\n"
                        return
            
            # Non-streaming response (either by config or fallback)
            # Rebuild api_params for non-streaming to avoid parameter conflicts
            api_params_nonstream = {
                "model": model_name,
                "messages": messages,
                "stream": False
            }
            
            # Handle model-specific parameters for non-streaming
            if model_name.startswith('gpt-5') or model_name.startswith('o1'):
                api_params_nonstream["max_completion_tokens"] = self.config.max_tokens
                # Don't set temperature for GPT-5 - use default
            else:
                api_params_nonstream["max_tokens"] = self.config.max_tokens
                api_params_nonstream["temperature"] = self.config.temperature
            
            debug_log(f"Using non-streaming request with model {model_name}")
            try:
                response = await self.client.chat.completions.create(**api_params_nonstream)
                
                content = response.choices[0].message.content
                debug_log(f"Non-streaming response length: {len(content) if content else 0} chars")
                if content:
                    debug_log(f"Non-streaming preview: '{content[:100]}...'")
                    yield content
                else:
                    ai_provider = os.getenv('AI_PROVIDER', 'openai')
                    if ai_provider == 'ollama':
                        yield f"❌ Ollama returned empty response\n"
                        yield f"💡 Check that model '{model_name}' is available: ollama list\n"
                    else:
                        debug_log("❌ Non-streaming response is empty!")
                        yield "❌ Empty response from AI\n"
            except Exception as e:
                ai_provider = os.getenv('AI_PROVIDER', 'openai')
                if ai_provider == 'ollama':
                    yield f"❌ Ollama error: {e}\n"
                    yield f"💡 Verify Ollama is running: curl http://localhost:11434/api/tags\n"
                    yield f"💡 Verify model '{model_name}' exists: ollama list\n"
                else:
                    yield f"❌ Error processing prompt: {e}\n"
                    
        except Exception as e:
            ai_provider = os.getenv('AI_PROVIDER', 'openai')
            if ai_provider == 'ollama':
                yield f"❌ Ollama request failed: {e}\n"
                yield f"💡 Check Ollama status and model availability\n"
            else:
                yield f"❌ Error processing prompt: {e}\n"
            
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context information for the AI"""
        context_parts = []
        
        if 'current_directory' in context:
            context_parts.append(f"Working directory: {context['current_directory']}")
            
        if 'last_command' in context:
            context_parts.append(f"Last command: {context['last_command']}")
            
        if 'last_exit_code' in context:
            if context['last_exit_code'] != 0:
                context_parts.append(f"Last command exit code: {context['last_exit_code']}")
                
        return "\n".join(context_parts)
        
    async def close(self):
        """Clean up resources"""
        if self.client:
            await self.client.close()
