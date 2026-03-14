#!/usr/bin/env python3
"""
Agent CLI - Call an LLM from Code

A simple CLI agent that takes a question, sends it to an LLM, and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with 'answer' and 'tool_calls' fields to stdout.
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


class AgentConfig:
    """Configuration for the LLM agent."""

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.api_base = os.getenv("LLM_API_BASE")
        self.model = os.getenv("LLM_MODEL", "qwen3-coder-plus")

        if not self.api_key:
            print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)
        if not self.api_base:
            print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
            sys.exit(1)


class Agent:
    """Simple LLM agent for answering questions."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.timeout = 60.0  # 60 seconds timeout

    def ask(self, question: str) -> dict:
        """
        Send a question to the LLM and get a structured answer.

        Args:
            question: The user's question as a string.

        Returns:
            Dictionary with 'answer' and 'tool_calls' fields.
        """
        url = f"{self.config.api_base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer questions concisely and accurately.",
                },
                {"role": "user", "content": question},
            ],
            "temperature": 0.7,
        }

        print(f"Sending request to LLM: {question}", file=sys.stderr)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        # Extract the answer from the response
        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}", file=sys.stderr)
            print(f"Raw response: {data}", file=sys.stderr)
            sys.exit(1)

        return {
            "answer": answer,
            "tool_calls": [],  # Will be populated in Task 2
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
