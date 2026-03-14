#!/usr/bin/env python3
"""
Agent CLI - Call an LLM from Code

A CLI agent that takes a question, sends it to an LLM, and returns a structured JSON answer.
Supports tool calling for navigating the project wiki.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer', 'source', and 'tool_calls' fields to stdout.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
ENV_FILE = Path(__file__).parent / ".env.agent.secret"
load_dotenv(ENV_FILE)

# Maximum tool calls per question
MAX_TOOL_CALLS = 10


class AgentConfig:
    """Configuration for the LLM agent."""

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.api_base = os.getenv("LLM_API_BASE")
        self.model = os.getenv("LLM_MODEL", "qwen3-coder-plus")
        self.project_root = Path(__file__).parent
        
        # Backend API configuration
        self.lms_api_key = os.getenv("LMS_API_KEY")
        self.agent_api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

        if not self.api_key:
            print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        if not self.api_base:
            print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)


class Agent:
    """Simple LLM agent for answering questions with tool support."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.timeout = 60.0  # 60 seconds timeout
        self.tool_calls_log = []

    def _validate_path(self, path: str) -> tuple[bool, str]:
        """
        Validate that a path is safe and within the project directory.

        Args:
            path: The path to validate.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is empty.
        """
        # Reject absolute paths
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            return False, "Absolute paths are not allowed"

        # Reject path traversal
        if ".." in path:
            return False, "Path traversal (..) is not allowed"

        # Resolve the path and verify it's within project root
        try:
            full_path = (self.config.project_root / path).resolve()
            project_root_resolved = self.config.project_root.resolve()

            # Check if the resolved path is within the project root
            try:
                full_path.relative_to(project_root_resolved)
            except ValueError:
                return False, "Path is outside the project directory"
        except Exception as e:
            return False, f"Invalid path: {e}"

        return True, ""

    def read_file(self, path: str) -> str:
        """
        Read a file from the project repository.

        Args:
            path: Relative path from project root.

        Returns:
            File contents as a string, or an error message.
        """
        is_valid, error = self._validate_path(path)
        if not is_valid:
            return f"Error: {error}"

        full_path = self.config.project_root / path

        if not full_path.exists():
            return f"Error: File not found: {path}"

        if not full_path.is_file():
            return f"Error: Not a file: {path}"

        try:
            return full_path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"

    def list_files(self, path: str) -> str:
        """
        List files and directories at a given path.

        Args:
            path: Relative directory path from project root.

        Returns:
            Newline-separated listing of entries, or an error message.
        """
        is_valid, error = self._validate_path(path)
        if not is_valid:
            return f"Error: {error}"

        full_path = self.config.project_root / path

        if not full_path.exists():
            return f"Error: Directory not found: {path}"

        if not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        try:
            entries = sorted(full_path.iterdir())
            lines = [entry.name for entry in entries]
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing directory: {e}"

    def query_api(self, method: str, path: str, body: str = None, auth: bool = True) -> str:
        """
        Query the deployed backend API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            path: API path (e.g., '/items/', '/analytics/completion-rate').
            body: Optional JSON request body for POST/PUT/PATCH requests.
            auth: Whether to include authentication header (default True).

        Returns:
            JSON string with status_code and body, or an error message.
        """
        # Validate method
        allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        if method.upper() not in allowed_methods:
            return f"Error: Invalid method '{method}'. Allowed: {', '.join(allowed_methods)}"

        # Validate path
        if not path.startswith("/"):
            return f"Error: Path must start with '/': {path}"

        # Construct full URL
        base_url = self.config.agent_api_base_url.rstrip("/")
        url = f"{base_url}{path}"

        headers = {
            "Content-Type": "application/json",
        }
        
        # Only add auth header if requested
        if auth and self.config.lms_api_key:
            headers["Authorization"] = f"Bearer {self.config.lms_api_key}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if body:
                    response = client.request(method, url, headers=headers, json=json.loads(body))
                else:
                    response = client.request(method, url, headers=headers)

            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            return json.dumps(result)
        except httpx.HTTPError as e:
            return f"Error: HTTP request failed: {e}"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON body: {e}"
        except Exception as e:
            return f"Error: API request failed: {e}"

    def _get_tool_definitions(self) -> list[dict]:
        """Get the tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file from the project repository. Use this to read wiki files or other documentation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                            }
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories in a directory. Use this to discover what files exist in a directory like 'wiki'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative directory path from project root (e.g., 'wiki')",
                            }
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_api",
                    "description": "Query the deployed backend API. Use this to get real-time data from the system, check status codes, or diagnose API errors. The API requires Bearer token authentication by default.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "method": {
                                "type": "string",
                                "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                            },
                            "path": {
                                "type": "string",
                                "description": "API path (e.g., '/items/', '/analytics/completion-rate')",
                            },
                            "body": {
                                "type": "string",
                                "description": "Optional JSON request body for POST/PUT/PATCH requests",
                            },
                            "auth": {
                                "type": "boolean",
                                "description": "Whether to include authentication header (default: true). Set to false to test unauthenticated access.",
                            },
                        },
                        "required": ["method", "path"],
                    },
                },
            },
        ]

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """
        Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute.
            args: Arguments for the tool.

        Returns:
            Tool execution result as a string.
        """
        if tool_name == "read_file":
            path = args.get("path", "")
            result = self.read_file(path)
        elif tool_name == "list_files":
            path = args.get("path", "")
            result = self.list_files(path)
        elif tool_name == "query_api":
            method = args.get("method", "GET")
            path = args.get("path", "")
            body = args.get("body")
            auth = args.get("auth", True)  # Default to authenticated
            result = self.query_api(method, path, body, auth)
        else:
            result = f"Error: Unknown tool: {tool_name}"

        return result

    def _extract_source_from_answer(self, answer: str) -> str:
        """
        Extract source reference from the answer text.

        Looks for patterns like:
        - wiki/file.md#section
        - Source: wiki/file.md
        - (wiki/file.md)
        - backend/app/routers/analytics.py#function

        Args:
            answer: The answer text.

        Returns:
            Source reference string, or empty if not found.
        """
        import re

        # Pattern 1: path/to/file.md#section or path/to/file.md (also .py, .txt, .yml, .yaml, .json)
        match = re.search(r"([a-zA-Z0-9_/.-]+\.(md|txt|py|yml|yaml|json)(#[a-zA-Z0-9_-]+)?)", answer)
        if match:
            source = match.group(1)
            # Ensure it has a proper path structure
            if "/" in source or source.endswith((".md", ".txt", ".py", ".yml", ".yaml", ".json")):
                return source

        return ""

    def ask(self, question: str) -> dict:
        """
        Send a question to the LLM and get a structured answer with tool calls.

        Args:
            question: The user's question as a string.

        Returns:
            Dictionary with 'answer', 'source', and 'tool_calls' fields.
        """
        url = f"{self.config.api_base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        system_prompt = """You are a documentation and system agent that helps answer questions by reading project files and querying the running backend API.

You have three tools available:
1. `list_files` - Discover what files exist in directories like 'wiki' or 'backend/app/routers'
2. `read_file` - Read wiki documentation, source code, or configuration files
3. `query_api` - Query the running backend API to get real-time data, check status codes, or diagnose errors

When answering questions:
- For documentation questions: use `list_files` to discover wiki files, then `read_file` to find answers
- For source code questions: use `list_files` to explore the codebase, then `read_file` to read relevant files
- For data-dependent questions (counts, scores, current state): use `query_api` to query the running system
- For status code or API behavior questions: use `query_api` to test the actual API
- For bug diagnosis: use `query_api` to reproduce the error, then `read_file` to examine the source code and identify the buggy line
- ALWAYS include a source reference in your answer - either a file path (e.g., wiki/git-workflow.md#section) or the API endpoint used
- Be concise and accurate
- If you cannot find the answer after reasonable exploration, say so

Format your final answer to include a source reference like:
- "According to wiki/git-workflow.md#resolving-merge-conflicts, ..."
- "Source: wiki/git-workflow.md#section-name"
- "Source: backend/app/routers/analytics.py#get_completion_rate"
- For API queries, mention the endpoint used
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        tool_calls_log = []
        tool_call_count = 0

        print(f"Sending request to LLM: {question}", file=sys.stderr)

        while tool_call_count < MAX_TOOL_CALLS:
            payload = {
                "model": self.config.model,
                "messages": messages,
                "tools": self._get_tool_definitions(),
                "tool_choice": "auto",
                "temperature": 0.7,
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            # Extract the response
            try:
                choice = data["choices"][0]
                message = choice["message"]
            except (KeyError, IndexError) as e:
                print(f"Error parsing LLM response: {e}", file=sys.stderr)
                print(f"Raw response: {data}", file=sys.stderr)
                sys.exit(1)

            # Check for tool calls
            tool_calls = message.get("tool_calls")

            if tool_calls:
                # Execute each tool call
                tool_results = []
                for tool_call in tool_calls:
                    tool_id = tool_call["id"]
                    function = tool_call["function"]
                    tool_name = function["name"]
                    tool_args = json.loads(function["arguments"])

                    print(f"Executing tool: {tool_name} with args: {tool_args}", file=sys.stderr)

                    result = self._execute_tool(tool_name, tool_args)

                    # Log the tool call
                    tool_calls_log.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "result": result,
                        }
                    )

                    # Add tool result to messages
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result,
                        }
                    )

                    tool_call_count += 1

                # Add assistant message and tool results to conversation
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.get("content"),
                        "tool_calls": tool_calls,
                    }
                )
                messages.extend(tool_results)

                print(f"Tool call count: {tool_call_count}", file=sys.stderr)
            else:
                # No tool calls - this is the final answer
                answer = message.get("content", "")

                # Extract source from answer
                source = self._extract_source_from_answer(answer)

                return {
                    "answer": answer,
                    "source": source,
                    "tool_calls": tool_calls_log,
                }

        # Max tool calls reached
        answer = "Maximum tool calls reached. Could not find a complete answer."
        return {
            "answer": answer,
            "source": "",
            "tool_calls": tool_calls_log,
        }


def main():
    """Main entry point for the agent CLI."""
    if len(sys.argv) < 2:
        print('Usage: uv run agent.py "Your question here"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    config = AgentConfig()
    agent = Agent(config)

    result = agent.ask(question)

    # Output only valid JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
