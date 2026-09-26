"""Task Understanding and Requirement Traceability Mapper."""
from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, Field
from forge.models.base import ModelProvider
from forge.state.state import Requirement, RequirementStatus


class StructuredTask(BaseModel):
    objective: str
    requirements: List[dict] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class RequirementMapper:
    def __init__(self, model_provider: Optional[ModelProvider] = None):
        self.model_provider = model_provider

    def parse_issue(self, issue_text: str) -> StructuredTask:
        """Extract objective, requirements, constraints, and criteria from issue text."""
        if self.model_provider:
            prompt = (
                f"You are the FORGE Task Understanding Engine. Analyze the following software engineering issue/task:\n\n"
                f"```text\n{issue_text}\n```\n\n"
                f"Decompose it into:\n"
                f"1. A concise objective.\n"
                f"2. Explicit and inferred requirements. Assign IDs starting from REQ-001, REQ-002, etc.\n"
                f"3. Constraints (e.g. do not break existing behavior, minimal changes).\n"
                f"4. Acceptance criteria (executable conditions to verify success)."
            )
            try:
                return self.model_provider.generate_structured(prompt, StructuredTask)
            except Exception:
                pass

        # Robust heuristic fallback when offline or model not responding
        return self._heuristic_parse(issue_text)

    def _heuristic_parse(self, issue_text: str) -> StructuredTask:
        lines = [line.strip() for line in issue_text.strip().splitlines() if line.strip()]
        objective = lines[0] if lines else "Implement task"
        
        reqs = []
        req_counter = 1
        
        # Look for bullet points or sentences
        for line in lines[1:]:
            clean = re.sub(r"^[-*#\d\.\)]\s*", "", line).strip()
            if len(clean) > 8:
                reqs.append({
                    "id": f"REQ-{req_counter:03d}",
                    "description": clean,
                    "source": "EXPLICIT"
                })
                req_counter += 1

        if not reqs:
            reqs.append({
                "id": "REQ-001",
                "description": objective,
                "source": "EXPLICIT"
            })

        return StructuredTask(
            objective=objective,
            requirements=reqs,
            constraints=[
                "Do not modify unrelated files",
                "Maintain backward compatibility",
                "Pass all existing test cases"
            ],
            acceptance_criteria=[
                "Code changes address the stated issue",
                "Targeted tests pass successfully",
                "Zero regression failures"
            ]
        )
