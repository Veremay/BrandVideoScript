from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime values are defined in `.env` (see `.env.example`)."""

    app_name: str
    api_prefix: str
    cors_origins: str
    mongodb_url: str
    mongodb_db: str
    redis_url: str
    siliconflow_api_key: str = ""
    siliconflow_base_url: str
    siliconflow_default_model: str
    siliconflow_advanced_model: str
    siliconflow_request_timeout_seconds: float
    siliconflow_stream_timeout_seconds: float
    tavily_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins(settings: Settings) -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
