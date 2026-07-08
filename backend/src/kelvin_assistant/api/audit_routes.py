"""Versioned API routes for querying security audit logs."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from kelvin_assistant.api.dependencies import (
    get_security_audit_logger,
    require_scope,
)
from kelvin_assistant.api.schemas import SecurityAuditEntryResponse
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope
from kelvin_assistant.ports.security_audit import SecurityAuditLogger

router = APIRouter(prefix="/api/v1/security", tags=["security"])

RuntimeSecurityAuditLogger = Annotated[
    SecurityAuditLogger, Depends(get_security_audit_logger)
]


@router.get(
    "/audit",
    response_model=Sequence[SecurityAuditEntryResponse],
    status_code=status.HTTP_200_OK,
)
async def list_security_audit_logs(
    audit_logger: RuntimeSecurityAuditLogger,
    _principal: Annotated[ApiPrincipal, Depends(require_scope(ApiScope.SYSTEM_READ))],
    event_type: Annotated[
        str | None, Query(pattern="^(input_guard|output_guard)$")
    ] = None,
    decision: Annotated[str | None, Query(pattern="^(allow|block)$")] = None,
    run_id: Annotated[UUID | None, Query()] = None,
    correlation_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[SecurityAuditEntryResponse]:
    """Query and filter security decision audit logs (input_guard, output_guard)."""

    entries = await audit_logger.list_entries(
        event_type=event_type,
        decision=decision,
        run_id=run_id,
        correlation_id=correlation_id,
        limit=limit,
        offset=offset,
    )

    return [
        SecurityAuditEntryResponse(
            id=entry.id,
            correlation_id=entry.correlation_id,
            run_id=entry.run_id,
            event_type=entry.event_type,
            decision=entry.decision,
            masked_content=entry.masked_content,
            warnings=entry.warnings,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
