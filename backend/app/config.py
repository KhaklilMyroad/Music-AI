from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    acestep_api_url: str = "http://localhost:8001"
    acestep_model: str = "acestep-v15-turbo"
    # flac is the engine's native default; mp3 requires ffmpeg on the engine host
    # (saving fails silently with an empty file path when it's missing).
    acestep_audio_format: str = "flac"

    omniroute_base_url: str = "http://localhost:4000/v1"
    omniroute_api_key: str = "sk-omniroute-local"
    omniroute_model: str = "claude-sonnet-5"

    database_url: str = "sqlite:///./crescendo.db"
    media_dir: str = "./media"
    mastering_enabled: bool = True
    # -9 LUFS = loud club master; use -14 for streaming-platform delivery
    master_lufs: float = -9.0
    cors_origins: str = "http://localhost:5173"
    poll_interval_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
