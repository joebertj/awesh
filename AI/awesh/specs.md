Product name & intent

Name: awesh

Acronym: Awe-Inspired Workspace Environment Shell

Type: AI-aware interactive shell

Philosophy: “AI by default, Bash when I mean Bash.”

Goal: Replace bloated IDE agents. Keep edit flow in vi; awesh is the conversation + command runner with strict guardrails (MCP).

Core behavior (routing rule)

Default: Any input line is treated as an AI prompt and sent to the model.

Override to Bash: If the line is detected as a shell command, it MUST execute as a Bash command instead of going to AI.

Detection:

If the first token is recognized by Bash as a command/builtin/alias/function, it is a Bash line.

If the line contains typical shell syntax (pipes, redirects, backgrounding, subshells, env refs, globs, assignments, command substitution), it is a Bash line.

Never send Bash lines to the model.

Minimal builtins handled by awesh itself: cd, pwd, exit. These affect awesh’s own process state (e.g., current working directory) and MUST NOT be delegated to Bash or the model.

AI interaction (no hidden prompts)

System prompt ownership: All system instructions live in a plain text file under your repo or home (e.g., “awesh_system.txt”). The IDE must not inject or modify it.

Conversation model: Single-turn by default; multi-turn only when explicitly enabled per session.

Tools exposure: The only tool exposed to the model is a single “mcp_call” that forwards to your MCP server. No other tools, web, or file I/O are available to the model directly.

Streaming: Model responses should stream to the terminal by default.

Safety: If the model attempts to call a non-declared tool or requests a raw shell, return a clear refusal message and do nothing.

MCP contract (tool gateway)

Single tool name: “mcp_call”.

Inputs: two fields — a tool name (string) and parameters (object).
Examples of tool names you will support: list_dir, read_file, git_status, git_diff, run.

Outputs: an object with either { ok: true, result: … } or { ok: false, error: { code, message } }.

Policy enforcement: The MCP server enforces command allow-lists, path allow-lists, timeouts, CPU/memory limits, output truncation, and optional dry-run for destructive verbs.

Transport: stdin/stdout JSON to a local MCP process. No network calls from the IDE to the MCP (awesh launches/subprocesses it locally).

Bash integration

Command resolution: Use Bash’s own command resolution to decide whether the first token is a Bash command.

Persistent state: For v1, only cd persists in the awesh process. All other Bash state (aliases, exported vars) can live in the transient Bash call and does not need to persist between lines. A later enhancement may keep a persistent interactive Bash child process to preserve alias/export state if requested.

Working directory: The current working directory is managed by awesh (via the cd builtin). All Bash executions and MCP tool calls inherit awesh’s cwd.

WSL & environment

Primary runtime: WSL (Ubuntu).

Interpreter: Python 3.11+ venv under the project directory, and all tools installed there.

Pathing: Any file dialogs or path rendering should use native Linux paths; UNC browsing is optional for Windows GUIs but not required for awesh.

Configuration files & locations

awesh config: ~/.aweshrc (human-readable; recommend simple key = value lines or TOML).

Keys: model, temperature, max_tokens, system_prompt_path, mcp_server_path, policy_path, streaming (on/off).

Keys for WSL path preferences if needed.

System prompt: path set in config; awesh must read exactly that file, unmodified.

Policy file for MCP: path set in config (e.g., “policy.yaml”).

History file: ~/.awesh_history (line input history only; never log secrets).

Security & privacy requirements

No shell execution from the model. Only MCP tools are callable.

No environment variable leakage to the model. Only send tool results.

Audit log (optional, configurable): A JSON-lines log per session with timestamp, input type (bash or ai), tool calls (name + redacted params), result codes, durations. Never log full command outputs unless explicitly enabled.

Network egress: AI API calls only. MCP tools default to no outbound network unless the policy allow-lists hosts.

Error handling (UX)

Bash failures: Show standard stderr and exit code. Do not fallback to AI.

AI failures (rate limit, auth, timeout): Show a single-line concise reason; do not reroute to Bash.

MCP errors: If ok: false, show the MCP error code/message. Do not retry automatically unless configured.

Ambiguous line (can’t parse tokens): Treat as AI prompt and display a one-line note: “Parsed as prompt.”

Terminal UX & key behaviors

Prompt label: “awesh> ” by default (configurable).

Editing: Standard line editing, history up/down, Ctrl-C cancels the current operation (Bash or AI) without exiting awesh.

Multiline: Optional. If enabled, Shift-Enter inserts a newline for AI prompts; Bash lines remain single-line unless explicit continuation characters are present.

Copy/paste: Plain text. No markup.

Colors: Minimal; reserved for error messages and subtle model/batch markers.

Performance targets

Cold start: under 500 ms to first prompt in a warmed Python venv.

Bash command dispatch: same feel as a typical shell; overhead under ~30 ms per run.

AI streaming onset: first tokens visible within ~1 second after sending to the model (network permitting).

MCP tool latency: bounded by policy timeouts; default max 10 seconds per tool call.

Determinism & repeatability

Model settings: Temperature and model must be fixed by config unless overridden per call.

Tool schemas: Document names and parameter shapes for each MCP tool; awesh must reject model calls to tools not declared.

No implicit retries: Retries only on explicit configuration.

Minimal command set (initial)

Builtins: cd [dir], pwd, exit.

Everything else: routed by the Bash/AI decision rule above.

Escape hatch (optional for later): a prefix character (e.g., a single bang) that forces Bash even if the heuristic would choose AI, and another that forces AI even if the line looks like shell; disabled by default unless explicitly requested.

Test plan (acceptance)

Routing tests:

“ls -la” → must run in Bash.

“summarize this directory’s structure” → must go to AI; if AI calls list_dir, MCP returns structured entries and the model summarizes.

“cat file.txt | grep foo” → must run in Bash (pipes detected).

“ruff check . --fix” → Bash (first token is an executable).

“why did ruff change these lines?” → AI.

Builtin tests:

“cd /tmp” then “pwd” → prints “/tmp”.

“exit” → terminates awesh gracefully.

Failure tests:

Invalid Bash command → shows “command not found” with exit code, no AI fallback.

MCP disallowed command → returns a clear policy error.

API key missing → concise error, no crash.

Config tests:

Changing system prompt path updates behavior immediately on next prompt.

Toggling streaming reflects in output style.

Deliverables to implement

Interactive CLI app “awesh” (Python runtime), installable into a venv and runnable from PATH.

Config reader for ~/.aweshrc.

Router that applies the Bash/AI decision rule exactly as specified.

Bash executor (non-persistent for v1).

AI client wrapper honoring your system prompt and exposing only the single “mcp_call” tool.

MCP call adapter to spawn your MCP server process and pass structured requests/responses.

Minimal help message: how routing works, how to configure, where logs are.

Option flags: --config, --no-stream, --model, --dry-run-tools (maps to MCP dry-run).

Non-goals (v1)

Full POSIX job control (fg/bg), persistent Bash session, aliases/functions persistence, tab-completion of commands, and plugins. These can be slated for v1.x once the core flow is stable.
