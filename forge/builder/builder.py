"""Builder Engine: Implements planned changes and applies code edits."""
from __future__ import annotations

import ast
from typing import List, Optional
from pydantic import BaseModel, Field
from forge.builder.tools import ToolHarness
from forge.models.base import ModelProvider
from forge.state.events import EventBus, EventType
from forge.state.state import PlanStep, TaskState


class FileEditAction(BaseModel):
    file_path: str
    target_content: str
    replacement_content: str
    description: str


class BuilderPlanExecution(BaseModel):
    step_id: str
    edits: List[FileEditAction] = Field(default_factory=list)
    new_files: dict[str, str] = Field(default_factory=dict)
    summary: str = ""


class Builder:
    def __init__(
        self,
        tools: ToolHarness,
        model_provider: Optional[ModelProvider] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.tools = tools
        self.model_provider = model_provider
        self.event_bus = event_bus

    def execute_step(self, step: PlanStep, state: TaskState, context: str) -> bool:
        """Generate and apply code changes for a given plan step."""
        if self.model_provider:
            prompt = (
                f"You are the FORGE Builder. Implement the following step:\n"
                f"Step ID: {step.id}\n"
                f"Objective: {step.objective}\n"
                f"Files: {', '.join(step.files)}\n"
                f"Expected Change: {step.expected_change}\n\n"
                f"Current Strategy: {state.current_strategy}\n"
                f"CONSEQUENTIAL CONTEXT:\n{context}\n\n"
                f"Provide precise edits using exact target_content and replacement_content, or whole new_files."
            )
            try:
                execution = self.model_provider.generate_structured(prompt, BuilderPlanExecution)
                return self._apply_execution(execution, state)
            except Exception:
                pass

        return False

    def _apply_execution(self, execution: BuilderPlanExecution, state: TaskState) -> bool:
        applied_any = False

        # Apply new files
        for file_path, content in execution.new_files.items():
            if self._validate_syntax(file_path, content):
                self.tools.write_file(file_path, content)
                if file_path not in state.files_modified:
                    state.files_modified.append(file_path)
                applied_any = True
                if self.event_bus:
                    self.event_bus.emit(
                        EventType.FILE_MODIFIED,
                        state.task_id,
                        state.iteration,
                        f"Created {file_path}",
                        {"file": file_path, "type": "new"},
                    )

        # Apply edits
        for edit in execution.edits:
            try:
                current_raw = self.tools.read_file(edit.file_path)
                # Remove line numbers from read_file output for syntax test
                target_p = self.tools._resolve(edit.file_path)
                actual_content = target_p.read_text(encoding="utf-8")
                candidate_content = actual_content.replace(edit.target_content, edit.replacement_content, 1)

                if self._validate_syntax(edit.file_path, candidate_content):
                    success = self.tools.edit_file(edit.file_path, edit.target_content, edit.replacement_content)
                    if success:
                        if edit.file_path not in state.files_modified:
                            state.files_modified.append(edit.file_path)
                        applied_any = True
                        if self.event_bus:
                            self.event_bus.emit(
                                EventType.FILE_MODIFIED,
                                state.task_id,
                                state.iteration,
                                f"Modified {edit.file_path}: {edit.description}",
                                {"file": edit.file_path, "description": edit.description},
                            )
            except Exception:
                pass

        return applied_any

    def _validate_syntax(self, file_path: str, content: str) -> bool:
        if file_path.endswith(".py"):
            try:
                ast.parse(content, filename=file_path)
            except SyntaxError:
                return False
        return True
