"""Recovery Engine: Strategy Shift and Rollback Orchestrator."""
from __future__ import annotations

from typing import Optional
from forge.recovery.checkpoint import CheckpointManager
from forge.state.events import EventBus, EventType
from forge.state.state import TaskState


STRATEGIES = [
    "STRATEGY_A_DIRECT_FIX",
    "STRATEGY_B_ADAPTER_LAYER",
    "STRATEGY_C_REWRITE_MODULE",
]


class RecoveryEngine:
    def __init__(
        self,
        checkpoint_mgr: CheckpointManager,
        event_bus: Optional[EventBus] = None,
        max_same_strategy_attempts: int = 2,
    ):
        self.checkpoint_mgr = checkpoint_mgr
        self.event_bus = event_bus
        self.max_same_strategy_attempts = max_same_strategy_attempts

    def handle_test_failure(self, state: TaskState, requires_rollback: bool = False) -> str:
        """Decide whether to retry, rollback, or shift strategy after a test failure."""
        state.consecutive_strategy_failures += 1

        if requires_rollback:
            self.checkpoint_mgr.rollback(state)
            return "ROLLBACK_APPLIED"

        if state.consecutive_strategy_failures >= self.max_same_strategy_attempts:
            new_strategy = self._shift_strategy(state)
            # Rollback to baseline checkpoint before trying new strategy
            if state.checkpoints:
                self.checkpoint_mgr.rollback(state, state.checkpoints[0].checkpoint_id)
            state.consecutive_strategy_failures = 0
            return f"SHIFTED_TO_{new_strategy}"

        return "RETRY_CURRENT_STRATEGY"

    def _shift_strategy(self, state: TaskState) -> str:
        current_idx = 0
        if state.current_strategy in STRATEGIES:
            current_idx = STRATEGIES.index(state.current_strategy)

        next_idx = (current_idx + 1) % len(STRATEGIES)
        new_strategy = STRATEGIES[next_idx]
        old_strategy = state.current_strategy
        state.current_strategy = new_strategy

        if self.event_bus:
            self.event_bus.emit(
                EventType.STRATEGY_CHANGED,
                state.task_id,
                state.iteration,
                f"Strategy shifted from {old_strategy} to {new_strategy}",
                {"old_strategy": old_strategy, "new_strategy": new_strategy},
            )

        return new_strategy
