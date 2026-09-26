"""Dependency Graph & Impact Analysis Engine."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Set
from pydantic import BaseModel, Field


class DependencyNode(BaseModel):
    file_path: str
    imports: Set[str] = Field(default_factory=set)  # files imported by this file
    imported_by: Set[str] = Field(default_factory=set)  # files that import this file
    symbols: List[str] = Field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0
    is_test: bool = False


class DependencyGraph:
    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()
        self.nodes: Dict[str, DependencyNode] = {}

    def build(self, files: Optional[List[str]] = None) -> None:
        self.nodes.clear()

        if files is None:
            files = [
                str(p.relative_to(self.root_path))
                for p in self.root_path.rglob("*")
                if p.is_file() and p.suffix in {".py", ".js", ".ts"}
                and not any(part.startswith(".") or part in {"node_modules", "venv", ".venv"} for part in p.parts)
            ]

        # Initialize nodes
        for f in files:
            is_test = "test" in f.lower()
            self.nodes[f] = DependencyNode(file_path=f, is_test=is_test)

        # Parse imports
        for f in files:
            full_path = self.root_path / f
            if f.endswith(".py"):
                self._parse_python_imports(f, full_path)
            elif f.endswith((".js", ".ts")):
                self._parse_js_imports(f, full_path)

        # Compute fan_in and fan_out
        for f, node in self.nodes.items():
            node.fan_out = len(node.imports)
            node.fan_in = len(node.imported_by)

    def _parse_python_imports(self, rel_path: str, full_path: Path) -> None:
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(full_path))
        except Exception:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._resolve_and_link_py(rel_path, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._resolve_and_link_py(rel_path, node.module)

    def _resolve_and_link_py(self, source_file: str, imported_mod: str) -> None:
        # Convert module dots to path parts (e.g. auth.jwt -> auth/jwt.py)
        mod_rel = imported_mod.replace(".", "/")
        for candidate_ext in [".py", "/__init__.py"]:
            candidate = mod_rel + candidate_ext
            for target_file in self.nodes.keys():
                if target_file.endswith(candidate) or target_file == candidate:
                    self.nodes[source_file].imports.add(target_file)
                    self.nodes[target_file].imported_by.add(source_file)
                    return

    def _parse_js_imports(self, rel_path: str, full_path: Path) -> None:
        try:
            source = full_path.read_text(encoding="utf-8")
        except Exception:
            return

        matches = re.findall(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", source)
        for target in matches:
            for ext in ["", ".js", ".ts", "/index.js", "/index.ts"]:
                candidate = (Path(rel_path).parent / (target + ext)).as_posix()
                if candidate in self.nodes:
                    self.nodes[rel_path].imports.add(candidate)
                    self.nodes[candidate].imported_by.add(rel_path)
                    break

    def get_affected_files(self, changed_file: str, max_depth: int = 3) -> Set[str]:
        """Find all files impacted by a change to changed_file using transitive closure."""
        affected: Set[str] = set()
        queue = [(changed_file, 0)]
        visited = {changed_file}

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            node = self.nodes.get(current)
            if not node:
                continue

            for dependent in node.imported_by:
                if dependent not in visited:
                    visited.add(dependent)
                    affected.add(dependent)
                    queue.append((dependent, depth + 1))

        return affected

    def get_affected_tests(self, changed_files: List[str]) -> List[str]:
        """Identify candidate test files that directly or indirectly test the changed files."""
        candidate_tests: Set[str] = set()
        for f in changed_files:
            # If the changed file itself is a test file
            if self.nodes.get(f, DependencyNode(file_path=f)).is_test:
                candidate_tests.add(f)

            # Transitive dependents that are test files
            affected = self.get_affected_files(f)
            for aff in affected:
                if self.nodes.get(aff, DependencyNode(file_path=aff)).is_test:
                    candidate_tests.add(aff)

            # Heuristic match: test_<name>.py or <name>_test.py
            stem = Path(f).stem
            for node_file, node in self.nodes.items():
                if node.is_test and stem in node_file:
                    candidate_tests.add(node_file)

        return sorted(candidate_tests)

    def calculate_risk(self, target_file: str) -> str:
        """Calculate modification risk: LOW, MEDIUM, HIGH based on fan-in/fan-out."""
        node = self.nodes.get(target_file)
        if not node:
            return "LOW"
        if node.fan_in >= 10:
            return "CRITICAL"
        if node.fan_in >= 4:
            return "HIGH"
        if node.fan_in >= 1:
            return "MEDIUM"
        return "LOW"
