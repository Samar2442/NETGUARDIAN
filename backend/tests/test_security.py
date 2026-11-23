import os
import pytest
from pydantic import ValidationError
from app.core.config import Settings, settings
from app.websocket.manager import ws_manager
from starlette.testclient import TestClient

# ==============================================================================
# 1. SECRET_KEY & CONFIGURATION TESTS (RULES 2 & 8)
# ==============================================================================

def test_secret_key_missing_in_prod_raises_error():
    """In PROD, missing SECRET_KEY must raise ValidationError."""
    with pytest.raises(ValidationError) as exc:
        Settings(ENVIRONMENT="PROD", SECRET_KEY=None)
    assert "SECRET_KEY environment variable is mandatory" in str(exc.value)

def test_secret_key_weak_in_prod_raises_error():
    """In PROD, SECRET_KEY with fewer than 32 characters must be rejected."""
    with pytest.raises(ValidationError) as exc:
        Settings(ENVIRONMENT="PROD", SECRET_KEY="short-secret-key-only-24c")
    assert "at least 32 characters long" in str(exc.value)

def test_secret_key_weak_in_dev_raises_error():
    """In DEV, if an explicit SECRET_KEY is supplied, it must also be >= 32 characters."""
    with pytest.raises(ValidationError) as exc:
        Settings(ENVIRONMENT="DEV", SECRET_KEY="too-short")
    assert "at least 32 characters long" in str(exc.value)

def test_secret_key_placeholder_in_prod_raises_error():
    """In PROD, known development placeholders must be strictly rejected."""
    placeholders = [
        "netguardian-super-secret-production-key-ccna-2026",
        "REPLACE_WITH_A_SECURE_SECRET",
        "12345678901234567890123456789012",
        "placeholder-super-long-insecure-secret-key-prod",
    ]
    for ph in placeholders:
        with pytest.raises(ValidationError) as exc:
            Settings(ENVIRONMENT="PROD", SECRET_KEY=ph)
        assert "insecure SECRET_KEY is strictly rejected" in str(exc.value)

def test_secret_key_valid_in_prod_succeeds():
    """In PROD, a strong unique 32+ character key is accepted."""
    valid_key = "a" * 32 + "-production-secure-key"
    s = Settings(
        ENVIRONMENT="PROD",
        SECRET_KEY=valid_key,
        BACKEND_CORS_ORIGINS=["https://netguardian.saturnx.local"]
    )
    assert s.SECRET_KEY == valid_key
    assert s.ENVIRONMENT == "PROD"

def test_secret_key_missing_in_dev_generates_ephemeral_key():
    """In DEV, if SECRET_KEY is omitted, a random secure 64-char key is generated."""
    s = Settings(ENVIRONMENT="DEV", SECRET_KEY=None)
    assert s.SECRET_KEY is not None
    assert len(s.SECRET_KEY) >= 64
    assert s.SECRET_KEY != "netguardian-super-secret-production-key-ccna-2026"

def test_production_missing_credentials_raises_error():
    """In PROD, missing initial credentials in seed_database must fail safely."""
    from app.database.seed import seed_database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database.session import Base

    mem_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=mem_engine)
    mem_session = sessionmaker(bind=mem_engine)()

    old_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "PROD"
    old_admin = os.environ.pop("ADMIN_PASSWORD", None)
    try:
        with pytest.raises(RuntimeError) as exc:
            seed_database(db=mem_session)
        assert "ADMIN_PASSWORD" in str(exc.value)
    finally:
        settings.ENVIRONMENT = old_env
        if old_admin:
            os.environ["ADMIN_PASSWORD"] = old_admin
        mem_session.close()


# ==============================================================================
# 2. CORS RESTRICTIONS TESTS (RULE 3)
# ==============================================================================

def test_cors_approved_origin_simple_request(client):
    """Approved frontend origin receives 200 and matching Access-Control-Allow-Origin."""
    origin = settings.BACKEND_CORS_ORIGINS[0]
    res = client.get("/", headers={"Origin": origin})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin

def test_cors_disallowed_origin_receives_no_allow_header(client):
    """Unapproved origin receives no Access-Control-Allow-Origin header."""
    res = client.get("/", headers={"Origin": "http://malicious-attacker.com"})
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers

def test_cors_approved_options_preflight(client):
    """Approved preflight receives 200 with allowed methods, headers, and origin."""
    origin = settings.BACKEND_CORS_ORIGINS[0]
    res = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    allow_methods = res.headers.get("access-control-allow-methods", "")
    for m in ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]:
        assert m in allow_methods
    allow_headers = res.headers.get("access-control-allow-headers", "")
    for h in ["Authorization", "Content-Type", "Accept"]:
        assert h in allow_headers

def test_cors_disallowed_options_preflight(client):
    """Disallowed preflight is rejected and does not receive access-control-allow-origin."""
    res = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    # Starlette CORSMiddleware rejects disallowed preflights with 400 Bad Request
    assert res.status_code in {200, 400}
    assert "access-control-allow-origin" not in res.headers

def test_cors_credentials_disabled_by_default(client):
    """Ensure access-control-allow-credentials is not set to true."""
    origin = settings.BACKEND_CORS_ORIGINS[0]
    res = client.get("/", headers={"Origin": origin})
    assert res.headers.get("access-control-allow-credentials") != "true"

def test_cors_multiple_configured_origins(client):
    """Ensure multiple allowed origins all receive authorization."""
    for origin in settings.BACKEND_CORS_ORIGINS:
        res = client.get("/", headers={"Origin": origin})
        assert res.headers.get("access-control-allow-origin") == origin

def test_cors_wildcard_rejected_in_prod():
    """In PROD, wildcard CORS origin is strictly forbidden."""
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="PROD",
            SECRET_KEY="a" * 32,
            BACKEND_CORS_ORIGINS=["*"]
        )
    assert "Wildcard CORS origins are strictly forbidden in production" in str(exc.value)

def test_cors_invalid_origin_format_rejected():
    """Invalid origins (bad scheme, path, query) are rejected."""
    bad_origins = [
        "ftp://localhost:5173",
        "http://localhost:5173/api/v1",
        "http://localhost:5173?foo=bar",
        "",
    ]
    for bad in bad_origins:
        with pytest.raises(ValidationError):
            Settings(BACKEND_CORS_ORIGINS=[bad])


# ==============================================================================
# 3. HTTP SECURITY HEADERS & CSP TESTS (RULE 4)
# ==============================================================================

def test_standard_security_headers_present(client):
    """Every HTTP response must contain nosniff, DENY, and strict-origin."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

def test_csp_header_structure_in_dev(client):
    """CSP in DEV must restrict object-src, frame-ancestors, and support ws/connect."""
    res = client.get("/health")
    csp = res.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "connect-src" in csp
    assert "ws:" in csp


# ==============================================================================
# 4. HSTS STRICT CONDITIONAL VERIFICATION (RULE 5)
# ==============================================================================

def test_hsts_omitted_on_dev_http(client):
    """DEV + HTTP: HSTS must be omitted."""
    settings.ENVIRONMENT = "DEV"
    res = client.get("/health")
    assert "strict-transport-security" not in res.headers

def test_hsts_omitted_on_dev_https(client):
    """DEV + HTTPS: HSTS must be omitted."""
    settings.ENVIRONMENT = "DEV"
    res = client.get("https://testserver/health")
    assert "strict-transport-security" not in res.headers

def test_hsts_omitted_on_prod_http(client):
    """PROD + HTTP: HSTS must be omitted (plain HTTP cannot assert HSTS)."""
    old_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "PROD"
    try:
        res = client.get("http://testserver/health")
        assert "strict-transport-security" not in res.headers
    finally:
        settings.ENVIRONMENT = old_env

def test_hsts_included_on_prod_https(client):
    """PROD + Verified HTTPS: HSTS must be present."""
    old_env = settings.ENVIRONMENT
    settings.ENVIRONMENT = "PROD"
    try:
        res = client.get("https://testserver/health")
        assert res.headers.get("strict-transport-security") == "max-age=31536000"
    finally:
        settings.ENVIRONMENT = old_env

def test_hsts_untrusted_proxy_forwarded_proto_ignored(client):
    """PROD + Untrusted proxy X-Forwarded-Proto header must NOT trigger HSTS."""
    old_env = settings.ENVIRONMENT
    old_trusted = settings.TRUSTED_PROXIES
    settings.ENVIRONMENT = "PROD"
    settings.TRUSTED_PROXIES = []  # No trusted proxies
    try:
        res = client.get(
            "http://testserver/health",
            headers={"X-Forwarded-Proto": "https"}
        )
        assert "strict-transport-security" not in res.headers
    finally:
        settings.ENVIRONMENT = old_env
        settings.TRUSTED_PROXIES = old_trusted

def test_hsts_trusted_proxy_forwarded_proto_accepted(client):
    """PROD + Trusted proxy X-Forwarded-Proto header triggers HSTS."""
    old_env = settings.ENVIRONMENT
    old_trusted = settings.TRUSTED_PROXIES
    settings.ENVIRONMENT = "PROD"
    settings.TRUSTED_PROXIES = ["testclient"]
    try:
        res = client.get(
            "http://testserver/health",
            headers={"X-Forwarded-Proto": "https"}
        )
        assert res.headers.get("strict-transport-security") == "max-age=31536000"
    finally:
        settings.ENVIRONMENT = old_env
        settings.TRUSTED_PROXIES = old_trusted


# ==============================================================================
# 5. ERROR RESPONSES SECURITY HEADERS (RULE 6)
# ==============================================================================

def test_security_headers_on_404_not_found(client):
    """404 Not Found response must include security headers."""
    res = client.get("/api/v1/nonexistent-route-for-testing")
    assert res.status_code == 404
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in res.headers

def test_security_headers_on_401_unauthorized(client):
    """401 Unauthorized response must include security headers."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in res.headers

def test_cors_and_security_headers_coexist_on_error(client):
    """CORS headers and security headers must both be present on error responses."""
    origin = settings.BACKEND_CORS_ORIGINS[0]
    res = client.get(
        "/api/v1/nonexistent-route-with-origin",
        headers={"Origin": origin}
    )
    assert res.status_code == 404
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"


# ==============================================================================
# 6. WEBSOCKET TEST (RULE 7)
# ==============================================================================

def test_websocket_connection_and_broadcast(client):
    """Test WebSocket connection, ping, broadcast reception, and clean disconnect."""
    initial_count = len(ws_manager.active_connections)
    with client.websocket_connect("/ws") as websocket:
        assert len(ws_manager.active_connections) == initial_count + 1
        # Send text ping to server
        websocket.send_text("client_ping")

        # Broadcast telemetry message from server
        import asyncio
        test_payload = {"type": "TEST_BROADCAST", "data": {"health": 98.5}}
        asyncio.run(ws_manager.broadcast(test_payload))

        # Client receives broadcast
        received = websocket.receive_json()
        assert received["type"] == "TEST_BROADCAST"
        assert received["data"]["health"] == 98.5

    # After exiting with block, client is disconnected
    assert len(ws_manager.active_connections) == initial_count
