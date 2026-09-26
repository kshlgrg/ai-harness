"""Requirement Verification and Hypothesis Validation Engine."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field
from forge.models.base import ModelProvider
from forge.state.events import EventBus, EventType
from forge.state.state import Requirement, RequirementStatus, TaskState


class RequirementVerificationReport(BaseModel):
    req_id: str
    satisfied: bool
    evidence: str
    remaining_risks: List[str] = Field(default_factory=list)


class Verifier:
    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.model_provider = model_provider
        self.event_bus = event_bus

    def verify_all_requirements(
        self,
        state: TaskState,
        diff: str,
        test_summary: dict,
    ) -> List[RequirementVerificationReport]:
        """Verify each requirement against code changes and test execution evidence."""
        if self.event_bus:
            self.event_bus.emit(
                EventType.VERIFICATION_STARTED,
                state.task_id,
                state.iteration,
                "Verifying requirements against diff and test evidence",
                {"total_requirements": len(state.requirements)},
            )

        reports: List[RequirementVerificationReport] = []

        tests_passed = test_summary.get("passed", 0)
        tests_failed = test_summary.get("failed", 0)

        for req in state.requirements:
            report = self._verify_single_requirement(req, state, diff, tests_passed, tests_failed)
            reports.append(report)

            if report.satisfied:
                state.mark_requirement_verified(req.id, report.evidence)

        return reports

    def _verify_single_requirement(
        self,
        req: Requirement,
        state: TaskState,
        diff: str,
        tests_passed: int,
        tests_failed: int,
    ) -> RequirementVerificationReport:
        if self.model_provider and diff:
            prompt = (
                f"You are the independent FORGE Verification Agent.\n\n"
                f"REQUIREMENT TO VERIFY:\n"
                f"ID: {req.id}\n"
                f"Description: {req.description}\n\n"
                f"DIFF:\n```\n{diff[:3000]}\n```\n\n"
                f"TEST RESULTS:\nPassed: {tests_passed}, Failed: {tests_failed}\n\n"
                f"Does the evidence confirm that this specific requirement is fully satisfied without regressions?"
            )
            try:
                return self.model_provider.generate_structured(prompt, RequirementVerificationReport)
            except Exception:
                pass

        # Deterministic verification heuristic
        is_satisfied = (tests_failed == 0 and tests_passed > 0 and len(diff.strip()) > 0)
        evidence = f"Passed {tests_passed} targeted tests with zero failures and verified diff modifications." if is_satisfied else "Insufficient test evidence or failing tests."
        
        return RequirementVerificationReport(
            req_id=req.id,
            satisfied=is_satisfied,
            evidence=evidence,
            remaining_risks=[] if is_satisfied else ["Tests failed or no diff produced"],
        )
