"""Port interface for writing and reading security decisions in the audit log."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class SecurityAuditEntry:
    id: UUID
    correlation_id: UUID | None
    run_id: UUID | None
    event_type: str
    decision: str
    masked_content: str | None
    warnings: list[str]
    created_at: datetime


@runtime_checkable
class SecurityAuditLogger(Protocol):
    """Port for logging and querying InputGuard and OutputGuard decisions."""

    async def log_decision(
        self,
        *,
        event_type: str,  # 'input_guard', 'output_guard'
        decision: str,  # 'allow', 'block'
        masked_content: str | None,
        warnings: list[str],
        correlation_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> None:
        """Log one security decision."""
        ...

    async def list_entries(
        self,
        *,
        event_type: str | None = None,
        decision: str | None = None,
        run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[SecurityAuditEntry]:
        """Query and filter stored security audit logs."""
        ...
