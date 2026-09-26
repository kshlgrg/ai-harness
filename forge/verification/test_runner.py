"""Test Execution and Output Parsing Harness."""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from forge.builder.tools import CommandResult, ToolHarness
from forge.state.events import EventBus, EventType
from forge.state.state import TestFailure


class TestRunOutput(BaseModel):
    command: str
    exit_code: int
    duration_ms: int
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: List[TestFailure] = Field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and self.failed == 0


class TestRunner:
    __test__ = False

    def __init__(
        self,
        tools: ToolHarness,
        root_path: Path | str = ".",
        event_bus: Optional[EventBus] = None,
    ):
        self.tools = tools
        self.root_path = Path(root_path).resolve()
        self.event_bus = event_bus

    def run_tests(
        self,
        test_files: Optional[List[str]] = None,
        custom_command: Optional[str] = None,
        task_id: str = "task",
        iteration: int = 0,
        timeout: float = 90.0,
    ) -> TestRunOutput:
        py_exec = shlex.quote(sys.executable or "python3")
        if custom_command:
            cmd = custom_command
            if cmd == "pytest" or cmd.startswith("pytest "):
                cmd = cmd.replace("pytest", f"{py_exec} -m pytest", 1)
        elif test_files:
            file_args = " ".join(shlex.quote(f) for f in test_files)
            cmd = f"{py_exec} -m pytest -v {file_args}"
        else:
            cmd = f"{py_exec} -m pytest -v"

        if self.event_bus:
            self.event_bus.emit(
                EventType.TEST_STARTED,
                task_id,
                iteration,
                f"Running tests: {cmd}",
                {"command": cmd, "test_files": test_files},
            )

        res = self.tools.run_command(cmd, timeout=timeout)
        parsed = self._parse_output(res)

        if self.event_bus:
            self.event_bus.emit(
                EventType.TEST_COMPLETED,
                task_id,
                iteration,
                f"Tests finished: {parsed.passed} passed, {parsed.failed} failed (exit {parsed.exit_code})",
                {
                    "total": parsed.total,
                    "passed": parsed.passed,
                    "failed": parsed.failed,
                    "exit_code": parsed.exit_code,
                },
            )

        return parsed

    def _parse_output(self, res: CommandResult) -> TestRunOutput:
        out = res.stdout + "\n" + res.stderr
        failures: List[TestFailure] = []
        
        passed_m = re.search(r"(\d+)\s+passed", out)
        failed_m = re.search(r"(\d+)\s+failed", out)
        skipped_m = re.search(r"(\d+)\s+skipped", out)

        passed = int(passed_m.group(1)) if passed_m else 0
        failed = int(failed_m.group(1)) if failed_m else (1 if res.exit_code != 0 else 0)
        skipped = int(skipped_m.group(1)) if skipped_m else 0
        total = passed + failed + skipped

        failure_blocks = re.findall(r"_{10,}\s*(.*?)\s*_{10,}([\s\S]*?)(?=(?:_{10,}|$|\n===))", out)
        for name, block in failure_blocks:
            clean_name = name.strip()
            err_match = re.search(r"E\s+([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception):\s*(.*)", block)
            if err_match:
                err_type = err_match.group(1)
                err_msg = err_match.group(2).strip()
            else:
                err_type = "Failure"
                err_msg = block.splitlines()[-1] if block.splitlines() else "Test failed"

            loc_match = re.search(r"([\w/\.-]+\.py):(\d+):", block)
            file_loc = loc_match.group(1) if loc_match else None
            line_loc = int(loc_match.group(2)) if loc_match else None

            failures.append(TestFailure(
                test_name=clean_name,
                error_type=err_type,
                error_message=err_msg,
                file=file_loc,
                line=line_loc,
                stack_trace=block.strip(),
            ))

        if res.exit_code != 0 and not failures:
            failures.append(TestFailure(
                test_name="CommandExecution",
                error_type="ExecutionError",
                error_message=res.stderr[:200] if res.stderr else "Non-zero exit code",
                stack_trace=res.stderr or res.stdout,
            ))

        return TestRunOutput(
            command=res.command,
            exit_code=res.exit_code,
            duration_ms=res.duration_ms,
            total=total if total > 0 else (1 if res.exit_code != 0 else 0),
            passed=passed,
            failed=failed,
            skipped=skipped,
            failures=failures,
            raw_stdout=res.stdout,
            raw_stderr=res.stderr,
        )
