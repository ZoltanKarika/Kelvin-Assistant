"""Unit tests for the memory application service."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.memory import MemorySearchResult

MEMORY_ID = UUID("462df5a5-a765-4159-9a6c-ca68bd832eaa")


def test_remember_creates_and_persists_memory_item() -> None:
    """The service builds a domain memory item before persistence."""

    async def scenario() -> None:
        repository = FakeMemoryRepository(
            stored_memory=_stored_memory(
                id=MEMORY_ID,
                content="The user prefers step-by-step explanations.",
            )
        )
        service = MemoryService(repository)
        expires_at = datetime.now(UTC) + timedelta(days=30)

        result = await service.remember(
            scope=MemoryScope.USER,
            kind=MemoryKind.PREFERENCE,
            content="  The user prefers step-by-step explanations.  ",
            source=" chat ",
            confidence=0.9,
            metadata={"topic": "communication"},
            expires_at=expires_at,
        )

        assert result.id == MEMORY_ID
        assert len(repository.added) == 1
        added = repository.added[0]
        assert added.scope is MemoryScope.USER
        assert added.kind is MemoryKind.PREFERENCE
        assert added.content == "The user prefers step-by-step explanations."
        assert added.source == "chat"
        assert added.confidence == 0.9
        assert added.metadata == {"topic": "communication"}
        assert added.expires_at == expires_at

    asyncio.run(scenario())


def test_remember_rejects_invalid_memory_before_persistence() -> None:
    """Invalid memory content never reaches the repository."""

    async def scenario() -> None:
        repository = FakeMemoryRepository()
        service = MemoryService(repository)

        with pytest.raises(ValueError, match="content"):
            await service.remember(
                scope=MemoryScope.USER,
                kind=MemoryKind.PREFERENCE,
                content=" ",
                source="chat",
            )

        assert repository.added == []

    asyncio.run(scenario())


def test_list_active_delegates_filters_to_repository() -> None:
    """The service keeps filtering policy visible to callers."""

    async def scenario() -> None:
        stored = (
            _stored_memory(
                id=MEMORY_ID,
                content="The user prefers step-by-step explanations.",
            ),
        )
        repository = FakeMemoryRepository(active_memories=stored)
        service = MemoryService(repository)

        result = await service.list_active(
            scope=MemoryScope.USER,
            kind=MemoryKind.PREFERENCE,
            limit=10,
        )

        assert result == stored
        assert repository.list_calls == [
            {
                "scope": MemoryScope.USER,
                "kind": MemoryKind.PREFERENCE,
                "limit": 10,
            }
        ]

    asyncio.run(scenario())


def test_forget_delegates_soft_delete_to_repository() -> None:
    """The service forgets memories through the repository boundary."""

    async def scenario() -> None:
        repository = FakeMemoryRepository()
        service = MemoryService(repository)

        await service.forget(MEMORY_ID)

        assert repository.deleted == [MEMORY_ID]

    asyncio.run(scenario())


def _stored_memory(
    *,
    id: UUID,
    content: str,
) -> MemoryItem:
    return MemoryItem(
        id=id,
        scope=MemoryScope.USER,
        kind=MemoryKind.PREFERENCE,
        content=content,
        source="chat",
        confidence=0.9,
        metadata={"topic": "communication"},
        created_at=datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
    )


class FakeMemoryRepository:
    """In-memory fake repository for service tests."""

    def __init__(
        self,
        *,
        stored_memory: MemoryItem | None = None,
        active_memories: tuple[MemoryItem, ...] = (),
    ) -> None:
        self._stored_memory = stored_memory
        self._active_memories = active_memories
        self.added: list[MemoryItem] = []
        self.deleted: list[UUID] = []
        self.list_calls: list[dict[str, object]] = []

    async def add(self, memory: MemoryItem) -> MemoryItem:
        self.added.append(memory)
        return self._stored_memory or memory

    async def list_active(
        self,
        *,
        scope: MemoryScope | None = None,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> tuple[MemoryItem, ...]:
        self.list_calls.append(
            {
                "scope": scope,
                "kind": kind,
                "limit": limit,
            }
        )
        return self._active_memories

    async def delete(self, memory_id: UUID) -> None:
        self.deleted.append(memory_id)

    async def search(
        self,
        query_embedding: tuple[float, ...],
        *,
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        _ = (query_embedding, embedding_model, limit)
        return ()
