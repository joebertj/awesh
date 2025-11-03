"""
Response Agent for awesh - Processes AI responses and delegates to appropriate agents

This agent analyzes AI responses and routes them to the correct specialized agent:
- File Editor Agent: for file edit blocks and code blocks that should be files
- Execution Agent: routes to Shell Agent (Sandbox/C) for command execution
- File Agent: for file context (already used in prompt processing)
- TODO Agent: for goal tracking (used in iterative workflows)

Architecture - Agent Hierarchy:
┌─────────────────────────────────────────┐
│      Response Agent (Coordinator)      │
└─────────────────────────────────────────┘
            │
    ┌───────┼───────┬───────┬───────┐
    │       │       │       │       │
┌───▼───┐ ┌─▼──┐ ┌─▼───┐ ┌─▼──┐ ┌─▼───┐
│ File  │ │File│ │Exec │ │TODO│ │Shell│
│Editor │ │Agent│ │Agent│ │Agent│ │Agent│
│       │ │     │ │     │ │     │ │(C)  │
└───────┘ └─────┘ └──┬──┘ └─────┘ └─────┘
                      │
              Routes commands to
                      │
                 ┌────▼────┐
                 │ Shell   │
                 │ Agent   │ ⚡ C-based for speed
                 │(Sandbox)│
                 └─────────┘

The Shell Agent (sandbox) is a specialized C-based agent for fast command execution:
- Implemented in C (awesh_sandbox.c) for performance
- Validates and executes shell commands quickly
- Provides isolated execution environment
- All commands MUST go through: Execution Agent → Shell Agent

Features:
- Detects file edit blocks (```edit:filename format)
- Detects executable commands (awesh: command format)
- Detects code blocks that should be written to files
- Delegates processing to specialized agents
- Routes all commands through Shell Agent (C-based) for fast execution
"""

import os
import sys
import re
from typing import Optional, List, Dict
from pathlib import Path

def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"📤 Response Agent: {message}", file=sys.stderr)


class ResponseAgent:
    """Agent that processes AI responses and delegates to specialized agents"""
    
    def __init__(self, file_editor, execution_agent):
        """
        Initialize response agent
        
        Args:
            file_editor: FileEditor instance for handling file operations
            execution_agent: ExecutionAgent instance for command execution
        """
        self.file_editor = file_editor
        self.execution_agent = execution_agent
    
    async def process_response(self, ai_response: str) -> tuple[str, bool]:
        """
        Process AI response and delegate to appropriate agents
        
        Args:
            ai_response: The raw AI response
            
        Returns:
            Tuple of (output_message, was_processed)
            - output_message: Formatted message to display to user
            - was_processed: True if response was processed by an agent, False if display as-is
        """
        debug_log("Processing AI response")
        
        # Clean up thinking process if present
        cleaned_response = self._clean_thinking(ai_response)
        
        # Priority 1: Check for explicit file edit blocks
        edits = self.file_editor.parse_edit_block(cleaned_response)
        if edits:
            debug_log(f"Found {len(edits)} file edit blocks - delegating to file editor")
            return await self._handle_file_edits(cleaned_response), True
        
        # Priority 2: Check for explicit awesh: commands
        if self._has_explicit_awesh_commands(cleaned_response):
            debug_log("Found explicit awesh: commands - delegating to execution agent")
            return await self._handle_commands(cleaned_response), True
        
        # Priority 3: Check for code blocks that should be written to files
        code_blocks = self._extract_code_blocks(cleaned_response)
        if code_blocks:
            debug_log(f"Found {len(code_blocks)} code blocks - checking if they should be files")
            file_result = await self._handle_code_blocks_as_files(code_blocks)
            if file_result:
                # Append file creation results to the response
                return f"{cleaned_response}\n\n{file_result}", True
        
        # No special processing needed - display as-is
        debug_log("No special processing needed - returning response as-is")
        return cleaned_response, False
    
    def _clean_thinking(self, response: str) -> str:
        """Remove thinking process markers from response"""
        thinking_end_markers = [
            "...done thinking.",
            "... done thinking.",
            "done thinking.",
            "done thinking",
        ]
        
        response_lower = response.lower()
        last_marker_pos = -1
        last_marker_len = 0
        
        for marker in thinking_end_markers:
            marker_lower = marker.lower()
            pos = response_lower.rfind(marker_lower)
            if pos > last_marker_pos:
                last_marker_pos = pos
                last_marker_len = len(marker)
        
        if last_marker_pos != -1:
            cleaned = response[last_marker_pos + last_marker_len:].strip()
            debug_log(f"🧹 Removed thinking process ({last_marker_pos} chars before marker)")
            return cleaned
        
        return response
    
    def _has_explicit_awesh_commands(self, response: str) -> bool:
        """Check if response contains explicit 'awesh:' commands on their own lines (not in code blocks)"""
        lines = response.split('\n')
        in_code_block = False
        for line in lines:
            stripped = line.strip()
            # Track code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            # Skip code blocks and comments
            if in_code_block or stripped.startswith('#'):
                continue
            # Match "awesh:" at start of line (after optional whitespace)
            if re.match(r'^\s*awesh:\s*(.+)$', line):
                debug_log(f"Found explicit awesh: command on line: '{line[:50]}'")
                return True
        return False
    
    def _extract_code_blocks(self, response: str) -> List[Dict]:
        """Extract code blocks from response"""
        code_blocks = []
        # Pattern: ```language or ```filename or ``` (optional language/filename on first line)
        pattern = r'```(?:(\w+)|([^\n]+))?\n(.*?)```'
        matches = re.finditer(pattern, response, re.DOTALL)
        for match in matches:
            language_or_file = match.group(1) or match.group(2) or ""
            code = match.group(3).strip()
            if code and len(code) > 10:  # Only consider substantial code blocks
                code_blocks.append({
                    'language': language_or_file,
                    'content': code,
                    'full_match': match.group(0)
                })
                debug_log(f"Extracted code block: language={language_or_file}, size={len(code)} chars")
        return code_blocks
    
    async def _handle_file_edits(self, ai_response: str) -> str:
        """Handle file edits using file editor"""
        debug_log("Delegating file edits to file editor")
        
        edits = self.file_editor.parse_edit_block(ai_response)
        if not edits:
            return f"🤖 {ai_response}\n"
        
        debug_log(f"File editor found {len(edits)} edit blocks")
        
        # Apply edits
        results = self.file_editor.apply_multiple_edits(edits)
        
        # Format response
        output = "📝 File Edit Results:\n\n"
        success_count = 0
        created_files = []
        
        for result in results:
            if result.success:
                success_count += 1
                output += f"✅ {result.message}\n"
                if result.backup_path:
                    output += f"   Backup: {result.backup_path}\n"
                if "Successfully created" in result.message:
                    created_files.append(result.file_path)
            else:
                output += f"❌ {result.message}\n"
        
        output += f"\n📊 {success_count}/{len(results)} edits applied successfully\n"
        
        # Add helpful follow-up instructions for newly created scripts
        if created_files:
            output += "\n➡️  Next steps:\n"
            for filepath in created_files:
                filename = filepath.split('/')[-1]
                output += f"   • Run now: sh {filename}\n"
                output += f"   • Or make executable: chmod +x {filename} && ./{filename}\n"
        
        # Include original AI response if there's additional context
        if '```' not in ai_response or len(ai_response.split('```')[0].strip()) > 10:
            preamble = ai_response.split('```')[0].strip()
            if preamble:
                output = f"🤖 {preamble}\n\n{output}"
        
        return output
    
    async def _handle_commands(self, ai_response: str) -> str:
        """Extract and execute awesh: commands via Execution Agent → Shell Agent (C-based)"""
        debug_log("Extracting and executing awesh: commands via Execution Agent → Shell Agent (C)")
        
        # Extract commands (same logic as server.py but using execution agent)
        lines = ai_response.split('\n')
        awesh_commands = []
        in_code_block = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                continue
            if in_code_block or stripped.startswith('#'):
                continue
            
            match = re.match(r'^\s*awesh:\s*(.+)$', line)
            if match:
                cmd = match.group(1).strip()
                if cmd and not cmd.startswith('#') and len(cmd) > 0:
                    words = cmd.split()
                    if len(words) >= 2 or any(char in cmd for char in ['/', '|', '&', ';', '(', ')', '{', '}', '$', '`']):
                        awesh_commands.append(cmd)
                        debug_log(f"Found awesh: command: '{cmd}'")
        
        if not awesh_commands:
            debug_log("No valid awesh: commands found")
            return ""
        
        debug_log(f"Routing {len(awesh_commands)} commands through Execution Agent → Shell Agent (C)")
        
        # All commands must go through Execution Agent → Shell Agent (C-based sandbox)
        # Shell Agent is C-based (awesh_sandbox.c) for fast command execution
        results = []
        for command in awesh_commands:
            debug_log(f"🔄 Routing command to Shell Agent (C): '{command}'")
            result = await self.execution_agent.execute_command(command)
            results.append((command, result))
        
        # Format results
        output_lines = []
        for command, result in results:
            if result.success:
                output = result.stdout if result.stdout else "Command executed successfully"
                output_lines.append(f"✅ {command}")
                if output and output.strip():
                    output_lines.append(f"   {output}")
            else:
                error = result.stderr if result.stderr else f"Command failed with exit code {result.exit_code}"
                output_lines.append(f"❌ {command}")
                if error and error.strip():
                    output_lines.append(f"   {error}")
        
        return "\n".join(output_lines) if output_lines else ""
    
    async def _handle_code_blocks_as_files(self, code_blocks: List[Dict]) -> Optional[str]:
        """Convert code blocks to files using file editor"""
        from awesh_backend.file_editor import FileEdit
        
        edits = []
        
        for i, block in enumerate(code_blocks):
            lang = block['language'].strip() if block['language'] else ""
            content = block['content']
            
            # Check if it looks like file content
            has_shebang = content.startswith('#!')
            looks_like_script = has_shebang or lang in ['sh', 'bash', 'python', 'py', 'js', 'javascript', 'rb', 'ruby', 'go', 'rs', 'c', 'cpp', 'java', 'php']
            is_substantial = len(content) > 20 and not content.strip().startswith('#')
            
            if not (looks_like_script or is_substantial):
                continue
            
            # Determine filename
            filename = None
            if has_shebang:
                if 'python' in content[:100].lower() or lang in ['python', 'py']:
                    filename = f"script_{i+1}.py"
                elif 'bash' in content[:100].lower() or 'sh' in content[:100].lower() or lang in ['bash', 'sh']:
                    filename = f"script_{i+1}.sh"
                elif 'node' in content[:100].lower() or lang in ['js', 'javascript']:
                    filename = f"script_{i+1}.js"
                else:
                    filename = f"script_{i+1}"
            elif lang:
                extension_map = {
                    'python': 'py', 'py': 'py',
                    'bash': 'sh', 'sh': 'sh', 'shell': 'sh',
                    'javascript': 'js', 'js': 'js',
                    'typescript': 'ts', 'ts': 'ts',
                    'go': 'go', 'golang': 'go',
                    'rust': 'rs',
                    'c': 'c', 'cpp': 'cpp', 'c++': 'cpp',
                    'java': 'java',
                    'ruby': 'rb', 'rb': 'rb',
                    'php': 'php',
                    'json': 'json',
                    'yaml': 'yaml', 'yml': 'yaml',
                    'html': 'html',
                    'css': 'css',
                    'markdown': 'md', 'md': 'md',
                }
                ext = extension_map.get(lang.lower(), 'txt')
                filename = f"script_{i+1}.{ext}"
            else:
                if content.startswith('#!/'):
                    filename = f"script_{i+1}.sh"
                else:
                    filename = f"script_{i+1}.txt"
            
            if filename:
                edit = FileEdit(
                    file_path=filename,
                    old_content="",
                    new_content=content
                )
                edits.append(edit)
                debug_log(f"Converted code block {i+1} to file edit: {filename}")
        
        if not edits:
            return None
        
        # Use file editor to apply edits
        try:
            results = self.file_editor.apply_multiple_edits(edits)
            
            output_lines = []
            success_count = 0
            created_files = []
            
            for result in results:
                if result.success:
                    success_count += 1
                    output_lines.append(f"✅ {result.message}")
                    if result.backup_path:
                        output_lines.append(f"   Backup: {result.backup_path}")
                    if "Successfully created" in result.message:
                        created_files.append(result.file_path)
                else:
                    output_lines.append(f"❌ {result.message}")
            
            if output_lines:
                header = f"📝 Created {success_count}/{len(results)} file(s) from code blocks:"
                output_lines.insert(0, header)
                
                if created_files:
                    output_lines.append("")
                    output_lines.append("➡️  Next steps:")
                    for filepath in created_files:
                        filename = filepath.split('/')[-1]
                        output_lines.append(f"   • Run: sh {filename}")
                        output_lines.append(f"   • Or make executable: chmod +x {filename} && ./{filename}")
                
                return "\n".join(output_lines)
        except Exception as e:
            debug_log(f"Error applying file edits from code blocks: {e}")
            return f"⚠️ Error creating files from code blocks: {e}"
        
        return None


def get_response_agent(file_editor, execution_agent):
    """Get or create response agent instance"""
    return ResponseAgent(file_editor, execution_agent)
