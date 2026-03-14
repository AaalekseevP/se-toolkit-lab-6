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

        Args:
            answer: The answer text.

        Returns:
            Source reference string, or empty if not found.
        """
        import re

        # Pattern 1: wiki/file.md#section or wiki/file.md
        match = re.search(r"([a-zA-Z0-9_/.-]+\.(md|txt)(#[a-zA-Z0-9_-]+)?)", answer)
        if match:
            source = match.group(1)
            # Ensure it has a proper path structure
            if "/" in source or source.endswith(".md") or source.endswith(".txt"):
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

        system_prompt = """You are a documentation agent that helps answer questions by reading project files.

When answering questions:
1. Use `list_files` to discover what files exist in directories like 'wiki'
2. Use `read_file` to read relevant files and find the answer
3. Always cite your source by including the file path and section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)
4. Be concise and accurate
5. If you cannot find the answer after reasonable exploration, say so

Format your final answer to include a source reference like:
- "According to wiki/git-workflow.md#resolving-merge-conflicts, ..."
- "Source: wiki/git-workflow.md#section-name"
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
