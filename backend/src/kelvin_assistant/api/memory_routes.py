"""Versioned memory API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from kelvin_assistant.api.dependencies import RequireScope, get_memory_service
from kelvin_assistant.api.schemas import (
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryResponse,
)
from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.domain.auth import ApiScope
from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.memory import (
    MemoryRepositoryConfigurationError,
    MemoryRepositoryUnavailableError,
)

router = APIRouter(prefix="/api/v1", tags=["memory"])
RuntimeMemoryService = Annotated[MemoryService, Depends(get_memory_service)]
ReadMemoryAccess = Annotated[None, Depends(RequireScope(ApiScope.MEMORY_READ))]
UNPROCESSABLE_CONTENT = 422


@router.post(
    "/memory",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        UNPROCESSABLE_CONTENT: {"description": "Invalid memory item."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Memory repository unavailable.",
        },
    },
)
async def create_memory(
    request: MemoryCreateRequest,
    memory_service: RuntimeMemoryService,
) -> MemoryResponse:
    """Store one typed memory item."""

    try:
        memory = await memory_service.remember(
            scope=request.scope,
            kind=request.kind,
            content=request.content,
            source=request.source,
            confidence=request.confidence,
            metadata=request.metadata,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (
        MemoryRepositoryConfigurationError,
        MemoryRepositoryUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _memory_response(memory)


@router.get(
    "/memory",
    response_model=MemoryListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        UNPROCESSABLE_CONTENT: {"description": "Invalid filters."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Memory repository unavailable.",
        },
    },
)
async def list_memories(
    memory_service: RuntimeMemoryService,
    _: ReadMemoryAccess,
    scope: MemoryScope | None = None,
    kind: MemoryKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MemoryListResponse:
    """List active memory items."""

    try:
        memories = await memory_service.list_active(
            scope=scope,
            kind=kind,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (
        MemoryRepositoryConfigurationError,
        MemoryRepositoryUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return MemoryListResponse(
        memories=[_memory_response(memory) for memory in memories]
    )


@router.delete(
    "/memory/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Memory repository unavailable.",
        },
    },
)
async def delete_memory(
    memory_id: UUID,
    memory_service: RuntimeMemoryService,
) -> Response:
    """Soft-delete one memory item."""

    try:
        await memory_service.forget(memory_id)
    except (
        MemoryRepositoryConfigurationError,
        MemoryRepositoryUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _memory_response(memory: MemoryItem) -> MemoryResponse:
    """Convert a domain memory item into the public API schema."""

    return MemoryResponse(
        id=memory.id,
        scope=memory.scope,
        kind=memory.kind,
        content=memory.content,
        source=memory.source,
        confidence=memory.confidence,
        metadata=dict(memory.metadata),
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        expires_at=memory.expires_at,
    )
