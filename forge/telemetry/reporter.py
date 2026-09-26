"""Final Task Report Generator."""
from __future__ import annotations

from pathlib import Path
from forge.state.state import TaskState


class TaskReporter:
    def __init__(self, output_dir: Path | str = ".agent/runs"):
        self.output_dir = Path(output_dir)

    def generate_report(self, state: TaskState, diff: str) -> Path:
        run_folder = self.output_dir / state.task_id
        run_folder.mkdir(parents=True, exist_ok=True)
        report_file = run_folder / "report.md"

        evidence = state.evidence or state.calculate_evidence()

        sections = [
            f"# FORGE Task Completion Report: `{state.task_id}`",
            f"**Objective:** {state.objective}",
            f"**Final Status:** `{state.status.value}`",
            f"**Total Iterations:** {state.iteration} / {state.max_iterations}",
            f"**Final Confidence Score:** {evidence.confidence_score * 100:.1f}%\n",
            "---",
            "## 1. Requirement Traceability Matrix",
            "| ID | Description | Source | Status | Evidence |",
            "|---|---|---|---|---|",
        ]

        for req in state.requirements:
            ev = req.evidence or "None"
            sections.append(f"| {req.id} | {req.description} | {req.source} | `{req.status.value}` | {ev} |")

        sections.extend([
            "\n## 2. Test Execution & Evidence",
            f"- **Target & Regression Tests Passed:** {evidence.tests_passed} / {evidence.total_tests}",
            f"- **Regressions Detected:** {evidence.regressions_detected}",
            f"- **Critic Review:** `{'PASS' if evidence.critic_passed else 'FAIL'}`",
        ])

        if state.diagnoses:
            sections.append("\n## 3. Failure Diagnoses & Recovery History")
            for diag in state.diagnoses:
                sections.append(
                    f"- **Cluster {diag.cluster_id}:** {diag.recommended_action} (Confidence: {diag.confidence:.2f})"
                )

        if state.checkpoints:
            sections.append("\n## 4. Checkpoints & Rollbacks")
            for cp in state.checkpoints:
                sections.append(f"- **{cp.checkpoint_id}**: {cp.description} (commit: {cp.commit_hash or 'in-memory'})")

        last_critic = state.critic_results[-1] if state.critic_results else None
        if last_critic:
            sections.append("\n## 5. Adversarial Critic Findings")
            for f in last_critic.findings:
                status_icon = "✓" if f.passed else "✗"
                sections.append(f"- [{status_icon}] **{f.check_name}** ({f.severity}): {f.evidence}")

        sections.extend([
            "\n## 6. Final Patch Diff",
            "```diff",
            diff if diff.strip() else "# No diff produced",
            "```",
        ])

        content = "\n".join(sections)
        report_file.write_text(content, encoding="utf-8")
        return report_file
