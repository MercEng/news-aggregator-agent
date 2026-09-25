"""Application settings, read from the environment and `.env`.

Import `get_settings()` rather than constructing `Settings()` directly so the
whole process shares one cached instance.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "api-base"
    environment: Environment = "local"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/api_base"
    cors_origins: list[str] = Field(default_factory=list)

    # Only read by the test suite; see tests/conftest.py.
    test_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/api_base_test"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept `a,b` as well as the JSON list pydantic-settings expects."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        if "+asyncpg" not in value and "+aiosqlite" not in value:
            raise ValueError(
                f"{value!r} is not an async DSN; use postgresql+asyncpg://... so SQLAlchemy "
                "can run on the event loop"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
