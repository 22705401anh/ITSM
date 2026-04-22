import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "KOSTAL ITSM"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"
    SQLALCHEMY_ECHO: bool = False

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email/Notifications
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@itsm.local"
    SMTP_ENABLED: bool = False

    # File uploads
    UPLOAD_DIR: str = "./storage/uploads"
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./storage/logs/app.log"

    # API
    API_PREFIX: str = "/api"

    # Web UI
    TEMPLATES_DIR: str = "./app/web/templates"
    STATIC_DIR: str = "./app/web/static"

    # LDAP
    LDAP_SERVER: str = "ldap://MAGEAD101.ma.kostal.int"
    LDAP_PORT: int = 389
    LDAP_BASE_DN: str = "DC=ma,DC=kostal,DC=int"
    LDAP_BIND_DN: str = "CN=kaziz999,OU=GE,OU=USR,DC=ma,DC=kostal,DC=int"
    LDAP_PASSWORD: str = "jkfnJKF#44"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()


settings = get_settings()
