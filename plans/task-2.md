# Task 2 Plan: The Documentation Agent

## Overview

Transform the simple CLI agent into an agentic system that can navigate the project wiki using two tools: `read_file` and `list_files`. The agent will iteratively call tools to find answers and cite sources.

## Tool Schemas

### `read_file`

**Purpose:** Read a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read the contents of a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept a relative path parameter
- Resolve the path against the project root
- Security: reject paths containing `../` or absolute paths
- Return file contents as string, or error message if file doesn't exist

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept a relative directory path parameter
- Resolve the path against the project root
- Security: reject paths containing `../` or absolute paths
- Return newline-separated listing of entries

## Path Security

Both tools must prevent accessing files outside the project directory:

1. **Reject absolute paths:** Check if path starts with `/` or drive letter (Windows)
2. **Reject path traversal:** Check for `../` or `..\\` in the path
3. **Resolve and verify:** After resolving the path, verify it's within the project root using `Path.resolve()` and checking the parent chain

## Agentic Loop

The agentic loop will:

1. **Initialize:** Start with user question and empty message history
2. **Send to LLM:** Send messages (system + conversation) with tool definitions to LLM
3. **Parse response:**
   - If `tool_calls` present → execute each tool, append results as `tool` role messages, repeat from step 2
   - If no `tool_calls` → extract final answer, output JSON and exit
4. **Limit iterations:** Stop after 10 tool calls maximum

### Message Format

Using OpenAI-compatible format:
- `system`: System prompt with instructions
- `user`: User question
- `assistant`: LLM response (may contain `tool_calls`)
- `tool`: Tool execution results

### System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to read relevant files and find answers
3. Include source references (file path + section anchor) in the answer
4. Output the final answer with the `source` field

## Output Format

```json
{
  "answer": "The answer text",
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

## Implementation Steps

1. Create this plan document
2. Implement `read_file` and `list_files` functions with security checks
3. Define tool schemas for LLM function calling
4. Implement the agentic loop in the `Agent` class
5. Update output format to include `source` and populated `tool_calls`
6. Update `AGENT.md` documentation
7. Add 2 regression tests

## Testing Strategy

Two regression tests:
1. **Merge conflict question:** `"How do you resolve a merge conflict?"`
   - Expects `read_file` in tool_calls
   - Expects `wiki/git-workflow.md` in source
2. **Wiki listing question:** `"What files are in the wiki?"`
   - Expects `list_files` in tool_calls
