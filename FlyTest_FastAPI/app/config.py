from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FlyTest FastAPI"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = "/api"
    api_version: str = "0.1.0"
    secret_key: str = "change-me"
    database_url: str = "sqlite:///./flytest_fastapi.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
