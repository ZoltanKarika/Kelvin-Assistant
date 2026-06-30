"""Application service for Kelvin memory operations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.memory import MemoryRepository


class MemoryService:
    """Coordinate memory validation and persistence."""

    def __init__(self, repository: MemoryRepository) -> None:
        """Initialize the service with a memory repository."""

        self._repository = repository

    async def remember(
        self,
        *,
        scope: MemoryScope,
        kind: MemoryKind,
        content: str,
        source: str,
        confidence: float = 1.0,
        metadata: Mapping[str, str] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryItem:
        """Store one typed memory item."""

        memory = MemoryItem(
            scope=scope,
            kind=kind,
            content=content,
            source=source,
            confidence=confidence,
            metadata=metadata or {},
            expires_at=expires_at,
        )
        return await self._repository.add(memory)

    async def list_active(
        self,
        *,
        scope: MemoryScope | None = None,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> tuple[MemoryItem, ...]:
        """List active memory items, optionally filtered by scope and kind."""

        return await self._repository.list_active(
            scope=scope,
            kind=kind,
            limit=limit,
        )

    async def forget(self, memory_id: UUID) -> None:
        """Soft-delete one memory item."""

        await self._repository.delete(memory_id)
