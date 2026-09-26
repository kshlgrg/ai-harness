"""Context Ranking, Prioritization, and Compression Engine."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
from forge.state.state import TaskState, TestFailure


class ContextEngine:
    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()

    def assemble_context(
        self,
        state: TaskState,
        relevant_files: Optional[List[str]] = None,
        max_file_lines: int = 250,
    ) -> str:
        """Build ranked and compressed context for the model prompt."""
        sections: List[str] = []

        # 1. Failing Tests & Stack Traces (Highest Priority)
        if state.failures:
            sections.append("### Active Test Failures & Stack Traces (PRIORITY 1)")
            for fail in state.failures[:5]:  # limit to top 5
                sections.append(
                    f"- **Test:** `{fail.test_name}` ({fail.error_type})\n"
                    f"  **Error:** {fail.error_message}\n"
                    f"  **File/Line:** {fail.file or 'unknown'}:{fail.line or 'unknown'}\n"
                    f"  ```text\n{fail.stack_trace[:800]}\n  ```"
                )

        # 2. Directly Modified / Target Files
        target_files = list(dict.fromkeys((relevant_files or []) + state.files_modified))
        if target_files:
            sections.append("### Target & Modified Files (PRIORITY 2)")
            for rel_file in target_files[:6]:
                full_path = self.root_path / rel_file
                if full_path.is_file():
                    try:
                        content = full_path.read_text(encoding="utf-8")
                        lines = content.splitlines()
                        if len(lines) > max_file_lines:
                            sample = "\n".join(lines[:max_file_lines]) + f"\n... [{len(lines) - max_file_lines} more lines truncated]"
                        else:
                            sample = content
                        sections.append(f"#### File: `{rel_file}`\n```\n{sample}\n```")
                    except Exception as e:
                        sections.append(f"#### File: `{rel_file}` (read error: {e})")

        # 3. Requirements Checklist
        sections.append("### Requirements Checklist")
        for req in state.requirements:
            status_symbol = "✓" if req.status.value == "VERIFIED" else "○"
            sections.append(f"- [{status_symbol}] **{req.id}**: {req.description} (status: {req.status.value})")

        # 4. Repository Instructions / Conventions
        repo_info = state.repository_info or {}
        instructions = repo_info.get("instruction_files", {})
        if instructions:
            sections.append("### Repository Guidance & Conventions")
            for filename, text in instructions.items():
                sections.append(f"- **{filename}**: {text[:300].strip()}...")

        return "\n\n".join(sections)
