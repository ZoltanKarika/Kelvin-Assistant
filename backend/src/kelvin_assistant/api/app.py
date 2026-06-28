"""FastAPI application factory."""

from fastapi import FastAPI

from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.api.routes import router
from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.observability.logging import configure_logging
from kelvin_assistant.ports.llm import LLMProvider


def create_app(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()
    active_llm_provider = (
        llm_provider if llm_provider is not None else OllamaProvider(active_settings)
    )
    configure_logging(active_settings)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = active_settings
    app.state.llm_provider = active_llm_provider
    app.include_router(router)
    return app
