"""FastAPI dependencies."""

from typing import cast

from fastapi import Request

from kelvin_assistant.config.settings import Settings
from kelvin_assistant.ports.llm import LLMProvider


def get_runtime_settings(request: Request) -> Settings:
    """Return the settings object attached to the app state."""

    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        msg = "Application settings are not configured."
        raise RuntimeError(msg)
    return settings


def get_llm_provider(request: Request) -> LLMProvider:
    """Return the language model provider attached to the app state."""

    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        msg = "Language model provider is not configured."
        raise RuntimeError(msg)
    return cast(LLMProvider, provider)
