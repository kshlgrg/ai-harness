"""Tests for Impact-Aware Test Selection."""
from forge.intelligence.dependency_graph import DependencyGraph, DependencyNode
from forge.verification.test_selector import TestSelector


def test_test_selector_heuristics_and_graph():
    dep_graph = DependencyGraph()
    # Mock node relationships
    dep_graph.nodes = {
        "auth/jwt.py": DependencyNode(file_path="auth/jwt.py", imported_by={"auth/middleware.py"}),
        "auth/middleware.py": DependencyNode(file_path="auth/middleware.py", imported_by={"tests/test_auth.py"}),
        "tests/test_auth.py": DependencyNode(file_path="tests/test_auth.py", is_test=True),
        "tests/test_users.py": DependencyNode(file_path="tests/test_users.py", is_test=True),
    }

    selector = TestSelector(dep_graph)
    all_tests = ["tests/test_auth.py", "tests/test_users.py", "tests/test_billing.py"]

    # Target test selection for changed auth/jwt.py
    selected = selector.select_tests(["auth/jwt.py"], all_tests, mode="targeted")
    assert "tests/test_auth.py" in selected
    assert "tests/test_billing.py" not in selected
