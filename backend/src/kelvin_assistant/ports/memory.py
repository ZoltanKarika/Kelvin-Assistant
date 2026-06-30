"""Ports for Kelvin memory persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope


class MemoryRepositoryError(RuntimeError):
    """Base error raised by memory repositories."""


class MemoryRepositoryConfigurationError(MemoryRepositoryError):
    """Raised when memory repository settings are incomplete."""


class MemoryRepositoryUnavailableError(MemoryRepositoryError):
    """Raised when the memory repository cannot be reached."""


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """One semantically relevant memory item."""

    memory: MemoryItem
    distance: float


class MemoryRepository(Protocol):
    """Interface for typed, deletable memory storage."""

    async def add(self, memory: MemoryItem) -> MemoryItem:
        """Store one memory item and return the stored version."""

    async def list_active(
        self,
        *,
        scope: MemoryScope | None = None,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> tuple[MemoryItem, ...]:
        """List active memory items, optionally filtered by scope and kind."""

    async def delete(self, memory_id: UUID) -> None:
        """Soft-delete one memory item."""

    async def search(
        self,
        query_embedding: tuple[float, ...],
        *,
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        """Search active memory items by embedding similarity."""


class MemoryContextProvider(Protocol):
    """Interface for building memory context for chat prompts."""

    async def get_context(self, query: str) -> str | None:
        """Return memory context relevant to a user query."""
