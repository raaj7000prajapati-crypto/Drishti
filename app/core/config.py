import os
from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "Drishti AICTE"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "drishti-aicte-super-secure-secret-key-sih-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day for demo convenience
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    # If DATABASE_URL is not set, default to SQLite for quick local standalone run, or Postgres in Docker
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./drishti.db")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:80"
    ]
    
    # Storage
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./uploads")
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"]
    
    # SMTP / MailHog
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "1025"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAILS_FROM_EMAIL: str = os.getenv("EMAILS_FROM_EMAIL", "noreply@drishti.aicte.gov.in")
    EMAILS_FROM_NAME: str = "Drishti AICTE Grievance System"
    ENABLE_EMAIL: bool = True
    
    # AI Similarity Thresholds
    SIMILARITY_HIGH_THRESHOLD: float = 0.80
    SIMILARITY_MEDIUM_THRESHOLD: float = 0.50
    SIMILARITY_LOW_THRESHOLD: float = 0.30
    
    # SLA Configurations (in days)
    SLA_URGENT_DAYS: int = 1
    SLA_HIGH_DAYS: int = 3
    SLA_MEDIUM_DAYS: int = 7
    SLA_LOW_DAYS: int = 14
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
