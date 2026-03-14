# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

**Provider:** Qwen Code API (deployed on VM)

**Model:** `qwen3-coder-plus`

**Rationale:**
- 1000 free requests per day (sufficient for development and testing)
- Works from Russia without restrictions
- No credit card required
- Strong tool calling capabilities (needed for future tasks)
- OpenAI-compatible API endpoint

## Architecture

### Components

1. **Environment Configuration** (`.env.agent.secret`)
   - `LLM_API_KEY`: API key for authentication
   - `LLM_API_BASE`: Base URL of the OpenAI-compatible endpoint
   - `LLM_MODEL`: Model name to use

2. **Agent CLI** (`agent.py`)
   - Parses command-line arguments (question as first argument)
   - Loads environment variables from `.env.agent.secret`
   - Constructs an OpenAI-compatible chat completion request
   - Sends request to LLM API using `httpx` (already in dependencies)
   - Parses the LLM response
   - Outputs structured JSON to stdout

### Data Flow

```
Command line argument → agent.py → HTTP POST to LLM API → Response → JSON output
```

### Output Format

```json
{"answer": "<LLM response content>", "tool_calls": []}
```

### Error Handling

- Timeout: 60 seconds for API request
- All debug/progress output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success, non-zero on failure

## Implementation Steps

1. Create `.env.agent.secret` from `.env.agent.example` with actual credentials
2. Implement `agent.py`:
   - Load environment variables using `pydantic-settings` or `os.environ`
   - Parse command-line arguments using `sys.argv` or `argparse`
   - Make HTTP request to LLM API using `httpx`
   - Parse response and format output
3. Create `AGENT.md` documentation
4. Write regression test

## Dependencies

Using existing project dependencies from `pyproject.toml`:
- `httpx`: For HTTP requests to LLM API
- `pydantic-settings`: For loading environment configuration
- `pydantic`: For data validation

No additional dependencies required.
