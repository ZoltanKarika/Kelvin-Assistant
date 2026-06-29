"""Versioned chat API routes."""

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from kelvin_assistant.api.dependencies import (
    get_chat_service,
    get_runtime_settings,
)
from kelvin_assistant.api.schemas import ChatRequest, ChatResponse
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import InvalidChatMessageError
from kelvin_assistant.ports.llm import LLMResponseError, LLMUnavailableError
from kelvin_assistant.ports.sessions import (
    SessionConflictError,
    SessionNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
RuntimeChatService = Annotated[ChatService, Depends(get_chat_service)]


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Session not found."},
        status.HTTP_409_CONFLICT: {"description": "Session changed concurrently."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Invalid model response."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Language model runtime unavailable.",
        },
    },
)
async def create_chat_turn(
    request: ChatRequest,
    settings: RuntimeSettings,
    chat_service: RuntimeChatService,
) -> ChatResponse:
    """Create one complete non-streaming conversation turn."""

    try:
        result = await chat_service.send_message(
            message=request.message,
            session_id=request.session_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SessionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (LLMResponseError, InvalidChatMessageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ChatResponse(
        session_id=result.session_id,
        message=result.message,
        model=settings.ollama_model,
    )


@router.post(
    "/chat/stream",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "content": {"text/event-stream": {}},
            "description": "Server-sent events with streamed assistant text.",
        },
        status.HTTP_404_NOT_FOUND: {"description": "Session not found."},
        422: {"description": "Invalid request."},
    },
)
async def stream_chat_turn(
    request: ChatRequest,
    settings: RuntimeSettings,
    chat_service: RuntimeChatService,
) -> StreamingResponse:
    """Stream one conversation turn as server-sent events."""

    try:
        result = await chat_service.stream_message(
            message=request.message,
            session_id=request.session_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StreamingResponse(
        _stream_chat_events(result.session_id, result.chunks, settings.ollama_model),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event: str, data: dict[str, object]) -> str:
    """Format a JSON server-sent event."""

    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _stream_chat_events(
    session_id: UUID,
    chunks: AsyncIterator[str],
    model: str,
) -> AsyncIterator[str]:
    """Convert streamed model chunks into the public SSE contract."""

    yield _sse_event(
        "session",
        {
            "session_id": str(session_id),
            "model": model,
        },
    )
    try:
        async for chunk in chunks:
            yield _sse_event("token", {"text": chunk})
    except (SessionConflictError, LLMUnavailableError) as exc:
        yield _sse_event("error", {"detail": str(exc), "retryable": True})
    except (LLMResponseError, InvalidChatMessageError) as exc:
        yield _sse_event("error", {"detail": str(exc), "retryable": False})
    else:
        yield _sse_event("done", {})
