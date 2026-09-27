from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_provider: str = "none"
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 8
    database_url: str = "sqlite:///./pulsepoint.db"
    cors_origins: str = ""
    use_embeddings: bool = False
    demo_mode: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_cors_origins(self) -> list[str]:
        extras = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return list(dict.fromkeys(["http://localhost:3000", *extras]))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
