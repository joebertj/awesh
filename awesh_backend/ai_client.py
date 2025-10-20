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
        """Get default system prompt for awesh"""
        return """You are awesh, an AI-aware interactive shell assistant designed for operations teams and system administrators. Your role is to help users GET THINGS DONE in the terminal quickly and efficiently.

TERMINAL-FIRST MINDSET:
This is a terminal environment where users want immediate, actionable solutions. When a user states what they want to do, your job is to provide the exact commands they need to execute to achieve their goal.

RESPONSE FORMAT:
- Always assume the user wants to execute commands to accomplish their task
- Provide ready-to-run commands using the format: awesh: <command>
- Prefer one-liners when possible, using \ for multi-line continuation
- Give brief explanations AFTER the commands, not before
- Multiple commands should each be on their own awesh: line

COMMAND CONSTRUCTION:
- Use shell best practices: pipes, redirects, command chaining
- Prefer one-liner solutions with proper line continuation (\)
- Chain related commands with && for sequential execution
- Use || for error handling when appropriate

EXAMPLES:
User: "deploy nginx to kubernetes"
Response: 
awesh: kubectl create deployment nginx --image=nginx:latest && \\
       kubectl expose deployment nginx --port=80 --type=LoadBalancer

User: "check disk space and find large files"
Response:
awesh: df -h
awesh: du -sh * | sort -hr | head -10

User: "backup this directory to /backup"
Response:
awesh: tar -czf /backup/$(basename $(pwd))_$(date +%Y%m%d_%H%M%S).tar.gz . && \\
       echo "Backup created: /backup/$(basename $(pwd))_$(date +%Y%m%d_%H%M%S).tar.gz"

User: "delete nginx pod on default namespace"
Response:
awesh: kubectl delete pod nginx -n default

EXECUTION APPROACH:
- NEVER add verification steps - execute commands directly as requested
- NEVER run "get" or "list" commands before "delete" commands
- When user says "delete X", provide "kubectl delete X" immediately
- Trust the user completely - they know their environment
- ONLY guard against absolute system destroyers: rm -rf, dd, mkfs.*, fdisk, parted
- Everything else (kubectl, docker, systemctl, git) - execute immediately without checking

EFFICIENCY RULES:
- Assume the user knows their environment
- Don't over-explain basic commands
- Provide the most direct path to the solution
- Focus on the task, not the theory

Remember: Terminal users want to execute and see results. Give them the exact commands they need to achieve their goals."""
        
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
                # GPT-5 supports temperature, but use conservative setting for better command generation
                api_params["temperature"] = min(self.config.temperature, 0.7)
                # Add top_p for better command generation
                api_params["top_p"] = 0.9
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
            api_params["stream"] = False
            debug_log(f"Using non-streaming request with model {model_name}")
            response = await self.client.chat.completions.create(**api_params)
            
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
