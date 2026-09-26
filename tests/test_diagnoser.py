"""Tests for Failure Diagnoser and Clustering."""
from forge.state.state import TaskState, TestFailure
from forge.verification.diagnoser import FailureDiagnoser


def test_failure_clustering():
    diagnoser = FailureDiagnoser()
    failures = [
        TestFailure(
            test_name="test_jwt_expired",
            error_type="JWTExpiredError",
            error_message="Token expired",
            file="auth/jwt.py",
            line=45,
            stack_trace="auth/jwt.py:45: in verify_token\nraise JWTExpiredError",
        ),
        TestFailure(
            test_name="test_jwt_expired_header",
            error_type="JWTExpiredError",
            error_message="Token expired",
            file="auth/jwt.py",
            line=48,
            stack_trace="auth/jwt.py:45: in verify_token\nraise JWTExpiredError",
        ),
        TestFailure(
            test_name="test_db_connect",
            error_type="ConnectionRefusedError",
            error_message="DB down",
            file="db/session.py",
            line=12,
            stack_trace="db/session.py:12: in connect",
        ),
    ]

    clusters = diagnoser.cluster_failures(failures)
    # Should cluster into 2 clusters: JWTExpiredError@auth/jwt.py and ConnectionRefusedError@db/session.py
    assert len(clusters) == 2
    jwt_cluster = [c for c in clusters if c.error_type == "JWTExpiredError"][0]
    assert len(jwt_cluster.failing_tests) == 2
    assert "test_jwt_expired" in jwt_cluster.failing_tests
    assert "test_jwt_expired_header" in jwt_cluster.failing_tests


def test_diagnose_generation():
    diagnoser = FailureDiagnoser()
    state = TaskState(task_id="t_diag", objective="Fix JWT")
    failures = [
        TestFailure(
            test_name="test_expired",
            error_type="JWTExpiredError",
            error_message="Token expired",
            file="auth/jwt.py",
        )
    ]
    clusters = diagnoser.cluster_failures(failures)
    diagnoses = diagnoser.diagnose_clusters(state, clusters)

    assert len(diagnoses) == 1
    assert diagnoses[0].confidence > 0.0
    assert "JWTExpiredError" in diagnoses[0].recommended_action
