#!/usr/bin/env python3
"""
Model switching utility for awesh
"""

import os
import sys
from pathlib import Path

def get_config_path():
    """Get the path to the awesh config file"""
    home = Path.home()
    return home / '.aweshrc'

def load_config():
    """Load current configuration"""
    config_path = get_config_path()
    config = {}
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config

def save_config(config):
    """Save configuration to file"""
    config_path = get_config_path()
    
    with open(config_path, 'w') as f:
        f.write("# awesh configuration file\n\n")
        f.write("# Verbose level: 0 = silent, 1 = normal, 2 = debug\n")
        f.write("VERBOSE=0\n\n")
        
        # AI Provider and Model
        f.write(f"# Default to OpenRouter with Mistral\n")
        f.write(f"AI_PROVIDER={config.get('AI_PROVIDER', 'openrouter')}\n")
        f.write(f"MODEL={config.get('MODEL', 'mistralai/mistral-small-3.1-24b-instruct:free')}\n\n")
        
        # API Keys
        if 'OPENROUTER_API_KEY' in config:
            f.write(f"# OpenRouter API key\n")
            f.write(f"OPENROUTER_API_KEY={config['OPENROUTER_API_KEY']}\n\n")
        
        if 'OPENAI_API_KEY' in config:
            f.write(f"# OpenAI API key (fallback for free models)\n")
            f.write(f"OPENAI_API_KEY={config['OPENAI_API_KEY']}\n\n")
        
        if 'OPENAI_FREE_MODEL' in config:
            f.write(f"# Free OpenAI model as fallback\n")
            f.write(f"OPENAI_FREE_MODEL={config['OPENAI_FREE_MODEL']}\n")

def switch_to_openrouter_mistral():
    """Switch to OpenRouter with Mistral"""
    config = load_config()
    config['AI_PROVIDER'] = 'openrouter'
    config['MODEL'] = 'mistralai/mistral-small-3.1-24b-instruct:free'
    save_config(config)
    print("✅ Switched to OpenRouter with Mistral (free)")

def switch_to_openai_free():
    """Switch to OpenAI free model"""
    config = load_config()
    config['AI_PROVIDER'] = 'openai'
    config['MODEL'] = 'gpt-3.5-turbo'
    save_config(config)
    print("✅ Switched to OpenAI gpt-3.5-turbo (free)")

def show_current_config():
    """Show current configuration"""
    config = load_config()
    print("Current awesh configuration:")
    print(f"  AI Provider: {config.get('AI_PROVIDER', 'not set')}")
    print(f"  Model: {config.get('MODEL', 'not set')}")
    print(f"  OpenRouter API Key: {'✅ Set' if 'OPENROUTER_API_KEY' in config else '❌ Not set'}")
    print(f"  OpenAI API Key: {'✅ Set' if 'OPENAI_API_KEY' in config else '❌ Not set'}")

def main():
    if len(sys.argv) < 2:
        print("awesh model switcher")
        print("Usage:")
        print("  python3 switch_model.py mistral    - Switch to OpenRouter Mistral (free)")
        print("  python3 switch_model.py openai     - Switch to OpenAI gpt-3.5-turbo (free)")
        print("  python3 switch_model.py status     - Show current configuration")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'mistral':
        switch_to_openrouter_mistral()
    elif command == 'openai':
        switch_to_openai_free()
    elif command == 'status':
        show_current_config()
    else:
        print(f"Unknown command: {command}")
        print("Use 'mistral', 'openai', or 'status'")

if __name__ == '__main__':
    main()
