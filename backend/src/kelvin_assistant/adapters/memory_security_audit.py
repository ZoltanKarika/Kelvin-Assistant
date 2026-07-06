"""In-memory security audit log adapter for testing."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from kelvin_assistant.ports.security_audit import SecurityAuditLogger


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


class InMemorySecurityAuditLogger(SecurityAuditLogger):
    """In-memory security audit log for testing."""

    def __init__(self) -> None:
        self.entries: list[SecurityAuditEntry] = []

    async def log_decision(
        self,
        *,
        event_type: str,
        decision: str,
        masked_content: str | None,
        warnings: list[str],
        correlation_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> None:
        entry = SecurityAuditEntry(
            id=uuid4(),
            correlation_id=correlation_id,
            run_id=run_id,
            event_type=event_type,
            decision=decision,
            masked_content=masked_content,
            warnings=list(warnings),
            created_at=datetime.now(UTC),
        )
        self.entries.append(entry)
