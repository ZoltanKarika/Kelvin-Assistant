"""FastAPI application factory."""

from fastapi import FastAPI

from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.api.chat_routes import router as chat_router
from kelvin_assistant.api.routes import router
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.observability.logging import configure_logging
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.sessions import SessionStore


def create_app(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
    session_store: SessionStore | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()
    active_llm_provider = (
        llm_provider if llm_provider is not None else OllamaProvider(active_settings)
    )
    active_session_store = (
        session_store if session_store is not None else InMemorySessionStore()
    )
    active_chat_service = ChatService(
        llm_provider=active_llm_provider,
        session_store=active_session_store,
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
    app.state.chat_service = active_chat_service
    app.include_router(router)
    app.include_router(chat_router)
    return app
