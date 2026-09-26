"""Adversarial Critic, Diff Hygiene, and Security Auditor."""
from __future__ import annotations

import re
from typing import List, Optional
from forge.models.base import ModelProvider
from forge.state.events import EventBus, EventType
from forge.state.state import CriticFinding, CriticResult, TaskState


class Critic:
    SUSPICIOUS_SECRETS = [
        r"(?i)api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        r"(?i)secret\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
        r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}",
        r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]",
    ]

    SUSPICIOUS_PATTERNS = [
        (r"eval\(", "Unsafe eval usage"),
        (r"exec\(", "Unsafe exec usage"),
        (r"shell=True", "Unsafe subprocess shell=True call"),
        (r"\.\./\.\.", "Potential directory traversal pattern"),
    ]

    DEBUG_PRINTS = [
        (r"console\.log\(", "Leftover JavaScript console.log"),
        (r"print\(\s*['\"]DEBUG", "Leftover python debug print"),
    ]

    def __init__(
        self,
        model_provider: Optional[ModelProvider] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.model_provider = model_provider
        self.event_bus = event_bus

    def review(self, state: TaskState, diff: str) -> CriticResult:
        """Conduct adversarial review and static safety checks on the proposed solution."""
        if self.event_bus:
            self.event_bus.emit(
                EventType.CRITIC_STARTED,
                state.task_id,
                state.iteration,
                "Critic evaluating requirements, diff hygiene, and security",
            )

        findings: List[CriticFinding] = []

        # 1. Security & Secrets scan
        for pattern in self.SUSPICIOUS_SECRETS:
            if re.search(pattern, diff):
                findings.append(CriticFinding(
                    check_name="Security Scan: Hardcoded Secrets",
                    passed=False,
                    severity="HIGH",
                    evidence="Potential API key or secret token detected in patch diff.",
                ))
                break

        for pattern, desc in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, diff):
                findings.append(CriticFinding(
                    check_name=f"Security Scan: {desc}",
                    passed=False,
                    severity="MEDIUM",
                    evidence=f"Suspicious pattern found in diff: {desc}",
                ))

        # 2. Diff Hygiene scan (leftover debug prints, temporary files)
        for pattern, desc in self.DEBUG_PRINTS:
            if re.search(pattern, diff):
                findings.append(CriticFinding(
                    check_name=f"Diff Hygiene: {desc}",
                    passed=False,
                    severity="LOW",
                    evidence=f"Debug statement detected in diff: {desc}",
                ))

        # 3. Minimal Patch check
        lines_changed = len(diff.splitlines())
        if lines_changed > 600:
            findings.append(CriticFinding(
                check_name="Diff Hygiene: Minimal Patch Optimization",
                passed=False,
                severity="MEDIUM",
                evidence=f"Diff is unusually large ({lines_changed} lines). Consider reducing blast radius.",
            ))

        # 4. Requirement completeness check
        unverified_reqs = [r.id for r in state.requirements if r.status.value != "VERIFIED"]
        if unverified_reqs:
            findings.append(CriticFinding(
                check_name="Requirement Completeness",
                passed=False,
                severity="HIGH",
                evidence=f"Requirements not yet verified by executable tests: {', '.join(unverified_reqs)}",
            ))

        # If LLM model is available, perform adversarial reasoning
        if self.model_provider and diff:
            llm_result = self._adversarial_llm_check(state, diff)
            if llm_result:
                findings.extend(llm_result.findings)

        # Overall pass if no HIGH severity findings
        passed = not any(not f.passed and f.severity in {"HIGH", "CRITICAL"} for f in findings)
        recommendation = "Approved for completion" if passed else "Address critical findings before completion"

        result = CriticResult(passed=passed, findings=findings, recommendation=recommendation)
        state.critic_results.append(result)

        if self.event_bus:
            self.event_bus.emit(
                EventType.CRITIC_COMPLETED,
                state.task_id,
                state.iteration,
                f"Critic verdict: {'PASS' if passed else 'FAIL'}",
                {"passed": passed, "finding_count": len(findings)},
            )

        return result

    def _adversarial_llm_check(self, state: TaskState, diff: str) -> Optional[CriticResult]:
        prompt = (
            f"You are the Adversarial FORGE Critic. Critically attack this proposed patch:\n\n"
            f"OBJECTIVE: {state.objective}\n\n"
            f"DIFF:\n```\n{diff[:4000]}\n```\n\n"
            f"Evaluate:\n"
            f"1. Did we accidentally break backward compatibility?\n"
            f"2. Are boundary conditions and empty inputs handled?\n"
            f"3. Are there any subtle regression risks?"
        )
        try:
            return self.model_provider.generate_structured(prompt, CriticResult)
        except Exception:
            return None
