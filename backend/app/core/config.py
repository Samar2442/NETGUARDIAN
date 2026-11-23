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

settings = Settings()
