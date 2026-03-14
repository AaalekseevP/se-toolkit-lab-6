# Agent

A CLI agent that connects to an LLM and answers questions.

## Architecture

### Components

- **`agent.py`**: Main CLI entry point
- **`.env.agent.secret`**: Environment configuration for LLM access

### LLM Provider

**Provider:** Qwen Code API

**Model:** `qwen3-coder-plus`

The agent uses an OpenAI-compatible API endpoint to communicate with the LLM.

### Data Flow

```
User question (CLI argument)
    ↓
agent.py (parses input)
    ↓
HTTP POST to LLM API
    ↓
LLM response
    ↓
JSON output: {"answer": "...", "tool_calls": []}
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
uv run agent.py "What does REST stand for?"
```

### Output

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

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

- Timeout: 60 seconds for API requests
- All debug output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success, non-zero on failure
