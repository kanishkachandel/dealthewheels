from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DEALTHEWHEELS"
    database_url: str = "sqlite:///./dealthewheels.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-secret-change-me"
    jwt_algorithm: str = "HS256"
    token_expiry_minutes: int = 480
    cooloff_minutes: int = 15
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
