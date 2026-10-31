import json
from typing import Annotated, List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_SECRET_KEY = "drishti-aicte-super-secure-secret-key-sih-2026"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in {"prod", "production"}

    PROJECT_NAME: str = "Drishti AICTE"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = INSECURE_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    APP_ENV: str = "development"
    LOGIN_FAILURE_LIMIT: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    
    # Database
    # If DATABASE_URL is not set, default to SQLite for quick local standalone run, or Postgres in Docker
    DATABASE_URL: str = "sqlite:///./drishti.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:80"
    ]
    
    # Storage
    STORAGE_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"]
    
    # SMTP / MailHog
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@drishti.aicte.gov.in"
    EMAILS_FROM_NAME: str = "Drishti AICTE Grievance System"
    ENABLE_EMAIL: bool = True
    
    # AI Similarity Thresholds
    SIMILARITY_HIGH_THRESHOLD: float = 0.80
    SIMILARITY_MEDIUM_THRESHOLD: float = 0.50
    SIMILARITY_LOW_THRESHOLD: float = 0.30
    SIMILARITY_TFIDF_WEIGHT: float = Field(default=0.65, ge=0, le=1)
    SIMILARITY_EMBEDDING_WEIGHT: float = Field(default=0.35, ge=0, le=1)
    SIMILARITY_MULTILINGUAL_ENABLED: bool = True
    SIMILARITY_ENGLISH_MODEL: str = "all-MiniLM-L6-v2"
    SIMILARITY_MULTILINGUAL_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    SIMILARITY_EMBEDDING_CACHE_VERSION: str = "1"

    # Dashboard aggregate cache
    DASHBOARD_CACHE_TTL_SECONDS: int = Field(default=10, ge=1, le=60)
    
    # SLA Configurations (in days)
    SLA_URGENT_DAYS: int = 1
    SLA_HIGH_DAYS: int = 3
    SLA_MEDIUM_DAYS: int = 7
    SLA_LOW_DAYS: int = 14
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return [origin.strip().rstrip("/") for origin in value if origin.strip()]
        raw_value = value.strip()
        if raw_value.startswith("["):
            parsed = json.loads(raw_value)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("BACKEND_CORS_ORIGINS must be a JSON array or comma-separated origins")
            return [origin.strip().rstrip("/") for origin in parsed if origin.strip()]
        return [origin.strip().rstrip("/") for origin in raw_value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_similarity_settings(self):
        if not (
            0 <= self.SIMILARITY_LOW_THRESHOLD
            < self.SIMILARITY_MEDIUM_THRESHOLD
            < self.SIMILARITY_HIGH_THRESHOLD
            <= 1
        ):
            raise ValueError(
                "Similarity thresholds must satisfy 0 <= low < medium < high <= 1."
            )
        total_weight = self.SIMILARITY_TFIDF_WEIGHT + self.SIMILARITY_EMBEDDING_WEIGHT
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError("Similarity weights must sum to 1.")
        return self

settings = Settings()
