"""HTTP routes for the public API."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from kelvin_assistant.api.dependencies import (
    get_database_client,
    get_llm_provider,
    get_runtime_settings,
    require_scope,
)
from kelvin_assistant.api.schemas import (
    DatabaseReadinessResponse,
    HealthResponse,
    ReadinessResponse,
    RootResponse,
    RuntimeComponentStatus,
    RuntimeStatusResponse,
    VersionResponse,
)
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.ports.database import DatabaseClient, DatabaseError
from kelvin_assistant.ports.llm import LLMProvider, LLMProviderError

router = APIRouter()
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
LanguageModelProvider = Annotated[LLMProvider, Depends(get_llm_provider)]
RuntimeDatabaseClient = Annotated[DatabaseClient, Depends(get_database_client)]


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
    "/status",
    response_model=RuntimeStatusResponse,
    tags=["system"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token."},
        status.HTTP_403_FORBIDDEN: {"description": "Token lacks required scope."},
    },
)
async def read_runtime_status(
    settings: RuntimeSettings,
    provider: LanguageModelProvider,
    database_client: RuntimeDatabaseClient,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
) -> RuntimeStatusResponse:
    """Return an aggregate runtime view without failing on degraded components."""

    components = [
        RuntimeComponentStatus(
            name="api",
            status="ready",
            required=True,
            detail="FastAPI process is running.",
        ),
        RuntimeComponentStatus(
            name="auth",
            status="ready" if settings.api_auth_mode == "required" else "disabled",
            required=settings.environment == "production",
            detail=(
                "API authentication is required."
                if settings.api_auth_mode == "required"
                else "API authentication is disabled; use only for local development."
            ),
        ),
    ]

    try:
        await provider.check_readiness()
    except LLMProviderError as exc:
        components.append(
            RuntimeComponentStatus(
                name="llm",
                status="unavailable",
                required=True,
                detail=str(exc),
            )
        )
    else:
        components.append(
            RuntimeComponentStatus(
                name="llm",
                status="ready",
                required=True,
                detail=f"{settings.llm_provider}:{settings.ollama_model}",
            )
        )

    if settings.database_url is None:
        components.append(
            RuntimeComponentStatus(
                name="database",
                status="unconfigured",
                required=False,
                detail=(
                    "KELVIN_DATABASE_URL is not configured; persistence-backed "
                    "features may use in-memory stores or be unavailable."
                ),
            )
        )
    else:
        try:
            await database_client.check_readiness()
        except DatabaseError as exc:
            components.append(
                RuntimeComponentStatus(
                    name="database",
                    status="unavailable",
                    required=True,
                    detail=str(exc),
                )
            )
        else:
            components.append(
                RuntimeComponentStatus(
                    name="database",
                    status="ready",
                    required=True,
                    detail="PostgreSQL connection is ready.",
                )
            )

    components.append(
        RuntimeComponentStatus(
            name="n8n",
            status="ready" if settings.n8n_url else "unconfigured",
            required=False,
            detail=(
                "n8n URL is configured; use /api/v1/n8n/health for reachability."
                if settings.n8n_url
                else "n8n is optional and not configured."
            ),
        )
    )

    overall_status = _aggregate_runtime_status(components)
    return RuntimeStatusResponse(status=overall_status, components=components)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    tags=["system"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token."},
        status.HTTP_403_FORBIDDEN: {"description": "Token lacks required scope."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The configured language model is not ready.",
        },
    },
)
async def read_readiness(
    settings: RuntimeSettings,
    provider: LanguageModelProvider,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
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


@router.get(
    "/ready/database",
    response_model=DatabaseReadinessResponse,
    tags=["system"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token."},
        status.HTTP_403_FORBIDDEN: {"description": "Token lacks required scope."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The configured database is not ready.",
        },
    },
)
async def read_database_readiness(
    database_client: RuntimeDatabaseClient,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
) -> DatabaseReadinessResponse:
    """Report whether the configured database can serve requests."""

    try:
        await database_client.check_readiness()
    except DatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return DatabaseReadinessResponse(status="ready", provider="postgresql")


@router.get("/version", response_model=VersionResponse, tags=["system"])
def read_version(settings: RuntimeSettings) -> VersionResponse:
    """Return the application version."""

    return VersionResponse(version=settings.app_version)


def _aggregate_runtime_status(
    components: list[RuntimeComponentStatus],
) -> Literal["ready", "degraded", "unavailable"]:
    if any(
        component.required
        and component.status in {"disabled", "unconfigured", "unavailable"}
        for component in components
    ):
        return "unavailable"
    if any(
        component.name == "database" and component.status == "unconfigured"
        for component in components
    ):
        return "degraded"
    if any(
        not component.required and component.status == "unavailable"
        for component in components
    ):
        return "degraded"
    return "ready"
