"""Tests for Sandboxed ToolHarness."""
import tempfile
from pathlib import Path
from forge.builder.tools import ToolHarness


def test_tool_harness_read_write_edit():
    with tempfile.TemporaryDirectory() as tmpdir:
        tools = ToolHarness(tmpdir)
        
        # Write
        tools.write_file("module.py", "def add(a, b):\n    return a - b\n")
        assert (Path(tmpdir) / "module.py").exists()

        # Read
        content = tools.read_file("module.py")
        assert "return a - b" in content

        # Edit
        edited = tools.edit_file("module.py", "return a - b", "return a + b")
        assert edited
        assert "return a + b" in tools.read_file("module.py")


def test_tool_harness_command_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        tools = ToolHarness(tmpdir)
        res = tools.run_command("python3 -c 'print(\"FORGE_OK\")'")
        assert res.exit_code == 0
        assert "FORGE_OK" in res.stdout
        assert res.duration_ms >= 0


def test_tool_harness_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        tools = ToolHarness(tmpdir)
        res = tools.run_command("python3 -c 'import time; time.sleep(2)'", timeout=0.2)
        assert res.exit_code == 124
        assert "timed out" in res.stderr
