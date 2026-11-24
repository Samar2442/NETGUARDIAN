from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Callable, Optional
from app.database.session import get_db
from app.models import User, AuditLog
from app.core.security import verify_jwt_token, TokenSecurityError, TokenExpiredError
from app.core.config import settings
from app.core.rate_limit import get_client_ip

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")

def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticate request via JWT and validate against authoritative user database record.
    Enforces:
    - Signature, algorithm, claim structure, and expiration
    - User presence and active status
    - Authoritative role match (rejects tampered or stale role claims)
    - Records security audit events for invalid or expired tokens
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    client_ip = get_client_ip(request) if request else "unknown"

    try:
        payload = verify_jwt_token(token)
    except TokenExpiredError:
        try:
            audit = AuditLog(
                username="anonymous",
                action="TOKEN_VALIDATION_FAILED",
                resource_type="AUTH",
                resource_id="jwt",
                status="FAILED",
                ip_address=client_ip,
                details={"reason": "TOKEN_EXPIRED"}
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except TokenSecurityError as e:
        try:
            audit = AuditLog(
                username="anonymous",
                action="TOKEN_VALIDATION_FAILED",
                resource_type="AUTH",
                resource_id="jwt",
                status="FAILED",
                ip_address=client_ip,
                details={"reason": "INVALID_TOKEN_SECURITY"}
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
        raise credentials_exception

    username: str = payload.get("sub")
    if not username:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise credentials_exception

    # Authoritative Role Verification
    # Prevents privilege escalation through a modified JWT with tampered role claim
    token_role = payload.get("role")
    if token_role and token_role != user.role:
        try:
            audit = AuditLog(
                username=user.username,
                action="ROLE_ESCALATION_ATTEMPT",
                resource_type="AUTH",
                resource_id=user.id,
                status="FAILED",
                ip_address=client_ip,
                details={"token_role": token_role, "authoritative_role": user.role}
            )
            db.add(audit)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token role does not match authoritative user record",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def require_role(allowed_roles: List[str]) -> Callable:
    """Dependency factory enforcing server-side Role-Based Access Control (RBAC)."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient privileges for this operation",
            )
        return current_user
    return role_checker

# Standard role guards
require_admin = require_role(["admin"])
require_engineer = require_role(["admin", "network_engineer"])
require_viewer = require_role(["admin", "network_engineer", "viewer"])
