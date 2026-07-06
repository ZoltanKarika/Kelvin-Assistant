"""Port interface for writing security decisions to the audit log."""

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class SecurityAuditLogger(Protocol):
    """Port for logging InputGuard and OutputGuard decisions."""

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
