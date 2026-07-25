"""
Application settings loaded from environment variables via pydantic-settings.
JWT secrets have no safe defaults — the app will fail-fast if .env is missing.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "vvresidency"

    # JWT — no safe defaults; .env MUST provide these in production
    JWT_SECRET: str = Field(
        default="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        description="Secret key for signing JWT access tokens",
    )
    JWT_REFRESH_SECRET: str = Field(
        default="730dbf2cc81df98db1598e040f3532b2f6efba2a8c3d4dbb6b3de21c3b1e9c8f",
        description="Secret key for signing JWT refresh tokens",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email — Brevo Transactional API
    BREVO_API_KEY: str = ""
    SENDER_EMAIL:  str = ""

    # Algorithm constant
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
