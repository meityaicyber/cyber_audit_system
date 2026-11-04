from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cyber_audit"

    # JWT
    SECRET_KEY: str = "change-this-to-a-secure-256-bit-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # File Storage
    STORAGE_PATH: str = "/storage/reports"
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".txt"]
    MAX_FILE_SIZE_MB: int = 1000

    # SeaweedFS Storage
    SEAWEEDFS_FILER_URL: str = "http://localhost:8888"

    # File Encryption
    FILE_ENCRYPTION_KEY: str = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="

    # ClamAV Integration
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = 3310

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # AI Pipeline Service
    AI_PIPELINE_URL: str = "http://ai-pipeline:8001"
    RAG_SERVICE_URL: str = "http://localhost:8077"

    # Admin defaults
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@123"
    DEFAULT_ADMIN_EMAIL: str = "admin@cyberaudit.local"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
