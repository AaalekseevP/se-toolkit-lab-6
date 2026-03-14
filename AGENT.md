# Agent

A CLI agent that connects to an LLM and answers questions using tools to navigate the project wiki.

## Architecture

### Components

- **`agent.py`**: Main CLI entry point with agentic loop
- **`.env.agent.secret`**: Environment configuration for LLM access
- **Tools**: `read_file` and `list_files` for navigating the project repository

### LLM Provider

**Provider:** Qwen Code API

**Model:** `qwen3-coder-plus`

The agent uses an OpenAI-compatible API endpoint to communicate with the LLM.

### Tools

The agent has two tools for navigating the project wiki:

#### `read_file`

Reads the contents of a file from the project repository.

- **Parameter:** `path` (string) — Relative path from project root (e.g., `wiki/git-workflow.md`)
- **Returns:** File contents as a string, or an error message
- **Security:** Rejects absolute paths, path traversal (`..`), and paths outside the project directory

#### `list_files`

Lists files and directories in a directory.

- **Parameter:** `path` (string) — Relative directory path from project root (e.g., `wiki`)
- **Returns:** Newline-separated listing of entries, or an error message
- **Security:** Rejects absolute paths, path traversal (`..`), and paths outside the project directory

### Agentic Loop

The agent uses an iterative loop to answer questions:

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                         │
                         no
                         │
                         ▼
                    JSON output
```

1. **Send to LLM:** The user's question and tool definitions are sent to the LLM
2. **Check for tool calls:**
   - If `tool_calls` present → execute each tool, append results as `tool` role messages, go to step 1
   - If no `tool_calls` → extract final answer, output JSON and exit
3. **Limit:** Maximum 10 tool calls per question

### System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to read relevant files and find answers
3. Always cite sources with file path and section anchor (e.g., `wiki/git-workflow.md#resolving-merge-conflicts`)
4. Be concise and accurate

### Data Flow

```
User question (CLI argument)
    ↓
agent.py (parses input, initializes agentic loop)
    ↓
HTTP POST to LLM API (with tool definitions)
    ↓
LLM response (with or without tool_calls)
    ↓
If tool_calls: execute tools → append results → repeat
If no tool_calls: extract answer and source
    ↓
JSON output: {"answer": "...", "source": "...", "tool_calls": [...]}
```

## Setup

### 1. Configure LLM Access

Copy the environment template and fill in your credentials:

```bash
cp .env.agent.example .env.agent.secret
```

Edit `.env.agent.secret`:

```bash
# Your LLM provider API key
LLM_API_KEY=your-api-key-here

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://<your-vm-ip>:<qwen-api-port>/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

### 2. Run the Agent

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

## Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Source reference (e.g., `wiki/git-workflow.md#section-name`) |
| `tool_calls` | array | All tool calls made during the agentic loop |

Each `tool_calls` entry contains:
- `tool`: Tool name (`read_file` or `list_files`)
- `args`: Arguments passed to the tool
- `result`: Tool execution result

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for LLM provider | `sk-...` |
| `LLM_API_BASE` | Base URL of OpenAI-compatible endpoint | `http://192.168.1.100:8080/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

## Dependencies

- `httpx`: HTTP client for API requests
- `python-dotenv`: Environment variable loading

## Error Handling

- **Timeout:** 60 seconds for API requests
- **Max tool calls:** 10 tool calls per question
- **Path security:** Rejects paths outside project directory
- **Output:** All debug output goes to stderr; only valid JSON goes to stdout
- **Exit codes:** 0 on success, non-zero on failure
