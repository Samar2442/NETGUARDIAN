import pytest
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token

def test_password_hashing():
    pw = "CiscoCCNA2026!Secure"
    hashed = get_password_hash(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

def test_jwt_token_generation_and_decoding():
    token = create_access_token(subject="admin", role="admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"

def test_api_login_success_and_failure(db):
    from app.api.v1.auth import login
    from app.schemas import LoginRequest
    from fastapi import HTTPException

    # Valid credentials
    res = login(LoginRequest(
        username="admin",
        password="NetGuardianAdmin2026!"
    ), db)
    assert "access_token" in res
    assert res["role"] == "admin"

    # Invalid password
    with pytest.raises(HTTPException):
        login(LoginRequest(
            username="admin",
            password="WrongPassword"
        ), db)
