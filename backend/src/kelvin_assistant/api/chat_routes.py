"""Versioned chat API routes."""

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from kelvin_assistant.api.dependencies import (
    get_chat_service,
    get_input_guard,
    get_runtime_settings,
    get_security_audit_logger,
    require_scope,
)
from kelvin_assistant.api.schemas import ChatRequest, ChatResponse
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.domain.chat import InvalidChatMessageError
from kelvin_assistant.domain.input_guard import InputGuard
from kelvin_assistant.domain.output_guard import mask_secrets
from kelvin_assistant.ports.llm import LLMResponseError, LLMUnavailableError
from kelvin_assistant.ports.security_audit import SecurityAuditLogger
from kelvin_assistant.ports.sessions import (
    SessionConflictError,
    SessionNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])
RuntimeSettings = Annotated[Settings, Depends(get_runtime_settings)]
RuntimeChatService = Annotated[ChatService, Depends(get_chat_service)]
RuntimeInputGuard = Annotated[InputGuard, Depends(get_input_guard)]
RuntimeSecurityAuditLogger = Annotated[
    SecurityAuditLogger, Depends(get_security_audit_logger)
]


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token."},
        status.HTTP_403_FORBIDDEN: {"description": "Token lacks required scope."},
        status.HTTP_404_NOT_FOUND: {"description": "Session not found."},
        status.HTTP_409_CONFLICT: {"description": "Session changed concurrently."},
        status.HTTP_502_BAD_GATEWAY: {"description": "Invalid model response."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Language model runtime unavailable.",
        },
    },
)
async def create_chat_turn(
    fastapi_request: Request,
    request: ChatRequest,
    settings: RuntimeSettings,
    chat_service: RuntimeChatService,
    input_guard: RuntimeInputGuard,
    audit_logger: RuntimeSecurityAuditLogger,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.CHAT_USE))],
) -> ChatResponse:
    """Create one complete non-streaming conversation turn."""

    validation = input_guard.validate_input(request.message)
    masked_input = mask_secrets(request.message)
    correlation_id = None
    if fastapi_request.state.correlation_id:
        try:
            correlation_id = UUID(fastapi_request.state.correlation_id)
        except ValueError:
            pass

    await audit_logger.log_decision(
        event_type="input_guard",
        decision="allow" if validation.is_safe else "block",
        masked_content=masked_input,
        warnings=validation.warnings,
        correlation_id=correlation_id,
    )

    if not validation.is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blocked due to: {', '.join(validation.warnings)}",
        )

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

    masked_message = mask_secrets(result.message) or ""
    await audit_logger.log_decision(
        event_type="output_guard",
        decision="allow",
        masked_content=masked_message,
        warnings=[],
        correlation_id=correlation_id,
    )

    return ChatResponse(
        session_id=result.session_id,
        message=masked_message,
        model=settings.ollama_model,
        correlation_id=fastapi_request.state.correlation_id,
    )


@router.post(
    "/chat/stream",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "content": {"text/event-stream": {}},
            "description": "Server-sent events with streamed assistant text.",
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token."},
        status.HTTP_403_FORBIDDEN: {"description": "Token lacks required scope."},
        status.HTTP_404_NOT_FOUND: {"description": "Session not found."},
        422: {"description": "Invalid request."},
    },
)
async def stream_chat_turn(
    fastapi_request: Request,
    request: ChatRequest,
    settings: RuntimeSettings,
    chat_service: RuntimeChatService,
    input_guard: RuntimeInputGuard,
    audit_logger: RuntimeSecurityAuditLogger,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.CHAT_USE))],
) -> StreamingResponse:
    """Stream one conversation turn as server-sent events."""

    validation = input_guard.validate_input(request.message)
    masked_input = mask_secrets(request.message)
    correlation_id = None
    if fastapi_request.state.correlation_id:
        try:
            correlation_id = UUID(fastapi_request.state.correlation_id)
        except ValueError:
            pass

    await audit_logger.log_decision(
        event_type="input_guard",
        decision="allow" if validation.is_safe else "block",
        masked_content=masked_input,
        warnings=validation.warnings,
        correlation_id=correlation_id,
    )

    if not validation.is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blocked due to: {', '.join(validation.warnings)}",
        )

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
        _stream_chat_events(
            result.session_id,
            result.chunks,
            settings.ollama_model,
            correlation_id,
            audit_logger,
        ),
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
    correlation_id: UUID | None,
    audit_logger: SecurityAuditLogger,
) -> AsyncIterator[str]:
    """Convert streamed model chunks into the public SSE contract."""

    yield _sse_event(
        "session",
        {
            "session_id": str(session_id),
            "model": model,
            "correlation_id": str(correlation_id) if correlation_id else None,
        },
    )
    full_response_parts = []
    try:
        async for chunk in chunks:
            masked_chunk = mask_secrets(chunk)
            if masked_chunk:
                full_response_parts.append(masked_chunk)
            yield _sse_event("token", {"text": masked_chunk})
    except (SessionConflictError, LLMUnavailableError) as exc:
        yield _sse_event("error", {"detail": str(exc), "retryable": True})
    except (LLMResponseError, InvalidChatMessageError) as exc:
        yield _sse_event("error", {"detail": str(exc), "retryable": False})
    else:
        full_response = "".join(full_response_parts)
        await audit_logger.log_decision(
            event_type="output_guard",
            decision="allow",
            masked_content=full_response,
            warnings=[],
            correlation_id=correlation_id,
        )
        yield _sse_event("done", {})
