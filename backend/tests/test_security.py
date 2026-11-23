import os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_allowed_origin_header():
    # Use one of the allowed origins
    origin = settings.BACKEND_CORS_ORIGINS[0]
    response = client.get("/", headers={"Origin": origin})
    assert response.status_code == 200
    # CORS header should be present and match the origin
    assert response.headers.get("access-control-allow-origin") == origin

def test_disallowed_origin_no_cors_header():
    response = client.get("/", headers={"Origin": "http://evil.com"})
    # FastAPI returns 200 but without the CORS header (browser would block)
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers

def test_preflight_allowed():
    origin = settings.BACKEND_CORS_ORIGINS[0]
    response = client.options(
        "/",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert response.status_code == 200
    # Should echo allowed methods and headers
    allow_methods = response.headers.get("access-control-allow-methods")
    assert allow_methods is not None
    for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]:
        assert method in allow_methods
    allow_headers = response.headers.get("access-control-allow-headers")
    assert allow_headers is not None
    for hdr in ["Authorization", "Content-Type", "Accept"]:
        assert hdr in allow_headers
    # Origin header should be echoed
    assert response.headers.get("access-control-allow-origin") == origin

def test_preflight_disallowed_origin():
    response = client.options(
        "/",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    # Starlette returns 200 but without CORS headers
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers

def test_security_headers_present():
    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    # CSP should be present
    assert "content-security-policy" in headers
    # HSTS should NOT be present in DEV mode
    if settings.ENVIRONMENT == "PROD":
        assert "strict-transport-security" in headers
    else:
        assert "strict-transport-security" not in headers
