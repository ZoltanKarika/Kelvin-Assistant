"""FastAPI application factory."""

from fastapi import FastAPI

from kelvin_assistant.api.routes import router
from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    active_settings = settings or get_settings()
    configure_logging(active_settings)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = active_settings
    app.include_router(router)
    return app
