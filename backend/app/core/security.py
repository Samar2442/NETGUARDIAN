import uuid
import logging
import bcrypt
import jwt
from jwt import exceptions as jwt_exceptions
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from app.core.config import settings

logger = logging.getLogger("netguardian.auth")

class TokenSecurityError(Exception):
    """Base exception for JWT security validation errors."""
    pass

class TokenExpiredError(TokenSecurityError):
    pass

class TokenSignatureError(TokenSecurityError):
    pass

class TokenClaimError(TokenSecurityError):
    pass

# Precomputed dummy bcrypt hash (work factor 12) to mitigate user-enumeration timing attacks.
# Matches format of standard bcrypt hash for nonexistent user evaluation.
DUMMY_BCRYPT_HASH = "$2b$12$e8Y0wU3aY0m7A9V7eS6xqunF2h1e0XGZ2wY3v4u5t6s7r8q9p0o1n"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash in constant-time comparison."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Password verification encountered error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with work factor = 12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def create_access_token(
    subject: str | Any,
    role: str,
    expires_delta: Optional[timedelta] = None,
    custom_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a cryptographically signed JWT with explicit claims:
    - sub (subject / username)
    - role (authoritative user role)
    - iat (issued at, UTC epoch)
    - exp (expiration, UTC epoch)
    - jti (unique token identifier)
    - iss (issuer)
    - aud (audience)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "role": str(role),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    if settings.JWT_ISSUER:
        payload["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        payload["aud"] = settings.JWT_AUDIENCE

    if custom_claims:
        payload.update(custom_claims)

    encoded_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Strictly verify and decode a JWT.
    Enforces:
    - Algorithm restriction (HS256 only; no 'none' or untrusted algorithms)
    - Cryptographic signature check
    - Required claims ('sub', 'iat', 'exp', 'jti')
    - Clock skew tolerance (leeway)
    - Issuer & Audience checks (if configured)
    - Claim type validation
    """
    if not token or not isinstance(token, str):
        raise TokenClaimError("Token must be a non-empty string")

    options = {
        "require": ["exp", "iat", "sub", "jti"],
        "verify_signature": True,
        "verify_exp": True,
        "verify_iat": True,
    }

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options=options,
            issuer=settings.JWT_ISSUER if settings.JWT_ISSUER else None,
            audience=settings.JWT_AUDIENCE if settings.JWT_AUDIENCE else None,
            leeway=settings.JWT_CLOCK_SKEW_SECONDS,
        )
    except jwt_exceptions.ExpiredSignatureError as e:
        raise TokenExpiredError(f"Token has expired: {e}")
    except jwt_exceptions.InvalidSignatureError as e:
        raise TokenSignatureError(f"Invalid token signature: {e}")
    except jwt_exceptions.ImmatureSignatureError as e:
        raise TokenClaimError(f"Token issued in the future (exceeds clock skew): {e}")
    except jwt_exceptions.MissingRequiredClaimError as e:
        raise TokenClaimError(f"Missing mandatory claim: {e}")
    except jwt_exceptions.InvalidSubjectError as e:
        raise TokenClaimError(f"Invalid subject claim type: {e}")
    except (jwt_exceptions.InvalidIssuerError, jwt_exceptions.InvalidAudienceError) as e:
        raise TokenSecurityError(f"Invalid token claims (issuer/audience): {e}")
    except (jwt_exceptions.InvalidAlgorithmError, jwt_exceptions.DecodeError) as e:
        raise TokenSecurityError(f"Invalid token structure or algorithm: {e}")
    except jwt_exceptions.PyJWTError as e:
        raise TokenSecurityError(f"Token validation failed: {e}")

    # Validate claim types
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise TokenClaimError("Claim 'sub' must be a non-empty string")

    role = payload.get("role")
    if role is not None and not isinstance(role, str):
        raise TokenClaimError("Claim 'role' must be a string")

    return payload

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Backward-compatible decoder.
    Returns decoded claims dict if valid; returns None if invalid or expired.
    """
    try:
        return verify_jwt_token(token)
    except TokenSecurityError as e:
        logger.debug(f"JWT decode rejected: {e}")
        return None
