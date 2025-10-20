"""
File Agent for awesh - Intelligent file detection and context injection

This agent processes user prompts to detect file references and automatically
injects relevant file content into the AI prompt for better context.

Features:
- Exact filename matching
- Partial filename matching (ignoring extensions)
- Fuzzy filename matching using grep patterns
- Smart content extraction (head/tail/targeted lines)
- File type-aware content limiting
- Multiple file handling
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

# Global verbose setting - shared with server.py
def debug_log(message):
    """Log debug message if verbose mode is enabled"""
    verbose = os.getenv('VERBOSE', '0') == '1'
    if verbose:
        print(f"🔍 File Agent: {message}", file=sys.stderr)


@dataclass
class FileMatch:
    """Represents a matched file with metadata"""
    path: str
    match_type: str  # 'exact', 'partial', 'fuzzy'
    confidence: float
    size: int
    lines: int


class FileAgent:
    """Intelligent file detection and context injection agent"""
    
    def __init__(self, max_file_size: int = 50000, max_total_content: int = 10000, 
                 max_files: int = 5, enabled: bool = True, ai_enhance: bool = True):
        self.max_file_size = max_file_size  # Max size per file to process
        self.max_total_content = max_total_content  # Max total content to inject
        self.max_files = max_files  # Max number of files to include
        self.enabled = enabled
        self.ai_enhance = ai_enhance  # Always True for built-in agents
        self.current_dir = os.getcwd()
        
        # File patterns that likely indicate file references
        self.file_patterns = [
            r'\b[\w\-\.]+\.(py|js|ts|jsx|tsx|go|rs|c|cpp|h|hpp|java|rb|php|sh|bash|zsh|fish|yml|yaml|json|xml|html|css|scss|sass|md|txt|log|conf|cfg|ini|env|dockerfile|makefile|gemfile|package\.json|requirements\.txt|cargo\.toml|go\.mod)\b',
            r'\b[\w\-\.]+/[\w\-\.]+\b',  # path-like patterns
            r'\.?/[\w\-\./]+\b',  # relative paths
            r'~/[\w\-\./]+\b',  # home-relative paths
        ]
        
        # Binary file extensions to skip
        self.binary_extensions = {
            '.bin', '.exe', '.dll', '.so', '.dylib', '.o', '.a', '.lib',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
            '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
            '.pyc', '.pyo', '.class', '.jar', '.war'
        }
    
    
    async def process_prompt(self, prompt: str, working_dir: str = None) -> Tuple[str, bool]:
        """
        Process user prompt to detect file references and inject context
        
        Returns:
            Tuple[enhanced_prompt, files_found]
        """
        if not self.enabled:
            return prompt, False
            
        if working_dir:
            self.current_dir = working_dir
            
        debug_log(f"Processing prompt in directory: {self.current_dir}")
        
        # Skip file agent for file creation requests
        if self._is_file_creation_request(prompt):
            debug_log("File creation request detected - skipping file agent processing")
            return prompt, False
        
        # Extract potential file references from prompt
        file_candidates = self._extract_file_candidates(prompt)
        
        if not file_candidates:
            debug_log("No file candidates found in prompt")
            return prompt, False
            
        debug_log(f"Found {len(file_candidates)} file candidates: {file_candidates}")
        
        # Search for actual files
        file_matches = await self._search_files(file_candidates)
        
        if not file_matches:
            debug_log("No actual files found for candidates")
            return prompt, False
            
        debug_log(f"Found {len(file_matches)} file matches")
        
        # Extract and inject file content
        enhanced_prompt = await self._inject_file_context(prompt, file_matches)
        
        return enhanced_prompt, True
    
    def _is_file_creation_request(self, prompt: str) -> bool:
        """Detect if this is a file creation request that should skip file agent processing"""
        prompt_lower = prompt.lower()
        
        # Common file creation patterns
        creation_patterns = [
            r'\b(create|write|make|generate|build)\s+.*\s+(file|program|script|code)',
            r'\b(write|create|make)\s+.*\s+as\s+\w+\.\w+',
            r'\b(generate|create)\s+.*\s+and\s+name\s+it',
            r'\b(hello\s+world|hello\s+world\s+in)',
            r'\b(create|write)\s+.*\s+in\s+\w+\s+and\s+name\s+it',
        ]
        
        for pattern in creation_patterns:
            if re.search(pattern, prompt_lower):
                return True
        
        return False
    
    def _extract_file_candidates(self, prompt: str) -> List[str]:
        """Extract potential file references from the prompt and verify they exist"""
        potential_candidates = set()
        
        # Apply each pattern
        for pattern in self.file_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # For patterns with groups, take the full match
                    full_match = re.search(pattern, prompt, re.IGNORECASE)
                    if full_match:
                        potential_candidates.add(full_match.group(0))
                else:
                    potential_candidates.add(match)
        
        # Look for words that are likely filenames (more restrictive)
        words = prompt.split()
        for word in words:
            # Clean word of punctuation
            clean_word = re.sub(r'[^\w\-\./]', '', word)
            if clean_word and self._is_likely_filename(clean_word):
                potential_candidates.add(clean_word)
        
        # Verify candidates actually exist in filesystem
        verified_candidates = []
        for candidate in potential_candidates:
            if self._candidate_exists_in_filesystem(candidate):
                verified_candidates.append(candidate)
                debug_log(f"Verified file candidate: {candidate}")
            else:
                debug_log(f"Rejected candidate (not found): {candidate}")
        
        return verified_candidates
    
    def _is_likely_filename(self, word: str) -> bool:
        """Check if a word is likely to be a filename"""
        # Skip common English words that are not filenames
        common_words = {
            'tell', 'me', 'about', 'what', 'is', 'the', 'this', 'that',
            'how', 'why', 'when', 'where', 'who', 'can', 'will', 'would',
            'should', 'could', 'do', 'does', 'did', 'have', 'has', 'had',
            'are', 'was', 'were', 'be', 'been', 'being', 'get', 'got',
            'make', 'made', 'take', 'took', 'come', 'came', 'go', 'went',
            'see', 'saw', 'know', 'knew', 'think', 'thought', 'say', 'said',
            'give', 'gave', 'find', 'found', 'use', 'used', 'work', 'works',
            'run', 'runs', 'ran', 'show', 'shows', 'showed', 'help', 'helps',
            'need', 'needs', 'want', 'wants', 'like', 'likes', 'look', 'looks',
            'try', 'tries', 'tried', 'start', 'starts', 'started', 'stop',
            'stops', 'stopped', 'open', 'opens', 'opened', 'close', 'closes',
            'closed', 'read', 'reads', 'write', 'writes', 'wrote', 'create',
            'creates', 'created', 'delete', 'deletes', 'deleted', 'update',
            'updates', 'updated', 'change', 'changes', 'changed', 'fix',
            'fixes', 'fixed', 'check', 'checks', 'checked', 'test', 'tests',
            'tested', 'install', 'installs', 'installed', 'remove', 'removes',
            'removed', 'add', 'adds', 'added', 'edit', 'edits', 'edited',
            'modify', 'modifies', 'modified', 'build', 'builds', 'built',
            'deploy', 'deploys', 'deployed', 'configure', 'configures', 'configured'
        }
        
        word_lower = word.lower()
        
        # Skip common words
        if word_lower in common_words:
            return False
            
        # Must have file-like characteristics
        return (
            '.' in word or  # Has extension
            '/' in word or  # Has path separator
            (len(word) > 4 and word_lower.endswith(('py', 'js', 'ts', 'go', 'rs', 'c', 'h', 'cpp', 'java', 'rb', 'php', 'sh', 'yml', 'yaml', 'json', 'xml', 'html', 'css', 'md', 'txt', 'log', 'conf', 'cfg', 'ini', 'env'))) or  # Common file endings
            (len(word) > 6 and not word_lower.isalpha())  # Long word with non-alpha chars (likely filename)
        )
    
    def _candidate_exists_in_filesystem(self, candidate: str) -> bool:
        """Check if a candidate actually exists in the filesystem"""
        try:
            # Try as-is first
            if os.path.isfile(candidate):
                return True
            
            # Try with current directory
            full_path = os.path.join(self.current_dir, candidate)
            if os.path.isfile(full_path):
                return True
            
            # For candidates without extensions, try common extensions
            if '.' not in candidate:
                common_extensions = ['.py', '.js', '.ts', '.go', '.rs', '.c', '.cpp', '.h', 
                                   '.java', '.rb', '.php', '.sh', '.yml', '.yaml', '.json', 
                                   '.xml', '.html', '.css', '.md', '.txt', '.log', '.conf', 
                                   '.cfg', '.ini', '.env']
                
                for ext in common_extensions:
                    test_path = os.path.join(self.current_dir, candidate + ext)
                    if os.path.isfile(test_path):
                        return True
            
            return False
        except Exception:
            return False
    
    async def _search_files(self, candidates: List[str]) -> List[FileMatch]:
        """Search for actual files matching the candidates"""
        matches = []
        
        for candidate in candidates:
            # Try exact match first
            exact_matches = await self._find_exact_matches(candidate)
            matches.extend(exact_matches)
            
            # Try partial matches (ignoring extensions)
            if not exact_matches:
                partial_matches = await self._find_partial_matches(candidate)
                matches.extend(partial_matches)
            
            # Try fuzzy matches if still nothing
            if not exact_matches and not partial_matches:
                fuzzy_matches = await self._find_fuzzy_matches(candidate)
                matches.extend(fuzzy_matches)
        
        # Remove duplicates and sort by confidence
        unique_matches = {}
        for match in matches:
            if match.path not in unique_matches or match.confidence > unique_matches[match.path].confidence:
                unique_matches[match.path] = match
        
        sorted_matches = sorted(unique_matches.values(), key=lambda x: x.confidence, reverse=True)
        return sorted_matches[:self.max_files]
    
    async def _find_exact_matches(self, candidate: str) -> List[FileMatch]:
        """Find exact filename matches"""
        matches = []
        
        # Try as-is
        if await self._file_exists_and_readable(candidate):
            match = await self._create_file_match(candidate, 'exact', 1.0)
            if match:
                matches.append(match)
        
        # Try with current directory
        full_path = os.path.join(self.current_dir, candidate)
        if await self._file_exists_and_readable(full_path):
            match = await self._create_file_match(full_path, 'exact', 0.9)
            if match:
                matches.append(match)
        
        return matches
    
    async def _find_partial_matches(self, candidate: str) -> List[FileMatch]:
        """Find partial matches ignoring extensions"""
        matches = []
        base_name = os.path.splitext(candidate)[0]
        
        try:
            # Use find to search for files with matching base name
            cmd = f"find {self.current_dir} -maxdepth 3 -type f -name '{base_name}*' 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            for line in result.stdout.strip().split('\n'):
                if line and await self._file_exists_and_readable(line):
                    match = await self._create_file_match(line, 'partial', 0.7)
                    if match:
                        matches.append(match)
        except subprocess.TimeoutExpired:
            debug_log(f"Timeout searching for partial matches of {candidate}")
        except Exception as e:
            debug_log(f"Error in partial search: {e}")
        
        return matches
    
    async def _find_fuzzy_matches(self, candidate: str) -> List[FileMatch]:
        """Find fuzzy matches using grep-like patterns"""
        matches = []
        
        try:
            # Use find with grep to search file contents and names
            cmd = f"find {self.current_dir} -maxdepth 2 -type f -name '*{candidate}*' 2>/dev/null | head -10"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            for line in result.stdout.strip().split('\n'):
                if line and await self._file_exists_and_readable(line):
                    match = await self._create_file_match(line, 'fuzzy', 0.5)
                    if match:
                        matches.append(match)
        except subprocess.TimeoutExpired:
            debug_log(f"Timeout searching for fuzzy matches of {candidate}")
        except Exception as e:
            debug_log(f"Error in fuzzy search: {e}")
        
        return matches
    
    async def _file_exists_and_readable(self, path: str) -> bool:
        """Check if file exists and is readable, not binary"""
        try:
            if not os.path.isfile(path):
                return False
            
            # Skip binary files
            ext = os.path.splitext(path)[1].lower()
            if ext in self.binary_extensions:
                return False
            
            # Check if file is readable
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                f.read(1)  # Try to read one character
            
            return True
        except:
            return False
    
    async def _create_file_match(self, path: str, match_type: str, confidence: float) -> Optional[FileMatch]:
        """Create a FileMatch object with metadata"""
        try:
            stat = os.stat(path)
            size = stat.st_size
            
            # Skip very large files
            if size > self.max_file_size:
                debug_log(f"Skipping large file: {path} ({size} bytes)")
                return None
            
            # Count lines for text files
            lines = 0
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = sum(1 for _ in f)
            except:
                lines = 0
            
            return FileMatch(
                path=path,
                match_type=match_type,
                confidence=confidence,
                size=size,
                lines=lines
            )
        except Exception as e:
            debug_log(f"Error creating file match for {path}: {e}")
            return None
    
    async def _inject_file_context(self, prompt: str, file_matches: List[FileMatch]) -> str:
        """Inject file content into the prompt"""
        file_contexts = []
        total_content_size = 0
        
        for match in file_matches:
            if total_content_size >= self.max_total_content:
                break
                
            content = await self._extract_file_content(match)
            if content:
                remaining_space = self.max_total_content - total_content_size
                if len(content) > remaining_space:
                    content = content[:remaining_space] + "\n... [truncated]"
                
                # Rich file context with metadata and analysis
                file_type = self._analyze_file_type(match.path)
                file_purpose = self._infer_file_purpose(match.path, content[:500])  # First 500 chars for purpose detection
                
                file_contexts.append(f"""
=== FILE ANALYSIS: {match.path} ===
📁 Type: {file_type}
🎯 Inferred Purpose: {file_purpose}
📊 Match Quality: {match.match_type} (confidence: {match.confidence:.1f})
📏 Size: {match.size} bytes ({match.lines} lines)
🔍 Discovery Method: {match.match_type}

📄 CONTENT:
{content}

=== END OF {os.path.basename(match.path).upper()} ANALYSIS ===
""")
                total_content_size += len(content)
        
        if not file_contexts:
            return prompt
        
        # Use AI to enhance the prompt for clarity (if enabled)
        if self.ai_enhance:
            enhanced_user_prompt = await self._ai_enhance_prompt(prompt, file_matches)
        else:
            enhanced_user_prompt = self._fallback_enhance_prompt(prompt, file_matches)
        
        # Inject context with the AI-enhanced prompt
        enhanced_prompt = f"""FILE CONTEXT:
The following files are relevant to the user's request:

{''.join(file_contexts)}

USER REQUEST (AI-Enhanced for Clarity):
{enhanced_user_prompt}

Please provide a comprehensive response based on the file content above. If you provide commands, format them as:
awesh: <command>"""
        
        debug_log(f"Enhanced prompt with {len(file_matches)} files, {total_content_size} chars of content")
        return enhanced_prompt
    
    async def _ai_enhance_prompt(self, original_prompt: str, file_matches: List[FileMatch]) -> str:
        """Use AI to enhance the user's prompt for better clarity and specificity"""
        try:
            # Import AI client here to avoid circular imports
            from .ai_client import AweshAIClient
            from .config import Config
            
            # Create a lightweight AI client for prompt enhancement
            config = Config()
            ai_client = AweshAIClient(config)
            await ai_client.initialize()
            
            file_names = [os.path.basename(match.path) for match in file_matches]
            file_list = ", ".join(file_names)
            
            enhancement_prompt = f"""You are an expert file analysis assistant. Your job is to transform user requests about files into comprehensive, specific instructions that will produce the most helpful response possible.

Original user request: "{original_prompt}"
Files involved: {file_list}

Transform this into a detailed, specific request that:
1. Clearly states what the user wants to achieve with these files
2. Specifies the type and depth of analysis needed
3. Requests actionable insights, explanations, or commands
4. Considers the file's role in the broader project context
5. Asks for both immediate understanding and practical next steps

Examples of transformations:
- "tell me about setup.py" → "Provide a comprehensive analysis of setup.py: explain its purpose in the Python packaging system, break down each configuration section (dependencies, entry points, metadata), identify any potential issues or improvements, and explain how this setup relates to the overall project structure and deployment process"

- "fix config" → "Thoroughly analyze config.py for potential issues: check for security vulnerabilities, configuration errors, missing error handling, inefficient patterns, and compatibility issues. Provide specific fixes with exact code examples, explain the reasoning behind each fix, and suggest best practices for configuration management"

- "update main" → "Review main.py comprehensively: analyze the current architecture and flow, identify areas for improvement (performance, maintainability, error handling), suggest specific modernizations or refactoring opportunities with exact code changes, and recommend testing strategies for the updates"

- "run tests" → "Analyze the test files to understand the testing strategy, explain how to execute the tests, identify any missing test coverage, suggest improvements to the test suite, and provide commands to run tests with proper reporting"

Create a rich, detailed prompt that will help the user truly understand and work effectively with their files:"""

            # Get AI enhancement
            enhanced_response = ""
            async for chunk in ai_client.process_prompt(enhancement_prompt):
                enhanced_response += chunk
            
            # Clean up the response
            enhanced_response = enhanced_response.strip()
            
            # If AI enhancement worked, use it; otherwise fall back to original + analysis
            if enhanced_response and len(enhanced_response) > len(original_prompt) * 0.8:
                debug_log(f"AI enhanced prompt: '{original_prompt}' → '{enhanced_response[:100]}...'")
                return enhanced_response
            else:
                debug_log("AI enhancement failed, using fallback enhancement")
                return self._fallback_enhance_prompt(original_prompt, file_matches)
                
        except Exception as e:
            debug_log(f"AI prompt enhancement failed: {e}, using fallback")
            return self._fallback_enhance_prompt(original_prompt, file_matches)
    
    def _fallback_enhance_prompt(self, original_prompt: str, file_matches: List[FileMatch]) -> str:
        """Fallback prompt enhancement when AI enhancement fails"""
        file_names = [os.path.basename(match.path) for match in file_matches]
        file_list = ", ".join(file_names)
        
        # Use the existing intent analysis as fallback
        intent_context = self._analyze_user_intent(original_prompt, file_matches)
        action_guidance = self._get_action_guidance(original_prompt)
        
        return f"{original_prompt}\n\nSpecifically: {intent_context.lower()} Please {action_guidance}."
    
    def _analyze_user_intent(self, prompt: str, file_matches: List[FileMatch]) -> str:
        """Analyze what the user wants to do with the files"""
        prompt_lower = prompt.lower()
        file_names = [os.path.basename(match.path) for match in file_matches]
        file_list = ", ".join(file_names)
        
        # Detect different types of intent
        if any(word in prompt_lower for word in ['explain', 'what does', 'what is', 'describe', 'tell me about']):
            return f"The user wants to understand what {file_list} does. Provide a clear explanation of the file's purpose, functionality, and key components."
        elif any(word in prompt_lower for word in ['fix', 'debug', 'error', 'bug', 'problem', 'issue']):
            return f"The user wants to fix or debug issues in {file_list}. Analyze the code for potential problems and suggest solutions."
        elif any(word in prompt_lower for word in ['update', 'modify', 'change', 'edit', 'add', 'remove']):
            return f"The user wants to modify {file_list}. Understand the current implementation and suggest specific changes."
        elif any(word in prompt_lower for word in ['run', 'execute', 'test', 'build', 'install']):
            return f"The user wants to run or execute something related to {file_list}. Provide the appropriate commands."
        elif any(word in prompt_lower for word in ['improve', 'optimize', 'refactor', 'enhance']):
            return f"The user wants to improve {file_list}. Analyze the code and suggest optimizations or refactoring."
        else:
            return f"The user is asking about {file_list}. Analyze the file content and provide helpful insights or actions."
    
    def _get_action_guidance(self, prompt: str) -> str:
        """Get specific guidance for what the AI should do"""
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ['explain', 'what does', 'what is', 'describe', 'tell me about']):
            return "explain the purpose, structure, and functionality of the file(s). Don't just show the content - analyze and describe what it does"
        elif any(word in prompt_lower for word in ['fix', 'debug', 'error', 'bug']):
            return "identify potential issues in the code and provide specific fixes or debugging steps"
        elif any(word in prompt_lower for word in ['update', 'modify', 'change', 'edit']):
            return "suggest specific modifications to the file(s) with exact code changes"
        elif any(word in prompt_lower for word in ['run', 'execute', 'test', 'build']):
            return "provide the exact commands needed to run, test, or build based on the file content"
        elif any(word in prompt_lower for word in ['improve', 'optimize', 'refactor']):
            return "analyze the code and suggest specific improvements or refactoring opportunities"
        else:
            return "provide actionable insights, explanations, or commands based on the file content"
    
    def _analyze_file_type(self, file_path: str) -> str:
        """Analyze and categorize the file type with rich context"""
        ext = os.path.splitext(file_path)[1].lower()
        basename = os.path.basename(file_path).lower()
        
        # Configuration files
        if basename in ['config.py', 'settings.py', 'config.yml', 'config.yaml', '.env', 'config.ini']:
            return "Configuration File - Controls application behavior and settings"
        elif ext in ['.ini', '.conf', '.cfg', '.toml'] or 'config' in basename:
            return "Configuration File - System or application configuration"
        
        # Build and deployment files  
        elif basename in ['setup.py', 'pyproject.toml', 'requirements.txt', 'package.json', 'cargo.toml', 'go.mod']:
            return "Build/Package Definition - Defines dependencies and build process"
        elif basename in ['dockerfile', 'docker-compose.yml', 'makefile']:
            return "Build/Deployment Script - Automates build and deployment processes"
        
        # Entry points and main files
        elif basename in ['main.py', '__main__.py', 'app.py', 'server.py', 'index.js', 'main.go', 'main.rs']:
            return "Application Entry Point - Main executable or server entry point"
        
        # Test files
        elif 'test' in basename or basename.startswith('test_') or ext == '.test':
            return "Test File - Contains automated tests for code validation"
        
        # Documentation
        elif ext in ['.md', '.rst', '.txt'] and ('readme' in basename or 'doc' in basename):
            return "Documentation - Project information and usage instructions"
        
        # Source code by language
        elif ext == '.py':
            return "Python Source Code - Python module or script"
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            return "JavaScript/TypeScript Source - Web application code"
        elif ext in ['.go']:
            return "Go Source Code - Go programming language module"
        elif ext in ['.rs']:
            return "Rust Source Code - Rust programming language module"
        elif ext in ['.c', '.cpp', '.h', '.hpp']:
            return "C/C++ Source Code - System-level programming code"
        elif ext in ['.java']:
            return "Java Source Code - Java programming language class"
        elif ext in ['.rb']:
            return "Ruby Source Code - Ruby programming language script"
        elif ext in ['.php']:
            return "PHP Source Code - Server-side web programming script"
        elif ext in ['.sh', '.bash']:
            return "Shell Script - Command-line automation script"
        
        # Data and config formats
        elif ext in ['.json']:
            return "JSON Data - Structured data interchange format"
        elif ext in ['.yml', '.yaml']:
            return "YAML Configuration - Human-readable data serialization"
        elif ext in ['.xml']:
            return "XML Data - Markup language for structured data"
        elif ext in ['.csv']:
            return "CSV Data - Comma-separated values data file"
        
        # Web files
        elif ext in ['.html', '.htm']:
            return "HTML Document - Web page markup"
        elif ext in ['.css', '.scss', '.sass']:
            return "Stylesheet - Web page styling definitions"
        
        # Logs and temporary
        elif ext in ['.log']:
            return "Log File - Application or system event log"
        elif ext in ['.tmp', '.temp']:
            return "Temporary File - Temporary data storage"
        
        else:
            return f"File ({ext or 'no extension'}) - General purpose file"
    
    def _infer_file_purpose(self, file_path: str, content_preview: str) -> str:
        """Infer the specific purpose of the file from its content"""
        basename = os.path.basename(file_path).lower()
        content_lower = content_preview.lower()
        
        # Specific file patterns
        if basename == 'setup.py':
            if 'setuptools' in content_lower:
                return "Python package setup and distribution configuration"
            else:
                return "Python project setup script"
        
        elif basename in ['config.py', 'settings.py']:
            if 'database' in content_lower:
                return "Database and application configuration settings"
            elif 'api' in content_lower:
                return "API configuration and service settings"
            else:
                return "Application configuration and environment settings"
        
        elif basename == 'main.py':
            if 'flask' in content_lower or 'app.run' in content_lower:
                return "Flask web application entry point"
            elif 'fastapi' in content_lower:
                return "FastAPI web service entry point"
            elif 'asyncio' in content_lower:
                return "Asynchronous Python application entry point"
            elif 'argparse' in content_lower:
                return "Command-line application entry point"
            else:
                return "Python application main execution entry point"
        
        elif basename == 'server.py':
            if 'socket' in content_lower:
                return "Network server implementation with socket communication"
            elif 'http' in content_lower or 'web' in content_lower:
                return "HTTP web server implementation"
            else:
                return "Server application core logic"
        
        elif 'test' in basename:
            if 'unittest' in content_lower:
                return "Unit tests using Python unittest framework"
            elif 'pytest' in content_lower:
                return "Unit tests using pytest framework"
            else:
                return "Automated test suite for code validation"
        
        elif basename == 'dockerfile':
            return "Container image build instructions and environment setup"
        
        elif basename == 'requirements.txt':
            return "Python package dependencies and version specifications"
        
        elif basename.endswith('.md'):
            if 'readme' in basename:
                return "Project documentation, setup instructions, and usage guide"
            else:
                return "Documentation and project information"
        
        # Content-based inference
        elif 'class ' in content_lower and 'def ' in content_lower:
            return "Object-oriented code with class definitions and methods"
        elif 'function' in content_lower or 'def ' in content_lower:
            return "Function definitions and procedural code logic"
        elif 'import ' in content_lower:
            return "Module with external dependencies and library usage"
        elif 'api' in content_lower and ('endpoint' in content_lower or 'route' in content_lower):
            return "API endpoint definitions and request handling"
        elif 'database' in content_lower or 'sql' in content_lower:
            return "Database interaction and data management code"
        
        else:
            return "General purpose code or data file"
    
    async def _extract_file_content(self, match: FileMatch) -> str:
        """Extract relevant content from a file"""
        try:
            with open(match.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # For small files, return everything
            if len(content) <= 2000:
                return content
            
            # For larger files, use smart extraction
            lines = content.split('\n')
            
            # If file has many lines, show head + tail + middle sample
            if len(lines) > 100:
                head = '\n'.join(lines[:20])
                tail = '\n'.join(lines[-10:])
                middle_start = len(lines) // 2 - 5
                middle = '\n'.join(lines[middle_start:middle_start + 10])
                
                return f"""{head}

... [showing lines {middle_start + 1}-{middle_start + 10} of {len(lines)}] ...
{middle}

... [showing last 10 lines] ...
{tail}"""
            else:
                # Medium files - show more content
                return content[:3000] + ("\n... [truncated]" if len(content) > 3000 else "")
                
        except Exception as e:
            debug_log(f"Error reading file {match.path}: {e}")
            return f"[Error reading file: {e}]"
