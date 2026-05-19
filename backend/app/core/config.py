from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BrandVideo API"
    api_prefix: str = "/api"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "brandvideo"
    redis_url: str = "redis://localhost:6379/0"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_default_model: str = "Qwen/Qwen3-8B"
    siliconflow_advanced_model: str = "Qwen/Qwen3-32B"
    tavily_api_key: str = ""
    brand_wiki_root: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

