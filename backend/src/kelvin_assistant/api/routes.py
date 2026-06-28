"""HTTP routes for the public API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from kelvin_assistant.api.dependencies import get_runtime_settings
from kelvin_assistant.api.schemas import HealthResponse, RootResponse, VersionResponse
from kelvin_assistant.config.settings import Settings

router = APIRouter()
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]


@router.get("/", response_model=RootResponse, tags=["system"])
def read_root(settings: RuntimeSettings) -> RootResponse:
    """Return a short application summary."""

    return RootResponse(
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
def read_health() -> HealthResponse:
    """Return a minimal health response."""

    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse, tags=["system"])
def read_version(settings: RuntimeSettings) -> VersionResponse:
    """Return the application version."""

    return VersionResponse(version=settings.app_version)
