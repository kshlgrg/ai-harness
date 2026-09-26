"""Deterministic Policy Engine for Agent Control Flow."""
from __future__ import annotations

from typing import Optional
from forge.state.state import Diagnosis, RequirementStatus, TaskState


class AgentPolicy:
    def __init__(self, max_same_strategy_attempts: int = 2):
        self.max_same_strategy_attempts = max_same_strategy_attempts

    def can_finish(self, state: TaskState) -> bool:
        """Completion requires explicit evidence: requirements verified, tests pass, critic passes."""
        # 1. Must have produced code or changes
        if not state.files_modified and not state.checkpoints:
            return False

        # 2. At least one requirement verified and none in FAILED state
        if not state.requirements:
            return False

        any_verified = any(r.status == RequirementStatus.VERIFIED for r in state.requirements)
        any_failed = any(r.status == RequirementStatus.FAILED for r in state.requirements)
        if not any_verified or any_failed:
            return False

        # 3. Targeted test suite must pass with 0 failures
        summary = state.test_results.get("summary", {})
        if summary.get("failed", 0) > 0:
            return False

        # 4. Critic must have reviewed and passed
        if not state.critic_results or not state.critic_results[-1].passed:
            return False

        return True

    def should_rollback(self, state: TaskState, last_diagnosis: Optional[Diagnosis]) -> bool:
        """Determine if recent changes caused a regression requiring rollback."""
        if last_diagnosis and last_diagnosis.requires_rollback:
            return True
        return False

    def should_shift_strategy(self, state: TaskState) -> bool:
        """Trigger strategy shift if repeated failures occur under current strategy."""
        return state.consecutive_strategy_failures >= self.max_same_strategy_attempts

    def detect_no_progress(self, state: TaskState) -> bool:
        """Detect looping without progress across multiple iterations."""
        if state.iteration >= 4 and not state.files_modified:
            return True
        if state.consecutive_strategy_failures >= 3:
            return True
        return False
