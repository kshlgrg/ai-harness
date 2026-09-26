"""FORGE Task and Agent State Definitions."""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    EXPLORING = "EXPLORING"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    DIAGNOSING = "DIAGNOSING"
    REPLANNING = "REPLANNING"
    VERIFYING = "VERIFYING"
    CRITIQUING = "CRITIQUING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RequirementStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Requirement(BaseModel):
    id: str  # e.g., REQ-001
    description: str
    source: str = "EXPLICIT"  # EXPLICIT or INFERRED
    status: RequirementStatus = RequirementStatus.PENDING
    target_files: List[str] = Field(default_factory=list)
    evidence: Optional[str] = None


class PlanStep(BaseModel):
    id: str  # e.g., STEP-1
    objective: str
    files: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    expected_change: str = ""
    risk: RiskLevel = RiskLevel.LOW
    tests: List[str] = Field(default_factory=list)
    completed: bool = False


class Plan(BaseModel):
    steps: List[PlanStep] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    verification_strategy: str = ""


class CheckpointInfo(BaseModel):
    checkpoint_id: str
    commit_hash: Optional[str] = None
    timestamp: str
    description: str
    files_snapshot: Dict[str, str] = Field(default_factory=dict)


class TestFailure(BaseModel):
    __test__ = False
    test_name: str
    error_type: str
    error_message: str
    file: Optional[str] = None
    line: Optional[int] = None
    stack_trace: str = ""


class FailureCluster(BaseModel):
    cluster_id: str
    root_candidate: str
    error_type: str
    failing_tests: List[str] = Field(default_factory=list)
    stack_frames: List[str] = Field(default_factory=list)


class Diagnosis(BaseModel):
    cluster_id: str
    hypotheses: List[str] = Field(default_factory=list)
    evidence: str = ""
    confidence: float = 0.0
    recommended_action: str = ""
    requires_rollback: bool = False
    requires_strategy_shift: bool = False


class CriticFinding(BaseModel):
    check_name: str
    passed: bool
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    evidence: str = ""


class CriticResult(BaseModel):
    passed: bool
    findings: List[CriticFinding] = Field(default_factory=list)
    recommendation: str = ""


class EvidenceSummary(BaseModel):
    requirements_satisfied: int = 0
    total_requirements: int = 0
    tests_passed: int = 0
    total_tests: int = 0
    critic_passed: bool = False
    regressions_detected: int = 0
    confidence_score: float = 0.0


class TaskState(BaseModel):
    task_id: str
    objective: str
    raw_issue: str = ""
    status: TaskStatus = TaskStatus.INITIALIZING
    iteration: int = 0
    max_iterations: int = 10
    consecutive_strategy_failures: int = 0
    current_strategy: str = "STRATEGY_A_DIRECT_FIX"

    requirements: List[Requirement] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)

    repository_info: Dict[str, Any] = Field(default_factory=dict)
    plan: Optional[Plan] = None

    files_inspected: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)

    checkpoints: List[CheckpointInfo] = Field(default_factory=list)
    test_results: Dict[str, Any] = Field(default_factory=dict)
    failures: List[TestFailure] = Field(default_factory=list)
    failure_clusters: List[FailureCluster] = Field(default_factory=list)
    diagnoses: List[Diagnosis] = Field(default_factory=list)
    critic_results: List[CriticResult] = Field(default_factory=list)
    evidence: Optional[EvidenceSummary] = None

    def add_requirement(self, req_id: str, description: str, source: str = "EXPLICIT") -> Requirement:
        req = Requirement(id=req_id, description=description, source=source)
        self.requirements.append(req)
        return req

    def mark_requirement_verified(self, req_id: str, evidence: str) -> bool:
        for r in self.requirements:
            if r.id == req_id:
                r.status = RequirementStatus.VERIFIED
                r.evidence = evidence
                return True
        return False

    def calculate_evidence(self) -> EvidenceSummary:
        total_reqs = len(self.requirements)
        sat_reqs = sum(1 for r in self.requirements if r.status == RequirementStatus.VERIFIED)
        
        test_info = self.test_results.get("summary", {})
        total_tests = test_info.get("total", 0)
        passed_tests = test_info.get("passed", 0)
        
        last_critic = self.critic_results[-1] if self.critic_results else None
        critic_ok = last_critic.passed if last_critic else False
        
        # Evidence-based confidence score heuristic (0.0 to 1.0)
        score = 0.0
        if total_reqs > 0:
            score += 0.40 * (sat_reqs / total_reqs)
        else:
            score += 0.20
            
        if total_tests > 0:
            score += 0.35 * (passed_tests / total_tests)
        else:
            score += 0.15
            
        if critic_ok:
            score += 0.25
            
        if self.consecutive_strategy_failures > 0:
            score = max(0.0, score - (0.15 * self.consecutive_strategy_failures))
            
        self.evidence = EvidenceSummary(
            requirements_satisfied=sat_reqs,
            total_requirements=total_reqs,
            tests_passed=passed_tests,
            total_tests=total_tests,
            critic_passed=critic_ok,
            regressions_detected=len(self.failures),
            confidence_score=round(min(1.0, score), 2),
        )
        return self.evidence

    def save(self, filepath: Path | str) -> None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, filepath: Path | str) -> TaskState:
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
