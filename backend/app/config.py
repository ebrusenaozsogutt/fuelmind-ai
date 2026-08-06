"""Central application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment-variable overrides."""

    APP_NAME: str = "FuelMind AI Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    DATABASE_URL: str = "postgresql+psycopg://fuelmind_user@localhost:5432/fuelmind_db"
    SECRET_KEY: str
    # Token expiration time (in minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    ENABLE_DEMO_USERS: bool = False
    DEMO_ADMIN_PASSWORD: str | None = None
    DEMO_OPERATOR_PASSWORD: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""

    return Settings()


settings = get_settings()
