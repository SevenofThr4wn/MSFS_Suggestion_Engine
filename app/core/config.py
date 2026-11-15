from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    APP_NAME: str = "MSFS FlightEngine"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "Testing"
    APP_ENV: str = "development"

    # API
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = (
        f"sqlite:///{(BASE_DIR / 'flightengine.db').as_posix()}"
    )

    DEFAULT_RECOMMENDATION_LIMIT: int = Field(
        default=5,
        ge=1,
        le=100,
    )

    MAX_RECOMMENDATION_LIMIT: int = Field(
        default=25,
        ge=1,
        le=100,
    )

    METAR_API_URL: str = (
        "https://aviationweather.gov/api/data/metar"
    )
    
    # Logging
    LOG_LEVEL: str = "INFO"


    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()


settings = get_settings()
