"""Tests for Adversarial Critic, Diff Hygiene, and Security Scanning."""
from forge.state.state import RequirementStatus, TaskState
from forge.verification.critic import Critic


def test_critic_security_detection():
    critic = Critic()
    state = TaskState(task_id="t_critic", objective="Review diff")
    state.add_requirement("REQ-001", "Ensure token validation")
    state.mark_requirement_verified("REQ-001", "Verified by test")

    # Patch with hardcoded secret
    bad_diff = """
+ API_KEY = "sk-1234567890abcdef1234567890"
+ print("DEBUG: token is", token)
"""
    result = critic.review(state, bad_diff)
    assert not result.passed
    finding_names = [f.check_name for f in result.findings if not f.passed]
    assert any("Hardcoded Secrets" in name for name in finding_names)


def test_critic_clean_diff_passes():
    critic = Critic()
    state = TaskState(task_id="t_critic_ok", objective="Review clean diff")
    state.add_requirement("REQ-001", "Fix math handler")
    state.mark_requirement_verified("REQ-001", "Verified by tests")

    clean_diff = """
--- a/math.py
+++ b/math.py
@@ -10,3 +10,5 @@
+    if b == 0:
+        raise ValueError("Cannot divide by zero")
     return a / b
"""
    result = critic.review(state, clean_diff)
    assert result.passed
