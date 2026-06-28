"""HTTP routes for the public API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import get_llm_provider, get_runtime_settings
from kelvin_assistant.api.schemas import (
    HealthResponse,
    ReadinessResponse,
    RootResponse,
    VersionResponse,
)
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.ports.llm import LLMProvider, LLMProviderError

router = APIRouter()
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
LanguageModelProvider = Annotated[LLMProvider, Depends(get_llm_provider)]


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


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    tags=["system"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The configured language model is not ready.",
        }
    },
)
async def read_readiness(
    settings: RuntimeSettings,
    provider: LanguageModelProvider,
) -> ReadinessResponse:
    """Report whether the configured language model can serve requests."""

    try:
        await provider.check_readiness()
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ReadinessResponse(
        status="ready",
        provider=settings.llm_provider,
        model=settings.ollama_model,
    )


@router.get("/version", response_model=VersionResponse, tags=["system"])
def read_version(settings: RuntimeSettings) -> VersionResponse:
    """Return the application version."""

    return VersionResponse(version=settings.app_version)
