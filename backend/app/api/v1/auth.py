from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database.session import get_db
from app.models import User, AuditLog
from app.schemas import Token, LoginRequest, UserResponse, UserCreate
from app.core.security import (
    verify_password,
    create_access_token,
    decode_access_token,
    get_password_hash,
    DUMMY_BCRYPT_HASH
)
from app.core.config import settings
from app.core.rate_limit import (
    login_rate_limiter,
    get_client_ip,
    normalize_username
)
from app.core.dependencies import (
    get_current_user,
    oauth2_scheme,
    require_role,
    require_admin,
    require_engineer
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    Authenticate user, enforce brute-force rate limiting, and issue a hardened JWT.
    Returns 401 with identical generic error for non-existent users and incorrect passwords.
    Returns 429 with Retry-After header when rate limit is exceeded.
    """
    client_ip = get_client_ip(request) if request else "127.0.0.1"
    norm_username = normalize_username(login_data.username)

    # 1. Brute-Force Rate Limiting (IP and Username checks)
    ip_blocked, ip_retry = login_rate_limiter.is_blocked(f"ip:{client_ip}")
    user_blocked, user_retry = login_rate_limiter.is_blocked(f"user:{norm_username}")

    if ip_blocked or user_blocked:
        retry_after = max(ip_retry, user_retry)
        audit = AuditLog(
            username=norm_username,
            action="LOGIN_RATE_LIMITED",
            resource_type="AUTH",
            resource_id="LOGIN_ENDPOINT",
            ip_address=client_ip,
            details={"retry_after": retry_after},
            status="WARNING"
        )
        db.add(audit)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    # 2. Case-insensitive user lookup
    user = db.query(User).filter(func.lower(User.username) == norm_username).first()

    # 3. Credential verification with constant-time comparison and dummy-hash timing attack mitigation
    if user:
        is_pw_valid = verify_password(login_data.password, user.hashed_password)
    else:
        # Run dummy bcrypt check so invalid usernames take identical execution time (~240ms)
        verify_password(login_data.password, DUMMY_BCRYPT_HASH)
        is_pw_valid = False

    if not user or not is_pw_valid or not user.is_active:
        # Record failure for both IP and Username
        login_rate_limiter.record_failure(f"ip:{client_ip}")
        login_rate_limiter.record_failure(f"user:{norm_username}")

        # Audit log failure (NEVER log the password or plaintext secret)
        audit = AuditLog(
            username=norm_username,
            action="USER_LOGIN_FAILED",
            resource_type="AUTH",
            resource_id="LOGIN_ENDPOINT",
            ip_address=client_ip,
            details={"reason": "INVALID_CREDENTIALS"},
            status="FAILED"
        )
        db.add(audit)
        db.commit()

        # Generic public error: never reveal whether the username exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # 4. Success: Reset failed attempt counters
    login_rate_limiter.reset(f"ip:{client_ip}")
    login_rate_limiter.reset(f"user:{norm_username}")

    access_token = create_access_token(subject=user.username, role=user.role)

    # 5. Audit log successful login
    audit = AuditLog(
        username=user.username,
        action="USER_LOGIN",
        resource_type="AUTH",
        resource_id=user.id,
        ip_address=client_ip,
        details={"role": user.role},
        status="SUCCESS"
    )
    db.add(audit)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }

@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """OAuth2 compatible token login endpoint with rate limiting."""
    return login(LoginRequest(username=form_data.username, password=form_data.password), db=db, request=request)

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Retrieve authenticated user details."""
    return current_user
