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

    # JWT Security Settings
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: Optional[str] = "netguardian-auth"
    JWT_AUDIENCE: Optional[str] = "netguardian-api"
    JWT_CLOCK_SKEW_SECONDS: int = 10

    # Rate Limiting & Brute-Force Protection
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_COOLDOWN_SECONDS: int = 300
    LOGIN_RATE_LIMIT_BACKEND: str = "memory"

    # Database
    DATABASE_URL: str = "sqlite:///./netguardian.db"

    # Environment: DEV for local development, PROD for production deployments
    ENVIRONMENT: str = "DEV"
    DEMO_MODE: bool = True
    ALLOW_REAL_SSH: bool = False

    # Remediation Execution Security Settings (Phase 5A)
    REMEDIATION_EXECUTION_MODE: str = "SIMULATION"  # SIMULATION, LAB, PRODUCTION
    REMEDIATION_EXECUTION_TIMEOUT_SECONDS: int = 30
    ALLOW_LAB_EXECUTION: bool = False
    ALLOW_PRODUCTION_EXECUTION: bool = False
    AUTHORIZED_LAB_DEVICES: List[str] = Field(default_factory=list)

    # Monitoring & Telemetry Simulation Settings (Milestone 4)
    MONITORING_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_HOURS: int = 72
    TELEMETRY_ENABLED: bool = True
    TELEMETRY_POLLING_INTERVAL_SECONDS: int = 5
    TELEMETRY_RETENTION_HOURS: int = 24
    TELEMETRY_MAX_ACTIVE_FAULTS: int = 10
    TELEMETRY_MAX_FAULT_DURATION_SECONDS: int = 3600
    THRESHOLD_CPU_WARN: float = 75.0
    THRESHOLD_CPU_CRIT: float = 90.0
    THRESHOLD_MEM_WARN: float = 80.0
    THRESHOLD_MEM_CRIT: float = 90.0
    THRESHOLD_UTIL_WARN: float = 75.0
    THRESHOLD_UTIL_CRIT: float = 90.0
    THRESHOLD_LOSS_WARN: float = 2.0
    THRESHOLD_LOSS_CRIT: float = 5.0
    THRESHOLD_LATENCY_WARN: float = 100.0
    THRESHOLD_LATENCY_CRIT: float = 250.0
    THRESHOLD_TEMP_WARN: float = 65.0
    THRESHOLD_TEMP_CRIT: float = 80.0

    # Incident Escalation Policy (Milestone 5)
    ESCALATION_CRITICAL_MINUTES: int = 5
    ESCALATION_MAJOR_MINUTES: int = 15
    ESCALATION_MINOR_MINUTES: int = 30

    # CORS – list of allowed frontend origins
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # Trusted reverse-proxy IP addresses for forwarded headers (e.g. X-Forwarded-Proto, X-Forwarded-For)
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
        # 1. JWT Algorithm validation
        if self.JWT_ALGORITHM.lower() == "none" or self.JWT_ALGORITHM not in {"HS256", "HS384", "HS512"}:
            raise ValueError(f"Invalid or insecure JWT algorithm: '{self.JWT_ALGORITHM}'. Must be a supported HMAC algorithm.")

        # 2. Rate limit boundary validation
        if self.LOGIN_RATE_LIMIT_MAX_ATTEMPTS <= 0:
            raise ValueError("LOGIN_RATE_LIMIT_MAX_ATTEMPTS must be greater than zero.")
        if self.LOGIN_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError("LOGIN_RATE_LIMIT_WINDOW_SECONDS must be greater than zero.")
        if self.LOGIN_RATE_LIMIT_COOLDOWN_SECONDS <= 0:
            raise ValueError("LOGIN_RATE_LIMIT_COOLDOWN_SECONDS must be greater than zero.")
        if self.LOGIN_RATE_LIMIT_BACKEND not in {"memory", "redis"}:
            raise ValueError("LOGIN_RATE_LIMIT_BACKEND must be 'memory' or 'redis'.")

        # 3. Remediation Execution Mode validation
        self.REMEDIATION_EXECUTION_MODE = self.REMEDIATION_EXECUTION_MODE.strip().upper()
        if self.REMEDIATION_EXECUTION_MODE not in {"SIMULATION", "LAB", "PRODUCTION"}:
            raise ValueError("REMEDIATION_EXECUTION_MODE must be 'SIMULATION', 'LAB', or 'PRODUCTION'.")
        if self.REMEDIATION_EXECUTION_TIMEOUT_SECONDS <= 0:
            raise ValueError("REMEDIATION_EXECUTION_TIMEOUT_SECONDS must be greater than zero.")

        if self.ENVIRONMENT == "PROD":
            # Secret Key validation in production
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

            # CORS validation in production
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
