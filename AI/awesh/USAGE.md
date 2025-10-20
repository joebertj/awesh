# awesh Usage Guide

## Quick Start

1. **Install awesh**:
   ```bash
   cd awesh/
   ./install.sh
   ```

2. **Configure your API key** using environment variables:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   export OPENAI_MODEL=gpt-5
   ```

3. **Run awesh**:
   ```bash
   awesh
   ```

## Basic Usage

awesh automatically detects whether your input should go to AI or Bash:

```bash
awesh> ls -la                           # → Bash execution
awesh> what files are here?             # → AI analysis  
awesh> find . -name "*.py"              # → Bash execution
awesh> explain this error message       # → AI interpretation
awesh> cd /var/log && analyze errors    # → Bash + AI
```

## Configuration

### Environment Variables

Set these environment variables in your shell:

```bash
# Required
export OPENAI_API_KEY=your_api_key_here

# Optional
export OPENAI_MODEL=gpt-5                      # AI model to use
export VERBOSE=1                               # 0=silent, 1=show AI status+debug, 2+=more verbose
```

### System Prompt

Customize AI behavior by editing `~/.awesh_system.txt`. The default prompt is optimized for operations and infrastructure management.

### Command Line Options

```bash
awesh --help                            # Show all options
awesh --model gpt-4                     # Override model
awesh --no-stream                       # Disable streaming
awesh --config /path/to/config          # Custom config file
awesh --dry-run-tools                   # Enable dry-run mode
```

## Smart Command Routing

awesh uses intelligent routing to decide between AI and Bash:

### Bash Execution Triggers
- Known shell commands (`ls`, `grep`, `find`, etc.)
- Shell syntax (`|`, `>`, `&&`, `$()`, etc.)
- Environment variables (`$HOME`, `${VAR}`)
- Glob patterns (`*.txt`, `[a-z]*`)
- Command assignments (`VAR=value`)

### AI Processing Triggers
- Natural language questions
- Requests for explanations
- Analysis requests
- Troubleshooting queries
- "How to" questions

## AI Features

### Context Awareness
The AI knows:
- Your current working directory
- Your last executed command
- Exit codes from recent commands

### Operations Focus
The default system prompt provides:
- System administration guidance
- Infrastructure troubleshooting help
- Security best practices
- Performance optimization suggestions
- Safety warnings for destructive operations

### Example AI Interactions

```bash
# System monitoring
awesh> check system health
awesh> what's using the most CPU?
awesh> analyze disk space usage

# Troubleshooting  
awesh> why is this service failing?
awesh> debug network connectivity issues
awesh> interpret these log errors

# Best practices
awesh> secure way to delete these files
awesh> backup strategy for this directory
awesh> performance tune this database
```

## Built-in Commands

awesh provides several built-in commands:

- `exit` - Quit awesh
- `pwd` - Show current directory
- `cd` - Change directory (with tab completion)

All other commands are routed to Bash or AI based on content detection.

## Tips & Best Practices

1. **Be specific with AI queries**: "Check disk space on /var partition" vs "check disk space"

2. **Use context**: The AI remembers your recent commands and current directory

3. **Safety first**: The AI will warn about potentially destructive operations

4. **Mix freely**: You can seamlessly switch between Bash commands and AI queries

5. **Customize the system prompt**: Edit `~/.awesh_system.txt` for domain-specific behavior

## Troubleshooting

### AI Not Working
- Check `OPENAI_API_KEY` in `~/.aweshrc`
- Verify API key has sufficient credits
- For GPT-5: Organization verification may be required for streaming

### Import Errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Try reinstalling: `./install.sh`

### Permission Issues
- Check file permissions on `~/.aweshrc` and `~/.awesh_system.txt`
- Ensure awesh binary is executable

## Advanced Configuration

### Custom System Prompts
Create specialized prompts for different use cases:

```bash
# For development work
cp ~/.awesh_system.txt ~/.awesh_dev.txt
# Edit for development-specific guidance

# Use with:
awesh --system-prompt ~/.awesh_dev.txt
```

### Integration with Tools
awesh works well with:
- tmux/screen sessions
- SSH connections  
- Container environments
- CI/CD pipelines
- Monitoring dashboards

## Philosophy

awesh embodies "AI is baseline + human creativity":
- AI provides superior foundational capabilities
- Human creativity pushes beyond training data limitations  
- The combination creates tools that transcend what either could achieve alone

Use AI as your baseline, then push further with creative problem-solving that goes beyond what the training data anticipated.
