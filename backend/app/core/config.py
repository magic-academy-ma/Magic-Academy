from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Magic Academy"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/v1"
    database_url: str | None = None
    db_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "magic_academy"
    postgres_user: str = "postgres"
    postgres_password: str | None = None
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str = Field(min_length=32)
    jwt_issuer: str = "magic-academy-api"
    jwt_audience: str = "magic-academy-web"
    jwt_access_token_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str | URL:
        if self.database_url and self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if self.database_url:
            return self.database_url
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
