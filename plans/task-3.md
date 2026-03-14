# Task 3 Plan: The System Agent

## Overview

Extend the documentation agent from Task 2 with a new `query_api` tool that can query the deployed backend API. This enables the agent to answer both static system questions (framework, ports, status codes) and data-dependent queries (item count, scores).

## Tool Schema: `query_api`

**Purpose:** Call the deployed backend API with authentication.

**Schema:**
```json
{
  "name": "query_api",
  "description": "Query the deployed backend API. Use this to get real-time data from the system, check status codes, or diagnose API errors.",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
      },
      "path": {
        "type": "string",
        "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT/PATCH requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

**Implementation:**
- Read `LMS_API_KEY` from environment (via `.env.docker.secret`)
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Construct full URL: `{AGENT_API_BASE_URL}{path}`
- Add `Authorization: Bearer {LMS_API_KEY}` header
- Return JSON string with `status_code` and `body`

## Environment Variables

The agent must read all configuration from environment variables:

| Variable             | Purpose                                      | Source File          |
| -------------------- | -------------------------------------------- | -------------------- |
| `LLM_API_KEY`        | LLM provider API key                         | `.env.agent.secret`  |
| `LLM_API_BASE`       | LLM API endpoint URL                         | `.env.agent.secret`  |
| `LLM_MODEL`          | Model name                                   | `.env.agent.secret`  |
| `LMS_API_KEY`        | Backend API key for `query_api` auth         | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (optional)          | `.env.docker.secret` |

**Important:** The autochecker runs the agent with different credentials. Never hardcode values.

## System Prompt Update

Update the system prompt to guide the LLM on when to use each tool:

1. **`list_files`**: Discover what files exist in a directory (e.g., `wiki/`, `backend/app/routers/`)
2. **`read_file`**: Read documentation, source code, or configuration files
3. **`query_api`**: Get real-time data from the running system, check status codes, diagnose API errors

The prompt should encourage the LLM to:
- Use wiki tools for documentation questions
- Use `read_file` on source code for implementation questions
- Use `query_api` for data-dependent questions or to check actual system behavior

## Agentic Loop Changes

The agentic loop remains the same as Task 2 — we're just adding one more tool. The loop:
1. Send question + tool definitions to LLM
2. If `tool_calls` present → execute tools, append results, repeat
3. If no `tool_calls` → return answer with optional source
4. Max 10 tool calls

## Benchmark Evaluation

Run `uv run run_eval.py` to test against 10 local questions:

| # | Question Type | Expected Tool |
|---|---------------|---------------|
| 0 | Wiki: branch protection | `read_file` |
| 1 | Wiki: SSH connection | `read_file` |
| 2 | Source code: web framework | `read_file` |
| 3 | Source code: API routers | `list_files` |
| 4 | Data: item count | `query_api` |
| 5 | Data: status code | `query_api` |
| 6 | Bug diagnosis: division by zero | `query_api`, `read_file` |
| 7 | Bug diagnosis: NoneType error | `query_api`, `read_file` |
| 8 | Reasoning: request lifecycle | `read_file` |
| 9 | Reasoning: ETL idempotency | `read_file` |

## Iteration Strategy

1. Implement `query_api` tool
2. Update system prompt
3. Run `run_eval.py`
4. For each failure:
   - Check if wrong tool was called → improve tool descriptions
   - Check if tool returned error → fix implementation
   - Check if answer doesn't match keywords → adjust system prompt
5. Repeat until all 10 pass

## Implementation Steps

1. Create this plan document
2. Add `LMS_API_KEY` and `AGENT_API_BASE_URL` to `AgentConfig`
3. Implement `query_api` method with authentication
4. Add `query_api` to tool definitions
5. Update system prompt
6. Run benchmark and iterate
7. Update `AGENT.md` with lessons learned
8. Add 2 regression tests

## Benchmark Results

**Final Score: 10/10 PASSED**

### Iterations:

1. **First run (5/10):** Failed on question 6 (status code without auth). The `query_api` tool always sent the API key, but the question asked what happens **without** authentication. 
   - **Fix:** Added optional `auth` parameter to `query_api` (default `true`).

2. **Second run (6/10):** Failed on question 7 (ZeroDivisionError bug). Agent found the error but didn't include a `source` field referencing the Python file.
   - **Fix:** Updated `_extract_source_from_answer` regex to also capture `.py` files, not just `.md`/`.txt`.

3. **Third run (10/10):** All tests passed after:
   - Updated system prompt to emphasize reading source code for bug diagnosis
   - Added explicit instruction to ALWAYS include a source reference
   - Fixed source extraction for Python files
