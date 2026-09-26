"""FORGE Orchestrator: The Closed-Loop Self-Verifying Engine."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional
from forge.builder.builder import Builder
from forge.builder.tools import ToolHarness
from forge.intelligence.context_engine import ContextEngine
from forge.intelligence.dependency_graph import DependencyGraph
from forge.intelligence.repo_map import RepoMap
from forge.intelligence.requirement_mapper import RequirementMapper
from forge.intelligence.symbol_graph import SymbolGraph
from forge.memory.repo_memory import RepoMemory
from forge.models.base import ModelProvider
from forge.models.mock import MockModelProvider
from forge.orchestrator.policy import AgentPolicy
from forge.planner.planner import Planner
from forge.recovery.checkpoint import CheckpointManager
from forge.recovery.recovery_engine import RecoveryEngine
from forge.state.events import EventBus, EventType, get_event_bus
from forge.state.state import RequirementStatus, TaskState, TaskStatus
from forge.telemetry.reporter import TaskReporter
from forge.ui.tui import ForgeUI
from forge.verification.critic import Critic
from forge.verification.diagnoser import FailureDiagnoser
from forge.verification.test_runner import TestRunner
from forge.verification.test_selector import TestSelector
from forge.verification.verifier import Verifier


class Orchestrator:
    def __init__(
        self,
        root_path: Path | str = ".",
        model_provider: Optional[ModelProvider] = None,
        max_iterations: int = 10,
        ui: Optional[ForgeUI] = None,
    ):
        self.root_path = Path(root_path).resolve()
        self.max_iterations = max_iterations
        self.model_provider = model_provider or MockModelProvider()
        self.ui = ui or ForgeUI()

        # Tools & Checkpoints
        self.tools = ToolHarness(self.root_path)
        self.event_bus = get_event_bus(self.root_path / ".agent" / "runs" / "active_events.jsonl")
        self.event_bus.subscribe(self.ui.handle_event)
        self.checkpoint_mgr = CheckpointManager(self.tools, self.root_path, self.event_bus)

        # Intelligence
        self.repo_map = RepoMap(self.root_path)
        self.symbol_graph = SymbolGraph(self.root_path)
        self.dep_graph = DependencyGraph(self.root_path)
        self.req_mapper = RequirementMapper(self.model_provider)
        self.context_engine = ContextEngine(self.root_path)

        # Core Agents
        self.planner = Planner(self.model_provider, self.dep_graph)
        self.builder = Builder(self.tools, self.model_provider, self.event_bus)
        self.test_runner = TestRunner(self.tools, self.root_path, self.event_bus)
        self.test_selector = TestSelector(self.dep_graph)
        self.diagnoser = FailureDiagnoser(self.model_provider, self.event_bus)
        self.verifier = Verifier(self.model_provider, self.event_bus)
        self.critic = Critic(self.model_provider, self.event_bus)
        self.recovery = RecoveryEngine(self.checkpoint_mgr, self.event_bus)
        self.policy = AgentPolicy()
        self.memory = RepoMemory(self.root_path)
        self.reporter = TaskReporter(self.root_path / ".agent" / "runs")

    def run_task(self, issue_text: str, task_id: Optional[str] = None) -> TaskState:
        """Execute autonomous self-verifying engineering loop on the issue."""
        tid = task_id or f"task_{int(time.time())}"
        state = TaskState(
            task_id=tid,
            objective="",
            raw_issue=issue_text,
            max_iterations=self.max_iterations,
        )

        self.event_bus.emit(
            EventType.TASK_STARTED,
            state.task_id,
            0,
            f"Starting FORGE task: {tid}",
            {"issue_length": len(issue_text)},
        )

        # 1. EXPLORING: Map Repository and Build Graphs
        state.status = TaskStatus.EXPLORING
        self.event_bus.emit(EventType.REPO_ANALYSIS_STARTED, state.task_id, 0, "Analyzing repository structure")
        
        profile = self.repo_map.scan()
        state.repository_info = profile.model_dump()
        self.symbol_graph.index_repository()
        self.dep_graph.build()

        self.event_bus.emit(
            EventType.REPO_ANALYSIS_COMPLETED,
            state.task_id,
            0,
            f"Discovered {profile.total_files} files ({profile.project_type} project)",
            {"type": profile.project_type, "test_cmd": profile.test_command},
        )

        # 2. UNDERSTANDING: Extract Structured Requirements
        structured_task = self.req_mapper.parse_issue(issue_text)
        state.objective = structured_task.objective
        state.constraints = structured_task.constraints
        state.acceptance_criteria = structured_task.acceptance_criteria
        for r in structured_task.requirements:
            state.add_requirement(r["id"], r["description"], r.get("source", "EXPLICIT"))

        # 3. BASELINE CHECKPOINT
        self.checkpoint_mgr.create_checkpoint(state, "Baseline before changes")

        # 4. PLANNING: Formulate Solution Plan
        state.status = TaskStatus.PLANNING
        context = self.context_engine.assemble_context(state)
        state.plan = self.planner.create_plan(state, context)
        self.event_bus.emit(
            EventType.PLAN_CREATED,
            state.task_id,
            0,
            f"Formulated {len(state.plan.steps)} plan steps",
            {"steps": [s.id for s in state.plan.steps]},
        )

        # 5. CLOSED-LOOP ITERATION
        while state.iteration < state.max_iterations:
            state.iteration += 1

            # A. IMPLEMENTING
            state.status = TaskStatus.IMPLEMENTING
            for step in state.plan.steps:
                if not step.completed:
                    self.checkpoint_mgr.create_checkpoint(state, f"Pre-implementation: {step.id}")
                    applied = self.builder.execute_step(step, state, context)
                    if applied:
                        step.completed = True

            diff = self.checkpoint_mgr.get_diff(state)

            # B. TESTING: Impact-Aware Test Selection
            state.status = TaskStatus.TESTING
            all_tests = profile.test_files
            targeted_tests = self.test_selector.select_tests(state.files_modified, all_tests, mode="targeted")
            
            test_output = self.test_runner.run_tests(
                test_files=targeted_tests if targeted_tests else None,
                custom_command=profile.test_command,
                task_id=state.task_id,
                iteration=state.iteration,
            )
            state.test_results["summary"] = {
                "total": test_output.total,
                "passed": test_output.passed,
                "failed": test_output.failed,
            }
            state.failures = test_output.failures

            # C. EVALUATION: Pass or Fail branching
            if test_output.is_success:
                # Tests passed! Move to VERIFYING & CRITIC
                state.status = TaskStatus.VERIFYING
                ver_reports = self.verifier.verify_all_requirements(state, diff, state.test_results["summary"])
                
                state.status = TaskStatus.CRITIQUING
                critic_res = self.critic.review(state, diff)

                # Run full regression suite if targeted passed and critic passed
                if critic_res.passed and len(all_tests) > len(targeted_tests):
                    full_output = self.test_runner.run_tests(
                        test_files=all_tests,
                        custom_command=profile.test_command,
                        task_id=state.task_id,
                        iteration=state.iteration,
                    )
                    if not full_output.is_success:
                        # Regression detected!
                        state.failures = full_output.failures
                        test_output = full_output

                # Check if deterministic completion policy is satisfied
                if self.policy.can_finish(state):
                    state.status = TaskStatus.COMPLETED
                    state.calculate_evidence()
                    self.event_bus.emit(
                        EventType.TASK_COMPLETED,
                        state.task_id,
                        state.iteration,
                        f"Task completed with evidence confidence: {state.evidence.confidence_score * 100:.0f}%",
                    )
                    break
                else:
                    state.status = TaskStatus.REPLANNING

            # If tests failed or verification not met: DIAGNOSING & RECOVERY
            if not test_output.is_success:
                state.status = TaskStatus.DIAGNOSING
                clusters = self.diagnoser.cluster_failures(state.failures)
                state.failure_clusters = clusters
                diagnoses = self.diagnoser.diagnose_clusters(state, clusters, context)
                state.diagnoses = diagnoses

                last_diag = diagnoses[-1] if diagnoses else None
                recovery_action = self.recovery.handle_test_failure(
                    state,
                    requires_rollback=(last_diag.requires_rollback if last_diag else False),
                )

                # Replan based on diagnosis
                state.status = TaskStatus.REPLANNING
                context = self.context_engine.assemble_context(state)
                state.plan = self.planner.create_plan(state, context)

            if self.policy.detect_no_progress(state):
                state.status = TaskStatus.INSUFFICIENT_EVIDENCE
                break

        # Final cleanup and report generation
        if state.status not in {TaskStatus.COMPLETED, TaskStatus.INSUFFICIENT_EVIDENCE}:
            state.status = TaskStatus.TIMEOUT

        state.calculate_evidence()
        final_diff = self.checkpoint_mgr.get_diff(state)
        report_path = self.reporter.generate_report(state, final_diff)
        state.save(self.root_path / ".agent" / "runs" / state.task_id / "state.json")

        self.ui.print_final_summary(state, final_diff)
        return state
