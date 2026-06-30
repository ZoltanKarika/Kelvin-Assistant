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


class RecentMemoryContextProvider:
    """Build chat context from recent active user memories."""

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        limit: int = 5,
    ) -> None:
        """Initialize the provider with a memory service and item limit."""

        if limit <= 0:
            msg = "memory context limit must be positive"
            raise ValueError(msg)
        self._memory_service = memory_service
        self._limit = limit

    async def get_context(self, query: str) -> str | None:
        """Return recent active user memories for a chat turn."""

        _ = query
        memories = await self._memory_service.list_active(
            scope=MemoryScope.USER,
            limit=self._limit,
        )
        if not memories:
            return None
        return "\n".join(
            _format_memory(index, memory) for index, memory in enumerate(memories, 1)
        )


def _format_memory(index: int, memory: MemoryItem) -> str:
    """Format one memory item for model context."""

    return (
        f"[{index}] scope={memory.scope.value}; "
        f"kind={memory.kind.value}; "
        f"confidence={memory.confidence:.2f}\n"
        f"{memory.content}"
    )
