from typing import List, Optional
import os
import urllib.parse
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_INSECURE_SECRETS = {
    "netguardian-super-secret-production-key-ccna-2026",
    "REPLACE_WITH_A_SECURE_SECRET",
    "secret",
    "changeme",
    "password",
    "12345678901234567890123456789012",
}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"
    )

    PROJECT_NAME: str = "NetGuardian"
    TAGLINE: str = "Detect. Understand. Predict. Recover."
    API_V1_STR: str = "/api/v1"

    # Secret key for JWT signing. Must be supplied via environment in production.
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./netguardian.db"

    # Environment: DEV for local development, PROD for production deployments
    ENVIRONMENT: str = "DEV"
    DEMO_MODE: bool = True
    ALLOW_REAL_SSH: bool = False

    # Monitoring intervals in seconds
    MONITORING_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_HOURS: int = 72

    # CORS – list of allowed frontend origins
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Trusted reverse-proxy IP addresses for forwarded headers (e.g. X-Forwarded-Proto)
    TRUSTED_PROXIES: List[str] = Field(default_factory=lambda: ["127.0.0.1", "::1"])

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper not in {"DEV", "PROD"}:
            raise ValueError('ENVIRONMENT must be "DEV" or "PROD"')
        return v_upper

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            v = [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: List[str]) -> List[str]:
        cleaned = []
        for origin in v:
            if not origin or not origin.strip():
                raise ValueError("CORS origin cannot be empty")
            if origin == "*":
                cleaned.append(origin)
                continue
            parsed = urllib.parse.urlparse(origin)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError(f"Invalid CORS origin scheme in '{origin}'. Only http and https are allowed.")
            if not parsed.netloc:
                raise ValueError(f"Invalid CORS origin '{origin}': missing host or domain.")
            if parsed.path and parsed.path != "/":
                raise ValueError(f"CORS origin must not contain a path: '{origin}'")
            if parsed.query or parsed.fragment:
                raise ValueError(f"CORS origin must not contain query parameters or fragments: '{origin}'")
            cleaned.append(f"{parsed.scheme}://{parsed.netloc}")
        return cleaned

    @model_validator(mode="after")
    def validate_security_configuration(self):
        if self.ENVIRONMENT == "PROD":
            # 1. Secret Key validation in production
            if not self.SECRET_KEY:
                raise ValueError("SECRET_KEY environment variable is mandatory in production environment.")
            if self.SECRET_KEY in KNOWN_INSECURE_SECRETS or "placeholder" in self.SECRET_KEY.lower():
                raise ValueError(
                    "Known placeholder or insecure SECRET_KEY is strictly rejected in production."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"SECRET_KEY must be at least 32 characters long in production (current length: {len(self.SECRET_KEY)})."
                )

            # 2. CORS validation in production
            if not self.BACKEND_CORS_ORIGINS:
                raise ValueError("BACKEND_CORS_ORIGINS must contain at least one explicit origin in production.")
            for origin in self.BACKEND_CORS_ORIGINS:
                if "*" in origin:
                    raise ValueError("Wildcard CORS origins are strictly forbidden in production.")
        else:
            # DEV mode:
            if not self.SECRET_KEY:
                # Generate a secure ephemeral random secret so no predictable secret is ever hardcoded
                import secrets
                self.SECRET_KEY = secrets.token_hex(32)
            elif len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"SECRET_KEY must be at least 32 characters long (current length: {len(self.SECRET_KEY)})."
                )

        return self

settings = Settings()
