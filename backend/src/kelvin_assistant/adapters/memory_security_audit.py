"""In-memory security audit log adapter for testing."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from kelvin_assistant.ports.security_audit import (
    SecurityAuditEntry,
    SecurityAuditLogger,
)


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
        results: list[SecurityAuditEntry] = self.entries
        if event_type is not None:
            results = [r for r in results if r.event_type == event_type]
        if decision is not None:
            results = [r for r in results if r.decision == decision]
        if run_id is not None:
            results = [r for r in results if r.run_id == run_id]
        if correlation_id is not None:
            results = [r for r in results if r.correlation_id == correlation_id]
        # Sort by creation time descending by default
        sorted_results = sorted(results, key=lambda r: r.created_at, reverse=True)
        return sorted_results[offset : offset + limit]
