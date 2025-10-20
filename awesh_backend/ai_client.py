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
            
        # Initialize OpenAI client (supports OpenRouter)
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
        return """You are an expert shell assistant working in a Linux terminal environment.

<response_format>
You have three ways to respond based on what the user needs:

1. **Execute shell commands** - Use this format:
   awesh: <command>
   
2. **Edit files** - Use this format:
   ```edit:path/to/file
   <<<<<<< OLD
   exact text to find
   =======
   new text to replace with
   >>>>>>> NEW
   ```

3. **Provide information** - Just respond with plain text
</response_format>

<guidelines>
- The user's request is SUPREME - do exactly what they ask
- Be direct and actionable - no preambles or apologies
- For "create/make/write" requests → provide the solution immediately
- For "check/show/list" requests → give the exact command with awesh: prefix
- For "edit/update/change" requests → use file edit blocks
- For "what/how/why" requests → explain concisely
- Prefer one-liners with pipes and command chaining
- Trust the user knows their environment
</guidelines>

<examples>
User: "create a script to check all open ports"
You: 
```edit:check_ports.sh
<<<<<<< OLD
=======
#!/bin/bash
# Check all open ports
sudo netstat -tulpn | grep LISTEN
sudo ss -tulpn | grep LISTEN
lsof -i -P -n | grep LISTEN
>>>>>>> NEW
```

User: "find all python files modified today"
You: awesh: find . -name "*.py" -mtime 0

User: "what does netstat do?"
You: netstat displays network connections, routing tables, and network interface statistics. Use -tulpn to show TCP/UDP listening ports with program names.
</examples>

<critical>
- User prompt is ALWAYS correct - do what they ask
- NO suggestions unless explicitly asked
- NO safety warnings for standard operations
- Give solutions, not explanations
</critical>"""
        
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
            if model_name.startswith('gpt-5') or model_name.startswith('o1'):
                # GPT-5 requires max_completion_tokens instead of max_tokens
                api_params["max_completion_tokens"] = self.config.max_tokens
                # GPT-5 only supports temperature=1.0 (default value)
                # Don't set temperature parameter - let it use the default
                # Add top_p for better command generation (if supported)
                # api_params["top_p"] = 0.9  # Skip for GPT-5 compatibility
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
                    # Check for organization verification error
                    if "organization must be verified" in error_msg.lower() or "unsupported_value" in error_msg:
                        # Fall back to non-streaming
                        pass
                    else:
                        # Other errors should be reported
                        yield f"Error processing prompt: {e}"
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
            response = await self.client.chat.completions.create(**api_params_nonstream)
            
            content = response.choices[0].message.content
            debug_log(f"Non-streaming response length: {len(content) if content else 0} chars")
            if content:
                debug_log(f"Non-streaming preview: '{content[:100]}...'")
                yield content
            else:
                debug_log("❌ Non-streaming response is empty!")
                    
        except Exception as e:
            yield f"Error processing prompt: {e}"
            
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
