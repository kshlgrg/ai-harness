"""FORGE Event Bus and Telemetry Logging."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    TASK_STARTED = "TASK_STARTED"
    REPO_ANALYSIS_STARTED = "REPO_ANALYSIS_STARTED"
    REPO_ANALYSIS_COMPLETED = "REPO_ANALYSIS_COMPLETED"
    PLAN_CREATED = "PLAN_CREATED"
    FILE_READ = "FILE_READ"
    FILE_MODIFIED = "FILE_MODIFIED"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    TEST_STARTED = "TEST_STARTED"
    TEST_COMPLETED = "TEST_COMPLETED"
    FAILURE_CLUSTERED = "FAILURE_CLUSTERED"
    DIAGNOSIS_CREATED = "DIAGNOSIS_CREATED"
    STRATEGY_CHANGED = "STRATEGY_CHANGED"
    ROLLBACK = "ROLLBACK"
    CRITIC_STARTED = "CRITIC_STARTED"
    CRITIC_COMPLETED = "CRITIC_COMPLETED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"


class ForgeEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: EventType
    task_id: str
    iteration: int = 0
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class EventBus:
    def __init__(self, log_path: Optional[Path | str] = None):
        self.log_path = Path(log_path) if log_path else None
        self.subscribers: List[Callable[[ForgeEvent], None]] = []
        self.events: List[ForgeEvent] = []

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, callback: Callable[[ForgeEvent], None]) -> None:
        self.subscribers.append(callback)

    def emit(self, event_type: EventType, task_id: str, iteration: int = 0, message: str = "", details: Optional[Dict[str, Any]] = None) -> ForgeEvent:
        event = ForgeEvent(
            event_type=event_type,
            task_id=task_id,
            iteration=iteration,
            message=message,
            details=details or {},
        )
        self.events.append(event)

        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")

        for subscriber in self.subscribers:
            try:
                subscriber(event)
            except Exception:
                pass

        return event


# Global default bus
_global_bus: Optional[EventBus] = None


def get_event_bus(log_path: Optional[Path | str] = None) -> EventBus:
    global _global_bus
    if _global_bus is None or log_path is not None:
        _global_bus = EventBus(log_path)
    return _global_bus
