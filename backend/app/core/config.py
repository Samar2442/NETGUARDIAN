from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetGuardian"
    TAGLINE: str = "Detect. Understand. Predict. Recover."
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "netguardian-super-secret-production-key-ccna-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./netguardian.db")

    # Environment & Simulation
    DEMO_MODE: bool = True
    ENVIRONMENT: str = "LAB-SIMULATION"
    ALLOW_REAL_SSH: bool = False

    # Monitoring intervals in seconds
    MONITORING_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_HOURS: int = 72

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

    # Validation
    @classmethod
    def __get_validators__(cls):
        yield cls.validate_secret_key

    @classmethod
    def validate_secret_key(cls, values):
        secret = values.get('SECRET_KEY')
        if not secret:
            raise ValueError('SECRET_KEY environment variable must be set')
        if len(secret) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        # Reject default placeholder used for demo only
        if secret == "netguardian-super-secret-production-key-ccna-2026" and not values.get('DEMO_MODE'):
            raise ValueError('Default SECRET_KEY is not allowed in production')
        return values

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./netguardian.db")
    
    # Environment & Simulation
    DEMO_MODE: bool = True
    ENVIRONMENT: str = "LAB-SIMULATION"
    ALLOW_REAL_SSH: bool = False
    
    # Monitoring intervals in seconds
    MONITORING_INTERVAL_SECONDS: int = 10
    METRIC_RETENTION_HOURS: int = 72
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
