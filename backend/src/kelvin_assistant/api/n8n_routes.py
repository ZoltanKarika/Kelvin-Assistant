"""Versioned API routes for checking n8n reachability and health."""

from datetime import UTC, datetime
from typing import Annotated

import httpx2
from fastapi import APIRouter, Depends, status

from kelvin_assistant.api.dependencies import (
    get_runtime_settings,
    require_scope,
)
from kelvin_assistant.api.schemas import N8NHealthResponse
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope

router = APIRouter(prefix="/api/v1/n8n", tags=["n8n"])

RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]


@router.get(
    "/health",
    response_model=N8NHealthResponse,
    status_code=status.HTTP_200_OK,
)
async def check_n8n_health(
    settings: RuntimeSettings,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
) -> N8NHealthResponse:
    """Check if the configured n8n endpoint is healthy and reachable."""
    now = datetime.now(UTC)

    if not settings.n8n_url:
        return N8NHealthResponse(
            status="unconfigured",
            configured=False,
            base_url=None,
            last_checked=now,
            error_message="n8n URL is not configured.",
        )

    try:
        headers = {}
        if settings.n8n_token:
            headers["X-N8N-API-KEY"] = settings.n8n_token

        async with httpx2.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.n8n_url, headers=headers)

            if response.status_code >= 500:
                return N8NHealthResponse(
                    status="degraded",
                    configured=True,
                    base_url=settings.n8n_url,
                    last_checked=now,
                    error_message=(
                        f"n8n returned server error: HTTP {response.status_code}"
                    ),
                )

            return N8NHealthResponse(
                status="healthy",
                configured=True,
                base_url=settings.n8n_url,
                last_checked=now,
            )

    except httpx2.HTTPStatusError as exc:
        return N8NHealthResponse(
            status="degraded",
            configured=True,
            base_url=settings.n8n_url,
            last_checked=now,
            error_message=f"HTTP Error: {exc}",
        )
    except (httpx2.RequestError, Exception) as exc:
        return N8NHealthResponse(
            status="unreachable",
            configured=True,
            base_url=settings.n8n_url,
            last_checked=now,
            error_message=f"Connection failed: {exc}",
        )
