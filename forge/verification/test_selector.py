"""Impact-Aware Test Selector."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set
from forge.intelligence.dependency_graph import DependencyGraph


class TestSelector:
    __test__ = False
    def __init__(self, dep_graph: Optional[DependencyGraph] = None):
        self.dep_graph = dep_graph

    def select_tests(
        self,
        changed_files: List[str],
        all_test_files: List[str],
        mode: str = "targeted",  # "targeted" or "full"
    ) -> List[str]:
        """Select targeted or regression tests based on changed files."""
        if mode == "full" or not changed_files:
            return sorted(all_test_files)

        selected: Set[str] = set()

        # 1. Dependency graph affected tests
        if self.dep_graph:
            graph_tests = self.dep_graph.get_affected_tests(changed_files)
            selected.update(graph_tests)

        # 2. Heuristic naming matching
        for changed in changed_files:
            stem = Path(changed).stem
            # test_<stem>.py or <stem>_test.py
            for t in all_test_files:
                t_stem = Path(t).stem
                if stem in t_stem or t_stem in stem:
                    selected.add(t)

        # If no targeted tests found, fallback to available tests (limit to top 5)
        if not selected:
            selected.update(all_test_files[:5])

        return sorted(selected)
