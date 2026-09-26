"""Tests for TaskState, Requirement Models, and EventBus."""
import json
import tempfile
from pathlib import Path
from forge.state.events import EventBus, EventType
from forge.state.state import (
    Requirement,
    RequirementStatus,
    RiskLevel,
    TaskState,
    TaskStatus,
)


def test_task_state_lifecycle():
    state = TaskState(task_id="task_test_01", objective="Test state machine")
    assert state.status == TaskStatus.INITIALIZING
    assert state.iteration == 0

    req = state.add_requirement("REQ-001", "Ensure zero error handling")
    assert req.id == "REQ-001"
    assert req.status == RequirementStatus.PENDING

    # Mark requirement verified
    success = state.mark_requirement_verified("REQ-001", "Passed unit test test_zero")
    assert success
    assert state.requirements[0].status == RequirementStatus.VERIFIED

    # State serialization & deserialization
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    state.save(tmp_path)
    loaded = TaskState.load(tmp_path)
    assert loaded.task_id == "task_test_01"
    assert len(loaded.requirements) == 1
    assert loaded.requirements[0].status == RequirementStatus.VERIFIED
    tmp_path.unlink()


def test_evidence_calculation():
    state = TaskState(task_id="task_ev_01", objective="Calculate evidence")
    state.add_requirement("REQ-001", "Requirement 1")
    state.mark_requirement_verified("REQ-001", "Evidence 1")
    state.test_results = {"summary": {"total": 10, "passed": 10, "failed": 0}}

    ev = state.calculate_evidence()
    assert ev.requirements_satisfied == 1
    assert ev.total_requirements == 1
    assert ev.tests_passed == 10
    assert ev.confidence_score > 0.5


def test_event_bus():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "events.jsonl"
        bus = EventBus(log_path=log_file)

        received = []
        bus.subscribe(lambda e: received.append(e))

        bus.emit(EventType.TASK_STARTED, "t1", 0, "Task started")
        bus.emit(EventType.PLAN_CREATED, "t1", 1, "Plan ready")

        assert len(received) == 2
        assert received[0].event_type == EventType.TASK_STARTED
        assert received[1].event_type == EventType.PLAN_CREATED

        # Verify JSONL log file
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        ev1 = json.loads(lines[0])
        assert ev1["event_type"] == "TASK_STARTED"
