"""Persistent Repository and Failure Memory Engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FailureMemoryItem(BaseModel):
    problem: str
    hypothesis: str
    change_applied: str
    result: str
    lesson: str


class RepoMemory:
    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()
        self.agent_dir = self.root_path / ".agent"
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.failures_file = self.agent_dir / "failure_memory.json"
        self.decisions_file = self.agent_dir / "decisions.json"
        self.failures: List[FailureMemoryItem] = []
        self.decisions: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.failures_file.exists():
            try:
                data = json.loads(self.failures_file.read_text(encoding="utf-8"))
                self.failures = [FailureMemoryItem.model_validate(item) for item in data]
            except Exception:
                self.failures = []

        if self.decisions_file.exists():
            try:
                self.decisions = json.loads(self.decisions_file.read_text(encoding="utf-8"))
            except Exception:
                self.decisions = []

    def record_failure_lesson(self, problem: str, hypothesis: str, change: str, result: str, lesson: str) -> None:
        item = FailureMemoryItem(
            problem=problem,
            hypothesis=hypothesis,
            change_applied=change,
            result=result,
            lesson=lesson,
        )
        self.failures.append(item)
        try:
            self.failures_file.write_text(
                json.dumps([f.model_dump() for f in self.failures[-50:]], indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_decision(self, task_id: str, decision: str, rationale: str) -> None:
        entry = {"task_id": task_id, "decision": decision, "rationale": rationale}
        self.decisions.append(entry)
        try:
            self.decisions_file.write_text(
                json.dumps(self.decisions[-100:], indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get_relevant_lessons(self, query: str) -> List[str]:
        q_lower = query.lower()
        lessons = []
        for f in self.failures:
            if any(word in f.problem.lower() for word in q_lower.split() if len(word) > 3):
                lessons.append(f"Past Failure: {f.problem} -> Lesson: {f.lesson}")
        return lessons[:5]
