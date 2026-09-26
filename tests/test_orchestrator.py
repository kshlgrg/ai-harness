"""End-to-End Orchestrator Offline Integration Test."""
import tempfile
from pathlib import Path
from forge.models.mock import MockModelProvider
from forge.orchestrator.engine import Orchestrator
from forge.state.state import TaskStatus
from forge.ui.tui import ForgeUI


def test_orchestrator_autonomous_cycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Setup mock project repo
        (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (root / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_calc.py").write_text("from calc import divide\ndef test_divide(): assert divide(4, 2) == 2\n", encoding="utf-8")

        mock_model = MockModelProvider()
        ui = ForgeUI()
        orchestrator = Orchestrator(
            root_path=root,
            model_provider=mock_model,
            max_iterations=3,
            ui=ui,
        )

        issue = "Fix divide function to handle zero denominator safely without crashing"
        state = orchestrator.run_task(issue, task_id="test_run_e2e")

        # Verify task completed or reached conclusive state
        assert state.task_id == "test_run_e2e"
        assert state.status in {TaskStatus.COMPLETED, TaskStatus.INSUFFICIENT_EVIDENCE}
        assert len(state.requirements) >= 1
        assert len(state.checkpoints) >= 1

        # Check telemetry report artifact generated
        report_file = root / ".agent" / "runs" / "test_run_e2e" / "report.md"
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "Requirement Traceability Matrix" in content
