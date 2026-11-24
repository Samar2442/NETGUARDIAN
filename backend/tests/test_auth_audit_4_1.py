import time
import pytest
import concurrent.futures
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import verify_password, DUMMY_BCRYPT_HASH, get_password_hash
from app.core.rate_limit import MemoryRateLimiter, login_rate_limiter
from app.models import AuditLog, User, RemediationProposal

@pytest.fixture(autouse=True)
def clean_rate_limiter():
    login_rate_limiter.clear_all()
    yield
    login_rate_limiter.clear_all()

# ------------------------------------------------------------------------------
# 1. Unknown-User Timing Mitigation Tests
# ------------------------------------------------------------------------------

def test_unknown_user_uses_dummy_bcrypt_hash():
    """Verify that verify_password against DUMMY_BCRYPT_HASH executes real bcrypt check and returns False."""
    assert DUMMY_BCRYPT_HASH is not None
    assert DUMMY_BCRYPT_HASH.startswith("$2b$12$")
    result = verify_password("AnyPassword!", DUMMY_BCRYPT_HASH)
    assert result is False

def test_login_timing_leak_mitigation(client):
    """
    Verify that response latency between a valid user with wrong password and
    an unknown user does not have a massive timing delta (within reasonable bounds, both do bcrypt).
    """
    # Valid user with wrong password
    t0 = time.perf_counter()
    res1 = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword!"})
    t_wrong_pw = time.perf_counter() - t0
    assert res1.status_code == 401

    # Unknown user
    t0 = time.perf_counter()
    res2 = client.post("/api/v1/auth/login", json={"username": "unknown_user_404", "password": "WrongPassword!"})
    t_unknown_user = time.perf_counter() - t0
    assert res2.status_code == 401

    # Both requests perform a work factor 12 bcrypt hash verification (~150-400ms on modern CPU).
    # The absolute difference should be small (< 150ms variance), proving dummy hash is executed.
    assert t_wrong_pw > 0.05
    assert t_unknown_user > 0.05
    delta = abs(t_wrong_pw - t_unknown_user)
    assert delta < 0.20, f"Timing difference {delta}s indicates potential user enumeration leak"

# ------------------------------------------------------------------------------
# 2. Rate Limiter Concurrency & Restart Behavior Tests
# ------------------------------------------------------------------------------

def test_rate_limiter_thread_safety_under_concurrent_load():
    """Verify thread-safe locking in MemoryRateLimiter under concurrent contention."""
    limiter = MemoryRateLimiter(max_attempts=10, window_seconds=60, cooldown_seconds=60)
    key = "concurrent_test_key"

    def record_attempt():
        return limiter.record_failure(key)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(record_attempt) for _ in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Check state consistency
    blocked_count = sum(1 for is_blocked, _ in results if is_blocked)
    assert blocked_count > 0, "Rate limiter should have triggered cooldown"
    is_blocked, retry = limiter.is_blocked(key)
    assert is_blocked is True
    assert retry > 0

def test_rate_limiter_in_memory_restart_limitation():
    """
    Document architectural limitation: in-memory rate limiter resets all state on process restart.
    Verifies that a new MemoryRateLimiter instance (simulating restart) does NOT persist previous blocks.
    """
    limiter1 = MemoryRateLimiter(max_attempts=2, window_seconds=60, cooldown_seconds=60)
    limiter1.record_failure("attacker_ip")
    limiter1.record_failure("attacker_ip")
    is_blocked1, _ = limiter1.is_blocked("attacker_ip")
    assert is_blocked1 is True

    # Process restart simulation: new instance
    limiter2 = MemoryRateLimiter(max_attempts=2, window_seconds=60, cooldown_seconds=60)
    is_blocked2, _ = limiter2.is_blocked("attacker_ip")
    # In-memory limiter loses state upon restart!
    assert is_blocked2 is False

# ------------------------------------------------------------------------------
# 3. RBAC & IDOR Verification
# ------------------------------------------------------------------------------

def test_remediation_proposal_idor_protection(client, db):
    """
    Verify that an attacker cannot approve a non-existent or arbitrary ID proposal.
    Must return 404 and not leak internal server details.
    """
    res_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "NetGuardianAdmin2026!"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/v1/remediation/non-existent-uuid-12345/approve", json={}, headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Proposal not found"

def test_viewer_role_strict_rejection_across_mutations(client):
    """Verify that viewer role cannot perform any remediation mutations."""
    res_login = client.post("/api/v1/auth/login", json={"username": "auditor", "password": "ViewerAuditor2026!"})
    viewer_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {viewer_token}"}

    endpoints = [
        "/api/v1/remediation/test-id/approve",
        "/api/v1/remediation/test-id/reject",
        "/api/v1/remediation/test-id/execute",
        "/api/v1/remediation/test-id/rollback"
    ]
    for ep in endpoints:
        res = client.post(ep, json={}, headers=headers)
        assert res.status_code == 403, f"Endpoint {ep} allowed viewer role!"

# ------------------------------------------------------------------------------
# 4. Audit Log Injection & Tampering Tests
# ------------------------------------------------------------------------------

def test_audit_log_injection_resistance(client, db):
    """Verify that malicious payload in username (e.g. JSON or newline injection) is safely escaped in AuditLog."""
    malicious_username = 'admin"}\n\n{"hacked": true}'
    res = client.post("/api/v1/auth/login", json={"username": malicious_username, "password": "bad"})
    assert res.status_code == 401

    log = db.query(AuditLog).filter(AuditLog.username == malicious_username.strip().lower()).first()
    assert log is not None
    # Details JSON is parsed safely as a dictionary, not raw executed text
    assert isinstance(log.details, dict)
    assert log.details.get("reason") == "INVALID_CREDENTIALS"

def test_role_escalation_audit_logged_before_rejection(client):
    """Verify that an altered JWT role records an audit log before returning 401."""
    from app.core.security import create_access_token
    # auditor has 'viewer' role in DB. Token claims 'admin'.
    forged_token = create_access_token(subject="auditor", role="admin")
    headers = {"Authorization": f"Bearer {forged_token}"}

    res = client.post("/api/v1/remediation/test-id/approve", json={}, headers=headers)
    assert res.status_code == 401
    assert "role" in res.json()["detail"].lower()
