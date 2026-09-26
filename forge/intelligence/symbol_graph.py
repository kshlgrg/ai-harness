"""AST and Structural Symbol Graph Extraction."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field


class SymbolInfo(BaseModel):
    name: str
    kind: str  # class, function, method, import
    file_path: str
    line: int
    end_line: Optional[int] = None
    docstring: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)


class SymbolGraph:
    def __init__(self, root_path: Path | str = "."):
        self.root_path = Path(root_path).resolve()
        self.symbols: Dict[str, SymbolInfo] = {}  # qualified_name -> SymbolInfo
        self.file_symbols: Dict[str, List[str]] = {}  # file_path -> [symbol_names]

    def index_repository(self, files: Optional[List[str]] = None) -> None:
        self.symbols.clear()
        self.file_symbols.clear()

        if files is None:
            # find all python and js/ts files
            files = [
                str(p.relative_to(self.root_path))
                for p in self.root_path.rglob("*")
                if p.is_file() and p.suffix in {".py", ".js", ".ts", ".jsx", ".tsx"}
                and not any(part.startswith(".") or part in {"node_modules", "venv", ".venv"} for part in p.parts)
            ]

        for rel_file in files:
            full_path = self.root_path / rel_file
            if rel_file.endswith(".py"):
                self._index_python_file(rel_file, full_path)
            elif rel_file.endswith((".js", ".ts", ".jsx", ".tsx")):
                self._index_js_file(rel_file, full_path)

    def _index_python_file(self, rel_path: str, full_path: Path) -> None:
        try:
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(full_path))
        except Exception:
            return

        file_syms: List[str] = []

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self, outer):
                self.outer = outer
                self.current_class = None

            def visit_ClassDef(self, node: ast.ClassDef):
                sym_name = f"{rel_path}:{node.name}"
                doc = ast.get_docstring(node)
                deps = [b.id for b in node.bases if isinstance(b, ast.Name)]
                info = SymbolInfo(
                    name=sym_name,
                    kind="class",
                    file_path=rel_path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    docstring=doc,
                    dependencies=deps,
                )
                self.outer.symbols[sym_name] = info
                file_syms.append(sym_name)

                prev_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = prev_class

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._record_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._record_func(node)

            def _record_func(self, node):
                if self.current_class:
                    sym_name = f"{rel_path}:{self.current_class}.{node.name}"
                    kind = "method"
                else:
                    sym_name = f"{rel_path}:{node.name}"
                    kind = "function"

                doc = ast.get_docstring(node)
                info = SymbolInfo(
                    name=sym_name,
                    kind=kind,
                    file_path=rel_path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    docstring=doc,
                )
                self.outer.symbols[sym_name] = info
                file_syms.append(sym_name)
                self.generic_visit(node)

        ASTVisitor(self).visit(tree)
        self.file_symbols[rel_path] = file_syms

    def _index_js_file(self, rel_path: str, full_path: Path) -> None:
        try:
            source = full_path.read_text(encoding="utf-8")
        except Exception:
            return

        file_syms: List[str] = []
        for i, line in enumerate(source.splitlines(), start=1):
            line_str = line.strip()
            # match class
            m_cls = re.match(r"^(?:export\s+)?class\s+([A-Za-z0-9_]+)", line_str)
            if m_cls:
                name = f"{rel_path}:{m_cls.group(1)}"
                self.symbols[name] = SymbolInfo(name=name, kind="class", file_path=rel_path, line=i)
                file_syms.append(name)
                continue

            # match function
            m_fn = re.match(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)", line_str)
            if m_fn:
                name = f"{rel_path}:{m_fn.group(1)}"
                self.symbols[name] = SymbolInfo(name=name, kind="function", file_path=rel_path, line=i)
                file_syms.append(name)
                continue

            # match const fn = () =>
            m_const = re.match(r"^(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", line_str)
            if m_const:
                name = f"{rel_path}:{m_const.group(1)}"
                self.symbols[name] = SymbolInfo(name=name, kind="function", file_path=rel_path, line=i)
                file_syms.append(name)

        self.file_symbols[rel_path] = file_syms

    def find_symbol(self, query: str) -> List[SymbolInfo]:
        matches = []
        q_lower = query.lower()
        for name, info in self.symbols.items():
            if q_lower in name.lower():
                matches.append(info)
        return matches
