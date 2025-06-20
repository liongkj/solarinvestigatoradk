"""Configuration settings for Solar Investigator ADK"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    app_name: str = Field(
        default="Solar Investigator ADK", description="Application name"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=False, description="Auto-reload on code changes")

    # Google Cloud Configuration
    google_project_id: Optional[str] = Field(
        default=None, description="Google Cloud project ID"
    )
    google_application_credentials: Optional[str] = Field(
        default=None, description="Path to Google credentials JSON"
    )

    # Investigation Configuration
    max_investigation_duration: int = Field(
        default=300, description="Max investigation duration in seconds"
    )
    max_concurrent_investigations: int = Field(
        default=10, description="Max concurrent investigations"
    )

    # Session and Memory Configuration
    session_ttl: int = Field(default=3600, description="Session TTL in seconds")
    memory_max_tokens: int = Field(default=4096, description="Memory max tokens")

    # Database Configuration for ADK DatabaseSessionService
    database_url: str = Field(
        default="postgresql://adk_user:my-password@localhost:9432/adk_db",
        description="Database URL for ADK session storage (SQLite for dev, PostgreSQL for prod)",
    )
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy echo")
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    # Redis Configuration (optional)
    # redis_url: Optional[str] = Field(
    #     default="redis://localhost:6379",
    #     description="Redis URL for caching and pub/sub",
    # )

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:4200",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:4200",
            "http://127.0.0.1:5173",
        ],
        description="CORS allowed origins",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="CORS allow credentials"
    )
    cors_allow_methods: list[str] = Field(
        default=["*"], description="CORS allowed methods"
    )
    cors_allow_headers: list[str] = Field(
        default=["*"], description="CORS allowed headers"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings
