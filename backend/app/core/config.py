from pydantic import BaseModel, validator
from pydantic_settings import BaseSettings
from typing import List
import os
import urllib.parse

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetGuardian"
    TAGLINE: str = "Detect. Understand. Predict. Recover."
    API_V1_STR: str = "/api/v1"
    # Secret key must be provided via environment; fallback is only for development/demo
    SECRET_KEY: str = os.getenv("SECRET_KEY", "netguardian-super-secret-production-key-ccna-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./netguardian.db")

    # Environment & Simulation
    DEMO_MODE: bool = True
    # Allowed values: DEV for local development, PROD for production deployments
    ENVIRONMENT: str = "DEV"
    ALLOW_REAL_SSH: bool = False

    # Monitoring intervals in seconds
    MONITORING_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_HOURS: int = 72

    # CORS – list of allowed origins (comma‑separated in .env)
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

    # ---------------------------------------------------------------------
    # Validators
    # ---------------------------------------------------------------------
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v, values):
        if not v:
            raise ValueError('SECRET_KEY environment variable must be set')
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        # Disallow the development placeholder when running in PROD
        if v == "netguardian-super-secret-production-key-ccna-2026" and values.get('ENVIRONMENT') != "DEV":
            raise ValueError('Default SECRET_KEY is not allowed in production')
        return v

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in {"DEV", "PROD"}:
            raise ValueError('ENVIRONMENT must be "DEV" or "PROD"')
        return v

    @validator("BACKEND_CORS_ORIGINS", each_item=True)
    def validate_cors_origin(cls, v):
        # Must be a valid http/https URL without path, query or fragment
        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f'Invalid CORS origin scheme in {v}')
        if not parsed.netloc:
            raise ValueError(f'Invalid CORS origin netloc in {v}')
        if any([parsed.path, parsed.params, parsed.query, parsed.fragment]):
            raise ValueError(f'CORS origin must not contain path, query or fragment: {v}')
        return v

    @validator("BACKEND_CORS_ORIGINS")
    def validate_cors_list(cls, v, values):
        env = values.get('ENVIRONMENT')
        if env == "PROD":
            if not v:
                raise ValueError('BACKEND_CORS_ORIGINS must contain at least one origin in PROD')
            for origin in v:
                if "*" in origin:
                    raise ValueError('Wildcard origins are not allowed in PROD')
        return v

settings = Settings()