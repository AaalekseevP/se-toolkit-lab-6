"""Regression tests for agent.py CLI.

These tests run agent.py as a subprocess and verify the output format.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# Path to the project root (where agent.py and .env.agent.secret live)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
AGENT_SCRIPT = PROJECT_ROOT / "agent.py"
ENV_FILE = PROJECT_ROOT / ".env.agent.secret"


def find_uv() -> str:
    """Find the uv executable."""
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path
    # Fallback: try common locations
    possible_paths = [
        Path.home() / ".local" / "bin" / "uv",
        Path("/usr/local/bin/uv"),
        Path("/usr/bin/uv"),
    ]
    for path in possible_paths:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return "uv"  # Hope it's in PATH


UV = find_uv()


@pytest.fixture(scope="module")
def env_file_exists():
    """Check that .env.agent.secret exists."""
    if not ENV_FILE.exists():
        pytest.skip(
            f".env.agent.secret not found at {ENV_FILE}. "
            "Copy .env.agent.example to .env.agent.secret and configure your LLM credentials."
        )
    return True


@pytest.fixture(scope="module")
def env_configured(env_file_exists):
    """Check that .env.agent.secret has valid configuration."""
    content = ENV_FILE.read_text()
    required_vars = ["LLM_API_KEY", "LLM_API_BASE"]

    for var in required_vars:
        if f"{var}=your-" in content or f"{var}=<" in content:
            pytest.skip(
                f"{var} not configured in .env.agent.secret. "
                "Please set up your LLM credentials before running tests."
            )


class TestAgentOutput:
    """Test that agent.py produces valid JSON output with required fields."""

    @pytest.mark.asyncio
    async def test_agent_outputs_valid_json(self, env_configured):
        """Test that agent.py outputs valid JSON."""
        result = subprocess.run(
            [UV, "run", str(AGENT_SCRIPT), "What is 2+2?"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )

        # Should exit with code 0
        assert result.returncode == 0, f"Agent failed: {result.stderr}"

        # Should output valid JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Agent did not output valid JSON: {e}\nStdout: {result.stdout}\nStderr: {result.stderr}"
            )

        assert isinstance(output, dict), "Output should be a JSON object"

    @pytest.mark.asyncio
    async def test_agent_output_has_answer_field(self, env_configured):
        """Test that agent.py output contains 'answer' field."""
        result = subprocess.run(
            [UV, "run", str(AGENT_SCRIPT), "What is 2+2?"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )

        output = json.loads(result.stdout)
        assert "answer" in output, "Output must contain 'answer' field"
        assert isinstance(output["answer"], str), "'answer' must be a string"
        assert len(output["answer"]) > 0, "'answer' must not be empty"

    @pytest.mark.asyncio
    async def test_agent_output_has_tool_calls_field(self, env_configured):
        """Test that agent.py output contains 'tool_calls' field."""
        result = subprocess.run(
            [UV, "run", str(AGENT_SCRIPT), "What is 2+2?"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )

        output = json.loads(result.stdout)
        assert "tool_calls" in output, "Output must contain 'tool_calls' field"
        assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    @pytest.mark.asyncio
    async def test_agent_stderr_not_empty(self, env_configured):
        """Test that agent.py outputs debug info to stderr (not stdout)."""
        result = subprocess.run(
            [UV, "run", str(AGENT_SCRIPT), "What is 2+2?"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )

        # Debug output should go to stderr
        assert len(result.stderr) > 0, "Agent should output debug info to stderr"

        # Stdout should only contain JSON (no debug messages)
        stdout_lines = result.stdout.strip().split("\n")
        for line in stdout_lines:
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    pytest.fail(f"Non-JSON output on stdout: {line}")
