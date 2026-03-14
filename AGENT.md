# Agent

A CLI agent that connects to an LLM and answers questions using tools to navigate the project wiki, read source code, and query the running backend API.

## Architecture

### Components

- **`agent.py`**: Main CLI entry point with agentic loop
- **`.env.agent.secret`**: Environment configuration for LLM access
- **`.env.docker.secret`**: Environment configuration for backend API access
- **Tools**: `read_file`, `list_files`, and `query_api` for interacting with the system

### LLM Provider

**Provider:** Qwen Code API

**Model:** `qwen3-coder-plus`

The agent uses an OpenAI-compatible API endpoint to communicate with the LLM.

### Tools

The agent has three tools for navigating the project and querying the system:

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

#### `query_api`

Queries the deployed backend API with Bearer token authentication.

- **Parameters:**
  - `method` (string) — HTTP method (GET, POST, PUT, DELETE, PATCH)
  - `path` (string) — API path (e.g., `/items/`, `/analytics/completion-rate`)
  - `body` (string, optional) — JSON request body for POST/PUT/PATCH requests
  - `auth` (boolean, default: true) — Whether to include authentication header
- **Returns:** JSON string with `status_code` and `body`, or an error message
- **Authentication:** Uses `LMS_API_KEY` from environment variables

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

1. Use `list_files` to discover wiki files or source code directories
2. Use `read_file` to read relevant files and find answers
3. Use `query_api` for data-dependent questions, status code checks, or bug diagnosis
4. For bug diagnosis: first reproduce the error with `query_api`, then read the source code with `read_file`
5. Always cite sources with file path and section anchor (e.g., `wiki/git-workflow.md#resolving-merge-conflicts` or `backend/app/routers/analytics.py#get_completion_rate`)
6. Be concise and accurate

### Tool Selection Guidance

The LLM decides which tool to use based on the question type:

| Question Type | Example | Expected Tool(s) |
|--------------|---------|------------------|
| Documentation lookup | "How do I protect a branch?" | `list_files`, `read_file` |
| Source code inspection | "What framework does the backend use?" | `list_files`, `read_file` |
| Data-dependent query | "How many items are in the database?" | `query_api` |
| Status code check | "What status code for unauthenticated request?" | `query_api` (with `auth: false`) |
| Bug diagnosis | "Why does /analytics/completion-rate crash?" | `query_api`, then `read_file` |
| Architecture reasoning | "Explain the request lifecycle" | `read_file` (multiple files) |

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
LLM_API_KEY=your-llm-api-key-here

# API base URL (OpenAI-compatible endpoint)
LLM_API_BASE=http://<your-vm-ip>:<qwen-api-port>/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

### 2. Configure Backend API Access

The backend API key is stored in `.env.docker.secret`:

```bash
# Secret key used to authorize in the backend LMS API
LMS_API_KEY=your-backend-api-key

# Base URL for the backend API (optional, defaults to http://localhost:42002)
AGENT_API_BASE_URL=http://localhost:42002
```

### 3. Run the Agent

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-vscode.md#resolve-a-merge-conflict",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-vscode.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-vscode.md"},
      "result": "..."
    }
  ]
}
```

## Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's answer to the question |
| `source` | string | Source reference (e.g., `wiki/git-workflow.md#section-name` or `backend/app/routers/analytics.py#function`) |
| `tool_calls` | array | All tool calls made during the agentic loop |

Each `tool_calls` entry contains:
- `tool`: Tool name (`read_file`, `list_files`, or `query_api`)
- `args`: Arguments passed to the tool
- `result`: Tool execution result

## Environment Variables

| Variable | Description | Source | Default |
|----------|-------------|--------|---------|
| `LLM_API_KEY` | API key for LLM provider | `.env.agent.secret` | Required |
| `LLM_API_BASE` | Base URL of OpenAI-compatible endpoint | `.env.agent.secret` | Required |
| `LLM_MODEL` | Model name to use | `.env.agent.secret` | `qwen3-coder-plus` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` | Required |
| `AGENT_API_BASE_URL` | Base URL for backend API | `.env.docker.secret` | `http://localhost:42002` |

## Dependencies

- `httpx`: HTTP client for API requests
- `python-dotenv`: Environment variable loading

## Error Handling

- **Timeout:** 60 seconds for API requests
- **Max tool calls:** 10 tool calls per question
- **Path security:** Rejects paths outside project directory
- **Output:** All debug output goes to stderr; only valid JSON goes to stdout
- **Exit codes:** 0 on success, non-zero on failure

## Benchmark Performance

The agent was evaluated against 10 benchmark questions covering:
- Wiki documentation lookup (2 questions)
- Source code inspection (2 questions)
- Data-dependent API queries (2 questions)
- Bug diagnosis with multi-step reasoning (2 questions)
- Architecture reasoning (2 questions)

**Final Score: 10/10 PASSED**

### Lessons Learned

1. **Authentication flexibility:** The `query_api` tool needed an optional `auth` parameter because some questions ask about unauthenticated behavior. Initially, the tool always sent the API key, causing it to fail on status code questions.

2. **Source extraction for code files:** The original `_extract_source_from_answer` regex only captured `.md` and `.txt` files. Bug diagnosis questions require citing Python source files, so the regex was extended to also match `.py`, `.yml`, `.yaml`, and `.json` extensions.

3. **System prompt emphasis:** The LLM needed explicit instructions to ALWAYS include a source reference. Adding "ALWAYS include a source reference in your answer" and providing examples for Python files (`backend/app/routers/analytics.py#get_completion_rate`) improved compliance.

4. **Multi-step bug diagnosis:** For bug diagnosis questions, the agent must first reproduce the error with `query_api`, then read the source code with `read_file` to identify the buggy line. The system prompt was updated to explicitly describe this workflow.

5. **Environment variable separation:** The agent uses two distinct API keys: `LLM_API_KEY` for the LLM provider and `LMS_API_KEY` for the backend API. Keeping these separate is crucial for security and for the autochecker to inject its own credentials during evaluation.
