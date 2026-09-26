"""Structured Planning and Risk Engine."""
from __future__ import annotations

from typing import List, Optional
from forge.intelligence.dependency_graph import DependencyGraph
from forge.models.base import ModelProvider
from forge.state.state import Plan, PlanStep, RiskLevel, TaskState


class Planner:
    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        dep_graph: Optional[DependencyGraph] = None,
    ):
        self.model_provider = model_provider
        self.dep_graph = dep_graph

    def create_plan(self, state: TaskState, context: str) -> Plan:
        """Create a structured, step-by-step engineering plan."""
        if self.model_provider:
            prompt = (
                f"You are the FORGE Master Planner. Create a minimal, high-precision engineering plan to solve the task.\n\n"
                f"TASK OBJECTIVE: {state.objective}\n"
                f"REQUIREMENTS:\n"
                + "\n".join(f"- {r.id}: {r.description}" for r in state.requirements)
                + f"\n\nCONTEXT:\n{context}\n\n"
                f"RULES:\n"
                f"1. Minimize the number of modified files.\n"
                f"2. Follow the repository's existing patterns and architecture.\n"
                f"3. Avoid unnecessary refactoring.\n"
                f"4. For each step specify targeted tests to verify the change."
            )
            try:
                plan = self.model_provider.generate_structured(prompt, Plan)
                self._enrich_risks(plan)
                return plan
            except Exception:
                pass

        # Heuristic fallback plan
        target_files = state.repository_info.get("source_files", [])[:2]
        test_files = state.repository_info.get("test_files", [])[:2]

        step = PlanStep(
            id="STEP-1",
            objective=f"Implement solution for: {state.objective}",
            files=target_files,
            expected_change="Apply targeted bug fix or feature implementation",
            risk=RiskLevel.MEDIUM,
            tests=test_files,
        )
        return Plan(
            steps=[step],
            risks=["Regression in existing dependent tests"],
            verification_strategy="Run targeted unit tests, then full test suite",
        )

    def _enrich_risks(self, plan: Plan) -> None:
        """Use dependency graph to calculate and enrich step risk levels."""
        if not self.dep_graph:
            return

        for step in plan.steps:
            max_risk = RiskLevel.LOW
            for file_path in step.files:
                risk_str = self.dep_graph.calculate_risk(file_path)
                if risk_str == "CRITICAL":
                    max_risk = RiskLevel.CRITICAL
                    break
                elif risk_str == "HIGH" and max_risk != RiskLevel.CRITICAL:
                    max_risk = RiskLevel.HIGH
                elif risk_str == "MEDIUM" and max_risk in {RiskLevel.LOW}:
                    max_risk = RiskLevel.MEDIUM
            step.risk = max_risk
