"""Regression tests for agent.py CLI.

These tests run agent.py as a subprocess and verify the output format.
Run with: uv run pytest test_agent.py -v
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def find_uv() -> str:
    """Find the uv executable."""
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path
    return "uv"


UV = find_uv()
PROJECT_ROOT = Path(__file__).parent
AGENT_SCRIPT = PROJECT_ROOT / "agent.py"
ENV_FILE = PROJECT_ROOT / ".env.agent.secret"


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON."""
    result = subprocess.run(
        [UV, "run", str(AGENT_SCRIPT), "What is 2+2?"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=60,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Agent did not output valid JSON: {e}\nStdout: {result.stdout}"
        ) from e

    assert isinstance(output, dict), "Output should be a JSON object"


def test_agent_output_has_answer_field():
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


def test_agent_output_has_tool_calls_field():
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


def test_agent_uses_read_file_for_merge_conflict_question():
    """Test that agent uses read_file tool when asked about merge conflicts."""
    result = subprocess.run(
        [UV, "run", str(AGENT_SCRIPT), "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)
    assert "tool_calls" in output, "Output must contain 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Check that read_file was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that source references a wiki file about git
    assert "source" in output, "Output must contain 'source' field"
    assert output["source"].startswith("wiki/git"), \
        f"Expected source to reference a wiki git file, got: {output.get('source', '')}"
    assert ".md" in output["source"], \
        f"Expected source to be a markdown file, got: {output.get('source', '')}"


def test_agent_uses_list_files_for_wiki_listing_question():
    """Test that agent uses list_files tool when asked about wiki files."""
    result = subprocess.run(
        [UV, "run", str(AGENT_SCRIPT), "What files are in the wiki?"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = json.loads(result.stdout)
    assert "tool_calls" in output, "Output must contain 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    # Check that list_files was used
    tool_names = [tc["tool"] for tc in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"
