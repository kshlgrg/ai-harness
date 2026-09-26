"""Failure Clustering & Root-Cause Diagnostician Engine."""
from __future__ import annotations

from typing import Dict, List, Optional
from forge.models.base import ModelProvider
from forge.state.events import EventBus, EventType
from forge.state.state import Diagnosis, FailureCluster, TaskState, TestFailure


class FailureDiagnoser:
    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.model_provider = model_provider
        self.event_bus = event_bus

    def cluster_failures(self, failures: List[TestFailure]) -> List[FailureCluster]:
        """Cluster multiple test failures by error type and root stack frame."""
        clusters_map: Dict[str, List[TestFailure]] = {}
        for f in failures:
            # Key based on error_type and file if known
            key = f"{f.error_type}@{f.file or 'unknown'}"
            clusters_map.setdefault(key, []).append(f)

        result: List[FailureCluster] = []
        for i, (key, grouped) in enumerate(clusters_map.items(), start=1):
            sample = grouped[0]
            frames = []
            if sample.stack_trace:
                lines = sample.stack_trace.splitlines()
                frames = [l.strip() for l in lines if ".py:" in l][:3]

            cluster = FailureCluster(
                cluster_id=f"cluster_{i}",
                root_candidate=f"{sample.error_type} in {sample.file or 'code'}",
                error_type=sample.error_type,
                failing_tests=[t.test_name for t in grouped],
                stack_frames=frames,
            )
            result.append(cluster)

        return result

    def diagnose_clusters(
        self,
        state: TaskState,
        clusters: List[FailureCluster],
        context: str = "",
    ) -> List[Diagnosis]:
        """Generate root-cause hypotheses and recommended recovery actions."""
        diagnoses: List[Diagnosis] = []

        for cluster in clusters:
            diag = self._diagnose_single_cluster(state, cluster, context)
            diagnoses.append(diag)
            if self.event_bus:
                self.event_bus.emit(
                    EventType.DIAGNOSIS_CREATED,
                    state.task_id,
                    state.iteration,
                    f"Diagnosis for {cluster.cluster_id}: {diag.recommended_action} (conf: {diag.confidence})",
                    {
                        "cluster_id": cluster.cluster_id,
                        "confidence": diag.confidence,
                        "requires_rollback": diag.requires_rollback,
                    },
                )

        return diagnoses

    def _diagnose_single_cluster(
        self,
        state: TaskState,
        cluster: FailureCluster,
        context: str,
    ) -> Diagnosis:
        if self.model_provider:
            prompt = (
                f"You are the FORGE Diagnostician. Analyze this failure cluster:\n\n"
                f"Cluster ID: {cluster.cluster_id}\n"
                f"Error Type: {cluster.error_type}\n"
                f"Root Candidate: {cluster.root_candidate}\n"
                f"Failing Tests: {', '.join(cluster.failing_tests)}\n"
                f"Stack Frames: {', '.join(cluster.stack_frames)}\n\n"
                f"Current Strategy: {state.current_strategy}\n"
                f"Consecutive Failures: {state.consecutive_strategy_failures}\n\n"
                f"Context:\n{context}\n\n"
                f"Provide:\n"
                f"1. Hypotheses for the root cause\n"
                f"2. Supporting evidence\n"
                f"3. Confidence rating (0.0 to 1.0)\n"
                f"4. Recommended action\n"
                f"5. Whether this regression requires a rollback or strategy shift."
            )
            try:
                return self.model_provider.generate_structured(prompt, Diagnosis)
            except Exception:
                pass

        # Heuristic fallback diagnosis
        confidence = 0.85
        requires_rollback = state.consecutive_strategy_failures >= 2
        requires_shift = state.consecutive_strategy_failures >= 2
        return Diagnosis(
            cluster_id=cluster.cluster_id,
            hypotheses=[f"Unhandled edge condition in {cluster.root_candidate}"],
            evidence=f"Cluster error: {cluster.error_type}",
            confidence=confidence,
            recommended_action=f"Refine condition handling for {cluster.error_type}",
            requires_rollback=requires_rollback,
            requires_strategy_shift=requires_shift,
        )
