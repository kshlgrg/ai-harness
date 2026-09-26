"""Deterministic Mock Model Provider for offline tests, baseline runs, and CI."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from forge.models.base import ModelProvider


class MockModelProvider(ModelProvider):
    """Provides structured, deterministic responses for tests and offline execution."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_history: List[Dict[str, Any]] = []

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        self.call_history.append({"prompt": prompt, "system_prompt": system_prompt})

        # Match custom responses
        for key, resp in self.responses.items():
            if key in prompt:
                return resp

        # Precise matching on engine system headers
        if "FORGE Builder" in prompt:
            return json.dumps({
                "step_id": "STEP-1",
                "edits": [
                    {
                        "file_path": "calc.py",
                        "target_content": "def divide(a, b):\n    return a / b",
                        "replacement_content": "def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
                        "description": "Safe zero check"
                    }
                ],
                "new_files": {},
                "summary": "Handled zero divisor safely"
            })

        if "FORGE Master Planner" in prompt:
            return json.dumps({
                "steps": [
                    {
                        "id": "STEP-1",
                        "objective": "Fix implementation",
                        "files": ["calc.py"],
                        "symbols": ["divide"],
                        "expected_change": "Handle edge case properly",
                        "risk": "LOW",
                        "tests": ["tests/test_calc.py"],
                        "completed": False
                    }
                ],
                "risks": ["Low regression risk"],
                "verification_strategy": "Run targeted test suite"
            })

        if "FORGE Diagnostician" in prompt:
            return json.dumps({
                "cluster_id": "cluster_1",
                "hypotheses": ["Edge case not handled in target function"],
                "evidence": "Exception raised on boundary condition",
                "confidence": 0.95,
                "recommended_action": "Add guard clause for zero or negative values",
                "requires_rollback": False,
                "requires_strategy_shift": False
            })

        if "FORGE Verification Agent" in prompt or "REQUIREMENT TO VERIFY" in prompt:
            return json.dumps({
                "req_id": "REQ-001",
                "satisfied": True,
                "evidence": "Targeted unit tests passed and diff verified",
                "remaining_risks": []
            })

        if "Adversarial FORGE Critic" in prompt or "Critic evaluating" in prompt or "Critic" in prompt:
            return json.dumps({
                "passed": True,
                "findings": [
                    {"check_name": "Requirement Coverage", "passed": True, "severity": "LOW", "evidence": "All REQs satisfied"},
                    {"check_name": "Security Check", "passed": True, "severity": "LOW", "evidence": "No credentials or injections"},
                    {"check_name": "Diff Hygiene", "passed": True, "severity": "LOW", "evidence": "Minimal clean diff"}
                ],
                "recommendation": "Ready for evidence-backed completion"
            })

        if "FORGE Task Understanding" in prompt:
            return json.dumps({
                "objective": "Resolve issue based on requirements",
                "requirements": [
                    {"id": "REQ-001", "description": "Implement requested behavior", "source": "EXPLICIT"}
                ],
                "constraints": ["Do not modify unrelated files"],
                "acceptance_criteria": ["All tests pass"]
            })

        return "OK"
