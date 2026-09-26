"""Tests for Repository Intelligence, AST Symbol Parsing, and Dependency Graph."""
import tempfile
from pathlib import Path
from forge.intelligence.dependency_graph import DependencyGraph
from forge.intelligence.repo_map import RepoMap
from forge.intelligence.requirement_mapper import RequirementMapper
from forge.intelligence.symbol_graph import SymbolGraph


def test_repo_map_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")
        (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mapper = RepoMap(root)
        profile = mapper.scan()

        assert profile.project_type == "python"
        assert profile.test_command == "pytest"
        assert "tests/test_sample.py" in profile.test_files
        assert "app.py" in profile.source_files


def test_symbol_graph_ast_parsing():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        code = '''
class UserAuth:
    """User authentication service."""
    def verify_token(self, token: str) -> bool:
        return True

def hash_password(pwd: str) -> str:
    """Hash password securely."""
    return "hash"
'''
        (root / "auth.py").write_text(code, encoding="utf-8")

        sg = SymbolGraph(root)
        sg.index_repository(["auth.py"])

        symbols = sg.symbols
        assert "auth.py:UserAuth" in symbols
        assert symbols["auth.py:UserAuth"].kind == "class"
        assert "User authentication service." in (symbols["auth.py:UserAuth"].docstring or "")

        assert "auth.py:UserAuth.verify_token" in symbols
        assert symbols["auth.py:UserAuth.verify_token"].kind == "method"

        assert "auth.py:hash_password" in symbols
        assert symbols["auth.py:hash_password"].kind == "function"


def test_dependency_graph_and_impact():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "core.py").write_text("def base(): return 1\n", encoding="utf-8")
        (root / "service.py").write_text("import core\ndef run(): return core.base()\n", encoding="utf-8")
        (root / "test_service.py").write_text("import service\ndef test_run(): assert service.run() == 1\n", encoding="utf-8")

        dg = DependencyGraph(root)
        dg.build(["core.py", "service.py", "test_service.py"])

        # service imports core, so core is imported_by service
        assert "service.py" in dg.nodes["core.py"].imported_by
        assert "core.py" in dg.nodes["service.py"].imports

        # Impact analysis: if core.py changes, service.py and test_service.py are affected
        affected = dg.get_affected_files("core.py")
        assert "service.py" in affected

        # Affected tests
        affected_tests = dg.get_affected_tests(["core.py"])
        assert "test_service.py" in affected_tests


def test_requirement_mapper_heuristic():
    issue = """
Fix 401 Unauthorized for expired JWT tokens
- Expired tokens must return HTTP 401 instead of 500
- Return JSON body with error code TOKEN_EXPIRED
- Do not affect valid tokens
"""
    mapper = RequirementMapper()
    structured = mapper.parse_issue(issue)

    assert "Fix 401" in structured.objective
    assert len(structured.requirements) >= 2
    req_ids = [r["id"] for r in structured.requirements]
    assert "REQ-001" in req_ids
