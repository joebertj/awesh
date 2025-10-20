"""
Configuration management for awesh
"""

import os
import configparser
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration settings for awesh"""
    
    # AI Model settings
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 2000
    streaming: bool = True
    
    # File paths
    system_prompt_path: str = "~/.awesh_system.txt"
    mcp_server_path: str = "mcp_server"
    policy_path: str = "~/.awesh_policy.yaml"
    history_file: str = "~/.awesh_history"
    
    # Shell settings
    prompt_label: str = "awesh> "
    multiline_enabled: bool = False
    
    # Security settings
    audit_log_enabled: bool = False
    audit_log_path: str = "~/.awesh_audit.jsonl"
    dry_run_tools: bool = False
    
    # WSL settings
    use_linux_paths: bool = True
    
    @classmethod
    def load(cls, config_path: Path) -> 'Config':
        """Load configuration from file and environment variables"""
        config = cls()
        
        # Load from ~/.aweshrc if it exists (simple key=value format)
        aweshrc_path = Path.home() / '.aweshrc'
        if aweshrc_path.exists():
            # Parse key=value pairs manually
            try:
                with open(aweshrc_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            except Exception as e:
                print(f"Warning: Could not parse {aweshrc_path}: {e}")
        
        # Override model from environment variable if set
        if os.getenv('MODEL'):
            config.model = os.getenv('MODEL')
        
        if not config_path.exists():
            # Create default config file
            config.save(config_path)
            return config
            
        # Try to parse configuration file
        # First check if it's a simple key=value format or INI format
        try:
            with open(config_path, 'r') as f:
                first_line = f.readline().strip()
                
            if first_line and '=' in first_line and not first_line.startswith('['):
                # Simple key=value format - already loaded by dotenv above
                return config
            else:
                # INI format - use configparser
                parser = configparser.ConfigParser()
                parser.read(config_path)
        except Exception as e:
            print(f"Warning: Could not read config file {config_path}: {e}")
            return config
        
        # AI settings
        if parser.has_section('ai'):
            ai_section = parser['ai']
            config.model = ai_section.get('model', config.model)
            config.temperature = ai_section.getfloat('temperature', config.temperature)
            config.max_tokens = ai_section.getint('max_tokens', config.max_tokens)
            config.streaming = ai_section.getboolean('streaming', config.streaming)
            
        # Paths
        if parser.has_section('paths'):
            paths_section = parser['paths']
            config.system_prompt_path = paths_section.get('system_prompt_path', config.system_prompt_path)
            config.mcp_server_path = paths_section.get('mcp_server_path', config.mcp_server_path)
            config.policy_path = paths_section.get('policy_path', config.policy_path)
            config.history_file = paths_section.get('history_file', config.history_file)
            
        # Shell settings
        if parser.has_section('shell'):
            shell_section = parser['shell']
            config.prompt_label = shell_section.get('prompt_label', config.prompt_label)
            config.multiline_enabled = shell_section.getboolean('multiline_enabled', config.multiline_enabled)
            
        # Security settings
        if parser.has_section('security'):
            security_section = parser['security']
            config.audit_log_enabled = security_section.getboolean('audit_log_enabled', config.audit_log_enabled)
            config.audit_log_path = security_section.get('audit_log_path', config.audit_log_path)
            config.dry_run_tools = security_section.getboolean('dry_run_tools', config.dry_run_tools)
            
        return config
    
    def save(self, config_path: Path) -> None:
        """Save configuration to file"""
        parser = configparser.ConfigParser()
        
        # AI settings
        parser['ai'] = {
            'model': self.model,
            'temperature': str(self.temperature),
            'max_tokens': str(self.max_tokens),
            'streaming': str(self.streaming).lower()
        }
        
        # Paths
        parser['paths'] = {
            'system_prompt_path': self.system_prompt_path,
            'mcp_server_path': self.mcp_server_path,
            'policy_path': self.policy_path,
            'history_file': self.history_file
        }
        
        # Shell settings
        parser['shell'] = {
            'prompt_label': self.prompt_label,
            'multiline_enabled': str(self.multiline_enabled).lower()
        }
        
        # Security settings
        parser['security'] = {
            'audit_log_enabled': str(self.audit_log_enabled).lower(),
            'audit_log_path': self.audit_log_path,
            'dry_run_tools': str(self.dry_run_tools).lower()
        }
        
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration file
        with open(config_path, 'w') as f:
            parser.write(f)
    
    def get_expanded_path(self, path_str: str) -> Path:
        """Get expanded path from config string"""
        return Path(path_str).expanduser().resolve()
    
    @property 
    def system_prompt_file(self) -> Path:
        """Get expanded system prompt file path"""
        return self.get_expanded_path(self.system_prompt_path)
    
    @property
    def mcp_server_file(self) -> Path:
        """Get expanded MCP server path"""
        return self.get_expanded_path(self.mcp_server_path)
    
    @property
    def policy_file(self) -> Path:
        """Get expanded policy file path"""
        return self.get_expanded_path(self.policy_path)
    
    @property
    def history_file_path(self) -> Path:
        """Get expanded history file path"""
        return self.get_expanded_path(self.history_file)
    
    @property
    def audit_log_file(self) -> Path:
        """Get expanded audit log file path"""
        return self.get_expanded_path(self.audit_log_path)
