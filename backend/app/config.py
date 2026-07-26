from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    acestep_api_url: str = "http://localhost:8001"
    acestep_model: str = "acestep-v15-turbo"

    omniroute_base_url: str = "http://localhost:4000/v1"
    omniroute_api_key: str = "sk-omniroute-local"
    omniroute_model: str = "claude-sonnet-5"

    database_url: str = "sqlite:///./crescendo.db"
    cors_origins: str = "http://localhost:5173"
    poll_interval_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
