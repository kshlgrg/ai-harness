"""Repository Mapping, Project Detection, and File Indexing."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RepoProfile(BaseModel):
    root_path: str
    project_type: str  # python, node, go, rust, java, unknown
    build_command: Optional[str] = None
    test_command: Optional[str] = None
    lint_command: Optional[str] = None
    package_manager: Optional[str] = None
    instruction_files: Dict[str, str] = Field(default_factory=dict)
    test_files: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)
    total_files: int = 0


class RepoMap:
    DEFAULT_IGNORES = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
        ".tox",
        ".idea",
        ".vscode",
    }

    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()

    def scan(self) -> RepoProfile:
        project_type, pm, build_cmd, test_cmd, lint_cmd = self._detect_project()
        all_files = self._list_files()
        
        test_files = []
        source_files = []
        for rel_path in all_files:
            lower = rel_path.lower()
            if (
                lower.startswith("test")
                or "tests/" in lower
                or "test_" in lower
                or "_test." in lower
                or ".spec." in lower
                or ".test." in lower
            ):
                test_files.append(rel_path)
            else:
                source_files.append(rel_path)

        instructions = self._read_instruction_files()

        return RepoProfile(
            root_path=str(self.root_path),
            project_type=project_type,
            build_command=build_cmd,
            test_command=test_cmd,
            lint_command=lint_cmd,
            package_manager=pm,
            instruction_files=instructions,
            test_files=test_files,
            source_files=source_files,
            total_files=len(all_files),
        )

    def _detect_project(self):
        root = self.root_path
        if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "requirements.txt").exists():
            test_cmd = "pytest" if (root / "tests").exists() or any(root.glob("test_*.py")) else "python -m unittest"
            return "python", "pip", None, test_cmd, "flake8"

        if (root / "package.json").exists():
            pm = "npm"
            if (root / "pnpm-lock.yaml").exists():
                pm = "pnpm"
            elif (root / "yarn.lock").exists():
                pm = "yarn"
            return "node", pm, f"{pm} run build", f"{pm} test", f"{pm} run lint"

        if (root / "Cargo.toml").exists():
            return "rust", "cargo", "cargo build", "cargo test", "cargo clippy"

        if (root / "go.mod").exists():
            return "go", "go", "go build ./...", "go test ./...", "golangci-lint run"

        if (root / "pom.xml").exists() or (root / "build.gradle").exists():
            return "java", "maven", "mvn compile", "mvn test", "mvn checkstyle:check"

        return "unknown", None, None, None, None

    def _list_files(self) -> List[str]:
        rel_files: List[str] = []
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.DEFAULT_IGNORES and not d.startswith(".")]
            for file in files:
                if file.startswith(".") or file.endswith((".pyc", ".so", ".png", ".jpg", ".tar", ".gz", ".zip")):
                    continue
                full_path = Path(root) / file
                try:
                    rel = str(full_path.relative_to(self.root_path))
                    rel_files.append(rel)
                except ValueError:
                    pass
        return sorted(rel_files)

    def _read_instruction_files(self) -> Dict[str, str]:
        candidates = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "README.md", "FORGE.md"]
        instructions = {}
        for candidate in candidates:
            p = self.root_path / candidate
            if p.is_file():
                try:
                    # read up to first 2000 chars to avoid prompt saturation
                    content = p.read_text(encoding="utf-8")[:2000]
                    instructions[candidate] = content
                except Exception:
                    pass
        return instructions
