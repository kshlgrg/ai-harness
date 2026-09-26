"""Atomic Checkpoint & Rollback System with File-tree Snapshots."""
from __future__ import annotations

import difflib
import time
from pathlib import Path
from typing import Dict, List, Optional
from forge.builder.tools import ToolHarness
from forge.state.events import EventBus, EventType
from forge.state.state import CheckpointInfo, TaskState


class CheckpointManager:
    def __init__(
        self,
        tools: ToolHarness,
        root_path: Path | str = ".",
        event_bus: Optional[EventBus] = None,
    ):
        self.tools = tools
        self.root_path = Path(root_path).resolve()
        self.event_bus = event_bus
        self.snapshots: Dict[str, Dict[str, str]] = {}
        self.checkpoints_dir = self.root_path / ".agent" / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(self, state: TaskState, description: str) -> CheckpointInfo:
        """Create an atomic snapshot of all tracked and modified files."""
        cp_id = f"cp_{len(state.checkpoints):03d}_{int(time.time())}"
        cp_dir = self.checkpoints_dir / cp_id
        cp_dir.mkdir(parents=True, exist_ok=True)

        file_snapshot: Dict[str, str] = {}
        candidate_files = list(dict.fromkeys(
            state.files_modified + state.repository_info.get("source_files", [])[:50]
        ))
        for rel_file in candidate_files:
            target = self.tools._resolve(rel_file)
            if target.is_file():
                try:
                    content = target.read_text(encoding="utf-8")
                    file_snapshot[rel_file] = content
                    dest = cp_dir / rel_file
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")
                except Exception:
                    pass

        self.snapshots[cp_id] = file_snapshot

        # Record tree hash if git is present without committing on branch HEAD
        tree_hash = None
        tree_res = self.tools.run_command("git write-tree")
        if tree_res.exit_code == 0:
            tree_hash = tree_res.stdout.strip()

        cp_info = CheckpointInfo(
            checkpoint_id=cp_id,
            commit_hash=tree_hash,
            timestamp=str(time.time()),
            description=description,
            files_snapshot={k: f"{len(v)} chars" for k, v in file_snapshot.items()},
        )
        state.checkpoints.append(cp_info)

        if self.event_bus:
            self.event_bus.emit(
                EventType.CHECKPOINT_CREATED,
                state.task_id,
                state.iteration,
                f"Checkpoint {cp_id}: {description}",
                {"checkpoint_id": cp_id, "tree_hash": tree_hash},
            )

        return cp_info

    def rollback(self, state: TaskState, checkpoint_id: Optional[str] = None) -> bool:
        """Rollback working tree to checkpoint."""
        if not state.checkpoints:
            return False

        target_cp = None
        if checkpoint_id:
            for cp in state.checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    target_cp = cp
                    break
        else:
            target_cp = state.checkpoints[-1]

        if not target_cp:
            return False

        snapshot = self.snapshots.get(target_cp.checkpoint_id, {})
        for rel_file, content in snapshot.items():
            try:
                self.tools.write_file(rel_file, content)
            except Exception:
                pass

        self._notify_rollback(state, target_cp.checkpoint_id)
        return True

    def get_diff(self, state: TaskState) -> str:
        """Get diff via git if available, or compute unified diff against baseline snapshot."""
        git_diff = self.tools.git_diff()
        if git_diff.strip():
            return git_diff

        if not state.checkpoints:
            return ""

        baseline_snapshot = self.snapshots.get(state.checkpoints[0].checkpoint_id, {})
        diff_chunks = []

        for file_path in state.files_modified:
            baseline_content = baseline_snapshot.get(file_path, "")
            target = self.tools._resolve(file_path)
            current_content = target.read_text(encoding="utf-8") if target.is_file() else ""

            lines1 = baseline_content.splitlines(keepends=True)
            lines2 = current_content.splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(lines1, lines2, fromfile=f"a/{file_path}", tofile=f"b/{file_path}"))
            if diff_lines:
                diff_chunks.append("".join(diff_lines))

        return "\n".join(diff_chunks)

    def _notify_rollback(self, state: TaskState, cp_id: str) -> None:
        if self.event_bus:
            self.event_bus.emit(
                EventType.ROLLBACK,
                state.task_id,
                state.iteration,
                f"Rolled back to {cp_id}",
                {"checkpoint_id": cp_id},
            )
