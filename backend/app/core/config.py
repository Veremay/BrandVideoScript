from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BrandVideo API"
    api_prefix: str = "/api"
    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001"
    )
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "brandvideo"
    redis_url: str = "redis://localhost:6379/0"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_default_model: str = "Qwen/Qwen3-8B"
    siliconflow_advanced_model: str = "Qwen/Qwen3-32B"
    tavily_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins(settings: Settings) -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

