"""FORGE Sandboxed File & Command Execution Tools."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel


class CommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class ToolHarness:
    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()

    def _resolve(self, rel_or_abs: str) -> Path:
        p = Path(rel_or_abs)
        if not p.is_absolute():
            p = (self.root_path / p).resolve()
        return p

    def read_file(self, file_path: str, start_line: int = 1, end_line: int = -1) -> str:
        target = self._resolve(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        lines = target.read_text(encoding="utf-8").splitlines()
        total = len(lines)
        start = max(1, start_line)
        end = total if end_line == -1 or end_line > total else end_line

        selected = lines[start - 1 : end]
        numbered = [f"{i + start:4d} | {line}" for i, line in enumerate(selected)]
        return "\n".join(numbered)

    def write_file(self, file_path: str, content: str) -> None:
        target = self._resolve(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def edit_file(self, file_path: str, target_chunk: str, replacement_chunk: str) -> bool:
        target = self._resolve(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = target.read_text(encoding="utf-8")
        if target_chunk not in content:
            return False

        updated = content.replace(target_chunk, replacement_chunk, 1)
        target.write_text(updated, encoding="utf-8")
        return True

    def run_command(self, cmd: str, timeout: float = 60.0) -> CommandResult:
        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.root_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            duration = int((time.time() - start_time) * 1000)
            # Truncate overly long outputs (limit to 100KB)
            stdout = proc.stdout[-30000:] if len(proc.stdout) > 30000 else proc.stdout
            stderr = proc.stderr[-30000:] if len(proc.stderr) > 30000 else proc.stderr
            return CommandResult(
                command=cmd,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired:
            duration = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=cmd,
                exit_code=124,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=cmd,
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration,
            )

    def git_diff(self, file_path: Optional[str] = None) -> str:
        cmd = f"git diff {file_path}" if file_path else "git diff"
        res = self.run_command(cmd)
        return res.stdout

    def git_status(self) -> str:
        res = self.run_command("git status --short")
        return res.stdout
