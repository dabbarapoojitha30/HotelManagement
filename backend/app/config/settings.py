"""
Application settings loaded from environment variables via pydantic-settings.
JWT secrets have no safe defaults — the app will fail-fast if .env is missing.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Single source of truth: backend/.env
ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):

    # Database — strictly loaded from .env
    MONGODB_URL: str = Field(..., description="MongoDB Connection URL")
    DATABASE_NAME: str = Field(..., description="MongoDB Database Name")

    # JWT — strictly loaded from .env (no hardcoded fallback)
    JWT_SECRET: str = Field(..., description="Secret key for signing JWT access tokens")
    JWT_REFRESH_SECRET: str = Field(..., description="Secret key for signing JWT refresh tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email — Gmail SMTP
    GMAIL_APP_PASSWORD: str = ""
    SENDER_EMAIL: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # Hotel Details — strictly loaded from .env (single source of truth)
    HOTEL_NAME: str = Field(..., description="Hotel Name")
    HOTEL_ADDRESS: str = Field(..., description="Hotel Address")
    HOTEL_PHONE: str = Field(..., description="Hotel Contact Phone")
    HOTEL_GSTIN: str = Field(..., description="Hotel GSTIN")


    class Config:
        env_file = str(ENV_FILE_PATH)
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

