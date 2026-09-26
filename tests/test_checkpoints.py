"""Tests for Checkpoints and Strategy Recovery."""
import tempfile
from pathlib import Path
from forge.builder.tools import ToolHarness
from forge.recovery.checkpoint import CheckpointManager
from forge.recovery.recovery_engine import RecoveryEngine
from forge.state.state import TaskState


def test_checkpoint_and_rollback():
    with tempfile.TemporaryDirectory() as tmpdir:
        tools = ToolHarness(tmpdir)
        mgr = CheckpointManager(tools, tmpdir)
        state = TaskState(task_id="t_cp", objective="test checkpoints")

        # Create original file
        tools.write_file("main.py", "VERSION = 1\n")
        state.files_modified.append("main.py")

        # Create baseline checkpoint
        cp1 = mgr.create_checkpoint(state, "Initial baseline")
        assert len(state.checkpoints) == 1

        # Modify file
        tools.write_file("main.py", "VERSION = 2\n")
        assert "VERSION = 2" in tools.read_file("main.py")

        # Rollback
        success = mgr.rollback(state, cp1.checkpoint_id)
        assert success
        assert "VERSION = 1" in tools.read_file("main.py")


def test_strategy_shift_on_repeated_failure():
    with tempfile.TemporaryDirectory() as tmpdir:
        tools = ToolHarness(tmpdir)
        mgr = CheckpointManager(tools, tmpdir)
        recovery = RecoveryEngine(mgr, max_same_strategy_attempts=2)
        state = TaskState(task_id="t_strat", objective="test strategy shift")

        assert state.current_strategy == "STRATEGY_A_DIRECT_FIX"

        # Failure 1
        act1 = recovery.handle_test_failure(state)
        assert act1 == "RETRY_CURRENT_STRATEGY"
        assert state.consecutive_strategy_failures == 1
        assert state.current_strategy == "STRATEGY_A_DIRECT_FIX"

        # Failure 2 -> should shift strategy!
        act2 = recovery.handle_test_failure(state)
        assert "SHIFTED_TO" in act2
        assert state.current_strategy == "STRATEGY_B_ADAPTER_LAYER"
        assert state.consecutive_strategy_failures == 0
