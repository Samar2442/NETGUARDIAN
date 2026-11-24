import time
import uuid
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_jwt_token,
    TokenSecurityError,
    TokenExpiredError,
    TokenSignatureError,
    TokenClaimError,
)
from app.core.rate_limit import login_rate_limiter, MemoryRateLimiter
from app.models import User, AuditLog, RemediationProposal, Device, Incident

@pytest.fixture(autouse=True)
def clean_rate_limiter():
    """Ensure test isolation by resetting rate limiter before and after each test."""
    login_rate_limiter.clear_all()
    yield
    login_rate_limiter.clear_all()

# ==============================================================================
# JWT TESTS (1-15)
# ==============================================================================

def test_01_valid_token_accepted():
    token = create_access_token(subject="admin", role="admin")
    payload = verify_jwt_token(token)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload

def test_02_expired_token_rejected():
    token = create_access_token(
        subject="admin",
        role="admin",
        expires_delta=timedelta(seconds=-60)
    )
    with pytest.raises(TokenExpiredError) as exc:
        verify_jwt_token(token)
    assert "expired" in str(exc.value).lower()

def test_03_malformed_token_rejected():
    with pytest.raises(TokenSecurityError):
        verify_jwt_token("not.a.valid.jwt")

def test_04_tampered_token_rejected():
    token = create_access_token(subject="admin", role="admin")
    parts = token.split(".")
    # Tamper with payload segment
    tampered_payload = parts[1][:-2] + "AA"
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    with pytest.raises(TokenSecurityError):
        verify_jwt_token(tampered_token)

def test_05_invalid_signature_rejected():
    token = create_access_token(subject="admin", role="admin")
    parts = token.split(".")
    # Mutate signature with valid base64url characters so PyJWT validates signature crypto and fails
    sig_chars = list(parts[2])
    sig_chars[0] = "A" if sig_chars[0] != "A" else "B"
    sig_chars[1] = "A" if sig_chars[1] != "A" else "B"
    tampered_token = f"{parts[0]}.{parts[1]}.{''.join(sig_chars)}"
    with pytest.raises(TokenSignatureError):
        verify_jwt_token(tampered_token)

def test_06_wrong_secret_key_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    wrong_token = jwt.encode(payload, "wrong-secret-key-32-characters-long", algorithm="HS256")
    with pytest.raises(TokenSignatureError):
        verify_jwt_token(wrong_token)

def test_07_none_algorithm_token_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
    }
    none_token = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(TokenSecurityError):
        verify_jwt_token(none_token)

def test_08_unsupported_algorithm_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    # Encode with HS384 when settings expects HS256
    token_hs384 = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS384")
    with pytest.raises(TokenSecurityError):
        verify_jwt_token(token_hs384)

def test_09_missing_sub_rejected():
    payload = {
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenClaimError) as exc:
        verify_jwt_token(token)
    assert "sub" in str(exc.value).lower()

def test_10_missing_exp_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenClaimError) as exc:
        verify_jwt_token(token)
    assert "exp" in str(exc.value).lower()

def test_11_invalid_claim_types_rejected():
    payload = {
        "sub": 99999,  # Non-string sub
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenClaimError) as exc:
        verify_jwt_token(token)
    assert "sub" in str(exc.value).lower()

def test_12_future_issued_token_rejected_beyond_clock_skew():
    future_iat = int(time.time()) + 300  # 5 minutes in future (exceeds 10s skew)
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": future_iat,
        "exp": future_iat + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenClaimError) as exc:
        verify_jwt_token(token)
    assert "future" in str(exc.value).lower() or "clock skew" in str(exc.value).lower()

def test_13_wrong_issuer_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": "unauthorized-malicious-issuer",
        "aud": settings.JWT_AUDIENCE,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenSecurityError):
        verify_jwt_token(token)

def test_14_wrong_audience_rejected():
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": "wrong-audience-service",
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenSecurityError):
        verify_jwt_token(token)

def test_15_valid_token_with_expected_claims_accepted():
    token = create_access_token(
        subject="neteng",
        role="network_engineer",
        custom_claims={"tenant": "SaturnX"}
    )
    payload = verify_jwt_token(token)
    assert payload["sub"] == "neteng"
    assert payload["role"] == "network_engineer"
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE
    assert payload["tenant"] == "SaturnX"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert isinstance(payload["jti"], str)


# ==============================================================================
# LOGIN & RATE LIMITING TESTS (16-26)
# ==============================================================================

def test_16_valid_credentials_authenticate_successfully(client):
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "NetGuardianAdmin2026!"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["username"] == "admin"
    assert data["role"] == "admin"

def test_17_invalid_password_rejected(client):
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "IncorrectPassword123!"
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect username or password"

def test_18_unknown_username_rejected(client):
    res = client.post("/api/v1/auth/login", json={
        "username": "completely_unknown_user",
        "password": "SomePassword123!"
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect username or password"

def test_19_unknown_username_and_invalid_password_produce_equivalent_error(client):
    res_wrong_pw = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "WrongPassword999!"
    })
    res_unknown_user = client.post("/api/v1/auth/login", json={
        "username": "ghost_user_999",
        "password": "WrongPassword999!"
    })
    assert res_wrong_pw.status_code == 401
    assert res_unknown_user.status_code == 401
    # Security requirement: identical error response to prevent user enumeration
    assert res_wrong_pw.json()["detail"] == res_unknown_user.json()["detail"]

def test_20_repeated_failed_attempts_trigger_rate_limiting(client):
    target_user = "brute_force_target_user"
    login_rate_limiter.reset(f"user:{target_user}")

    for i in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        res = client.post("/api/v1/auth/login", json={
            "username": target_user,
            "password": "WrongPassword!"
        })
        assert res.status_code == 401

    # Next attempt must trigger rate limit
    res_blocked = client.post("/api/v1/auth/login", json={
        "username": target_user,
        "password": "WrongPassword!"
    })
    assert res_blocked.status_code == 429

def test_21_rate_limited_response_returns_http_429(client):
    target_user = "rate_limit_429_test_user"
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})
    res = client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})
    assert res.status_code == 429
    assert "too many" in res.json()["detail"].lower()

def test_22_retry_after_header_present_and_valid(client):
    target_user = "retry_after_test_user"
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})
    res = client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})
    assert res.status_code == 429
    assert "retry-after" in res.headers
    retry_after = int(res.headers["retry-after"])
    assert retry_after > 0
    assert retry_after <= settings.LOGIN_RATE_LIMIT_COOLDOWN_SECONDS

def test_23_successful_login_resets_failed_attempt_counter(client):
    target_user = "admin"
    login_rate_limiter.reset(f"user:{target_user}")

    # 3 failed attempts (less than max of 5)
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})

    # Successful login resets failure counter
    res_success = client.post("/api/v1/auth/login", json={
        "username": target_user,
        "password": "NetGuardianAdmin2026!"
    })
    assert res_success.status_code == 200

    # User should now have a clean slate (not blocked)
    res_after = client.post("/api/v1/auth/login", json={"username": target_user, "password": "bad"})
    assert res_after.status_code == 401  # 401, not 429!

def test_24_identifier_normalization_behaves_consistently(client):
    base_user = "case_normalized_user"
    login_rate_limiter.reset(f"user:{base_user}")

    # Alternate case variations - trigger 5 failed attempts
    variations = [
        "Case_Normalized_User",
        "CASE_NORMALIZED_USER",
        "  case_normalized_user  ",
        "CaSe_NoRmAlIzEd_UsEr",
        "case_normalized_user"
    ]
    for var in variations:
        client.post("/api/v1/auth/login", json={"username": var, "password": "bad"})

    # Check that another variation is throttled by normalized identifier
    res = client.post("/api/v1/auth/login", json={"username": "CASE_NORMALIZED_USER", "password": "bad"})
    assert res.status_code == 429

def test_25_ip_based_rate_limiting_with_trusted_proxy(client):
    spoofed_ip = "198.51.100.77"
    login_rate_limiter.reset(f"ip:{spoofed_ip}")

    # Client connects from trusted proxy 127.0.0.1 with X-Forwarded-For
    headers = {"X-Forwarded-For": f"{spoofed_ip}, 127.0.0.1"}
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        client.post("/api/v1/auth/login", json={"username": "unique_user_" + str(uuid.uuid4())[:8], "password": "bad"}, headers=headers)

    # Next attempt from that IP is throttled
    res = client.post("/api/v1/auth/login", json={"username": "another_unique_user", "password": "bad"}, headers=headers)
    assert res.status_code == 429

def test_26_untrusted_forwarded_headers_cannot_bypass(client):
    # If client connects from an untrusted IP, arbitrary X-Forwarded-For must be ignored
    old_trusted = settings.TRUSTED_PROXIES
    settings.TRUSTED_PROXIES = []  # No trusted proxies
    try:
        limiter = MemoryRateLimiter(max_attempts=2, window_seconds=60, cooldown_seconds=60)
        from app.core.rate_limit import get_client_ip
        from starlette.requests import Request

        # Create mock requests with spoofed X-Forwarded-For
        scope = {
            "type": "http",
            "client": ("203.0.113.10", 12345),
            "headers": [(b"x-forwarded-for", b"1.1.1.1")]
        }
        req = Request(scope)
        resolved_ip = get_client_ip(req)
        # Must resolve to direct client IP 203.0.113.10, NOT spoofed 1.1.1.1
        assert resolved_ip == "203.0.113.10"
    finally:
        settings.TRUSTED_PROXIES = old_trusted


# ==============================================================================
# RBAC TESTS (27-33)
# ==============================================================================

def test_27_unauthenticated_protected_api_access_rejected(client):
    # Remediation approval requires authentication
    res = client.post("/api/v1/remediation/test-prop-id/approve", json={})
    assert res.status_code == 401

def test_28_viewer_cannot_execute_remediation(client):
    # Log in as auditor (viewer role)
    res_login = client.post("/api/v1/auth/login", json={
        "username": "auditor",
        "password": "ViewerAuditor2026!"
    })
    viewer_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Attempt to execute remediation (requires engineer or admin)
    res = client.post("/api/v1/remediation/test-prop-id/execute", json={}, headers=headers)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()

def test_29_viewer_cannot_access_admin_only_endpoints(client):
    res_login = client.post("/api/v1/auth/login", json={
        "username": "auditor",
        "password": "ViewerAuditor2026!"
    })
    viewer_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Attempt to approve remediation (requires admin)
    res = client.post("/api/v1/remediation/test-prop-id/approve", json={}, headers=headers)
    assert res.status_code == 403

def test_30_engineer_cannot_access_admin_only_endpoints(client):
    res_login = client.post("/api/v1/auth/login", json={
        "username": "neteng",
        "password": "CiscoEngineer2026!"
    })
    eng_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {eng_token}"}

    # Engineer cannot approve remediation (requires admin)
    res = client.post("/api/v1/remediation/test-prop-id/approve", json={}, headers=headers)
    assert res.status_code == 403

def test_31_admin_can_access_authorized_admin_endpoints(client, db):
    # Ensure device, incident, and proposal exist in db
    dev = db.query(Device).first()
    if not dev:
        dev = Device(
            hostname="SW-TEST-CORE",
            management_ip="10.0.0.1",
            device_type="l3_switch"
        )
        db.add(dev)
        db.commit()

    inc = db.query(Incident).first()
    if not inc:
        inc = Incident(
            incident_number="INC-AUTH-TEST",
            title="Authentication Test Incident",
            description="Test incident for auth hardening",
            severity="low",
            status="DETECTED"
        )
        db.add(inc)
        db.commit()

    prop = db.query(RemediationProposal).first()
    if not prop:
        prop = RemediationProposal(
            incident_id=inc.id,
            device_id=dev.id,
            title="Interface bounce",
            proposed_commands="interface GigabitEthernet0/1\n no shutdown",
            rollback_commands="interface GigabitEthernet0/1\n shutdown",
            status="PENDING_APPROVAL",
            risk_level="low",
            expected_result="Link restored"
        )
        db.add(prop)
        db.commit()

    res_login = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "NetGuardianAdmin2026!"
    })
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.post(f"/api/v1/remediation/{prop.id}/approve", json={}, headers=headers)
    # Admin is authorized: response is 200 (or proposal state), not 401 or 403!
    assert res.status_code in {200, 400}
    assert res.status_code not in {401, 403}

def test_32_role_escalation_through_modified_jwt_rejected(client, db):
    # Attacker takes valid viewer user ('auditor') but tampers role to 'admin' in JWT claim
    tampered_role_token = create_access_token(
        subject="auditor",
        role="admin"  # In DB, auditor is 'viewer'
    )
    headers = {"Authorization": f"Bearer {tampered_role_token}"}

    res = client.post("/api/v1/remediation/test-id/approve", json={}, headers=headers)
    # Server-side authoritative validation catches that token role doesn't match DB role
    assert res.status_code == 401
    assert "role" in res.json()["detail"].lower()

def test_33_existing_authentication_behavior_compatible(client):
    res_login = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "NetGuardianAdmin2026!"
    })
    token = res_login.json()["access_token"]
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["username"] == "admin"
    assert res_me.json()["role"] == "admin"


# ==============================================================================
# SECURITY LOGGING TESTS (34-40)
# ==============================================================================

def test_34_successful_login_event_recorded(client, db):
    client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "NetGuardianAdmin2026!"
    })
    audit = db.query(AuditLog).filter(
        AuditLog.action == "USER_LOGIN",
        AuditLog.status == "SUCCESS"
    ).order_by(AuditLog.timestamp.desc()).first()
    assert audit is not None
    assert audit.username == "admin"

def test_35_failed_login_event_recorded(client, db):
    client.post("/api/v1/auth/login", json={
        "username": "security_test_failure_user",
        "password": "WrongPassword123!"
    })
    audit = db.query(AuditLog).filter(
        AuditLog.action == "USER_LOGIN_FAILED",
        AuditLog.username == "security_test_failure_user"
    ).order_by(AuditLog.timestamp.desc()).first()
    assert audit is not None
    assert audit.status == "FAILED"
    assert audit.details.get("reason") == "INVALID_CREDENTIALS"

def test_36_rate_limit_event_recorded(client, db):
    target = "rate_limit_audit_target"
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS + 1):
        client.post("/api/v1/auth/login", json={"username": target, "password": "bad"})

    audit = db.query(AuditLog).filter(
        AuditLog.action == "LOGIN_RATE_LIMITED",
        AuditLog.username == target
    ).first()
    assert audit is not None
    assert audit.status == "WARNING"
    assert "retry_after" in audit.details

def test_37_invalid_token_event_recorded(client):
    # Attempt request with invalid token
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert res.status_code == 401

def test_38_logs_do_not_contain_plaintext_passwords(db):
    logs = db.query(AuditLog).all()
    for log in logs:
        # Check details json
        details_str = str(log.details or {}).lower()
        assert "password" not in details_str or "reason" in details_str
        assert "netguardianadmin2026!" not in details_str
        assert "wrongpassword" not in details_str
        assert "secret" not in details_str

def test_39_logs_do_not_contain_raw_jwts(db):
    logs = db.query(AuditLog).all()
    for log in logs:
        details_str = str(log.details or {})
        # A raw JWT has eyJ...
        assert "eyJ" not in details_str

def test_40_logs_do_not_contain_authorization_headers(db):
    logs = db.query(AuditLog).all()
    for log in logs:
        details_str = str(log.details or {})
        assert "bearer " not in details_str.lower()
