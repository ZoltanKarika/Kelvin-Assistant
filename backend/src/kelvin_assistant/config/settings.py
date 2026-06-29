"""Application settings loaded from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from kelvin_assistant.version import APP_VERSION

DEFAULT_SYSTEM_PROMPT = (
    "Te Kelvin vagy, egy helyben futó személyes AI-asszisztens. "
    "Alapértelmezetten természetes, nyelvtanilag helyes magyar nyelven "
    "válaszolj. Kerüld a szó szerinti angol fordulatokat és a szükségtelen "
    "idegen szavakat. Légy világos, tényszerű és segítőkész. Ha a felhasználó "
    "más nyelven kérdez, vagy más nyelvű választ kér, válaszolj azon a nyelven. "
    "Ne állítsd, hogy elvégeztél olyan műveletet, amelyhez nincs eszközöd."
)


class Settings(BaseSettings):
    """Runtime settings for the Kelvin Assistant API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="KELVIN_",
        extra="ignore",
    )

    app_name: str = Field(default="Kelvin Assistant")
    app_version: str = Field(default=APP_VERSION)
    environment: str = Field(default="development")
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="gemma4:e4b")
    ollama_embedding_model: str = Field(default="nomic-embed-text")
    embedding_dimension: int = Field(default=768, gt=0)
    ollama_timeout: float = Field(default=120.0, gt=0)
    llm_provider: Literal["ollama"] = Field(default="ollama")
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT, min_length=1)
    database_url: str | None = Field(default=None)
    database_connect_timeout: int = Field(default=5, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings."""

    return Settings()
