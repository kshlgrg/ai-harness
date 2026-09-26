"""Semantic File Indexer for Code-Search Systems."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from forge.config import get_config
from forge.intelligence.symbol_graph import SymbolGraph
from forge.models.base import ModelProvider
from forge.models.llm import LiveLLMProvider
from forge.models.mock import MockModelProvider


class FileIndexMetadata(BaseModel):
    path: str
    language: str
    purpose: str
    symbols: List[str] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    calls_out_to: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    test_relevance: str


INDEXING_SYSTEM_PROMPT = """You are indexing a single source file for a code-search system. Given the
file's path and content, produce a compact structured summary that will be
embedded for semantic search. Be terse. Do not repeat the code. Every claim
must be grounded in what's actually in the file — never speculate about
what isn't shown.

Output ONLY valid JSON matching this schema:
{
  "path": "<file path>",
  "language": "<language>",
  "purpose": "<1-2 sentence description of what this file does, plain language>",
  "symbols": ["<top-level classes/functions/exported names>"],
  "imports": ["<key external/internal imports>"],
  "calls_out_to": ["<other modules/services this file interacts with, if evident>"],
  "side_effects": ["<I/O, network, disk, global state — empty list if none>"],
  "keywords": ["<5-10 search terms a developer might use to find this file>"],
  "test_relevance": "<'has tests' | 'tested by <file>' | 'untested' | 'is a test file'>"
}

Rules:
- If a field doesn't apply, use an empty list or string — never invent content.
- Keep "purpose" under 30 words.
- "keywords" should mix technical terms (function/class names) with conceptual
  ones (what someone would search for — e.g. "authentication", "retry logic").
- No markdown, no explanation, no text outside the JSON object."""


class SemanticIndexer:
    def __init__(
        self,
        root_path: Path | str = ".",
        model_provider: Optional[ModelProvider] = None,
    ):
        self.root_path = Path(root_path).resolve()
        if model_provider:
            self.model_provider = model_provider
        else:
            config = get_config()
            if config.api_key:
                self.model_provider = LiveLLMProvider(
                    api_key=config.api_key,
                    model=config.model,
                    base_url=config.base_url,
                )
            else:
                self.model_provider = MockModelProvider()

        self.symbol_graph = SymbolGraph(self.root_path)

    def detect_language(self, file_path: Path | str) -> str:
        suffix = Path(file_path).suffix.lower()
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React/JavaScript",
            ".tsx": "React/TypeScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".c": "C",
            ".cpp": "C++",
            ".sh": "Shell",
            ".md": "Markdown",
            ".json": "JSON",
            ".yaml": "YAML",
            ".yml": "YAML",
        }
        return mapping.get(suffix, "Unknown")

    def index_file(self, rel_path: str) -> FileIndexMetadata:
        full_path = self.root_path / rel_path
        if not full_path.is_file():
            raise FileNotFoundError(f"File not found: {rel_path}")

        content = full_path.read_text(encoding="utf-8")
        language = self.detect_language(full_path)

        # Detect symbols via AST
        self.symbol_graph.index_repository([rel_path])
        symbols = [sym.name.split(":")[-1] for sym in self.symbol_graph.symbols.values()]

        # Quick import scan
        imports = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith(("import ", "from ")) and language == "Python":
                imports.append(line_str)
            elif "import " in line_str and language in {"JavaScript", "TypeScript"}:
                imports.append(line_str)

        user_prompt = (
            f"File path: {rel_path}\n"
            f"Language: {language}\n"
            f"Structural context (from tree-sitter): symbols={symbols}, imports={imports[:10]}\n\n"
            f"File content:\n"
            f"{content[:8000]}"
        )

        response = self.model_provider.generate(
            prompt=user_prompt,
            system_prompt=INDEXING_SYSTEM_PROMPT,
            temperature=0.1,
        )

        return ModelProvider._extract_and_parse_json(response, FileIndexMetadata)
