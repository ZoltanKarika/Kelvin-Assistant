"""Domain models for Kelvin memory."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID


class MemoryError(ValueError):
    """Raised when a memory item violates domain rules."""


class MemoryScope(StrEnum):
    """Where a memory item applies."""

    USER = "user"
    PROJECT = "project"
    SESSION = "session"
    SYSTEM = "system"


class MemoryKind(StrEnum):
    """What kind of memory item is stored."""

    PREFERENCE = "preference"
    FACT = "fact"
    SUMMARY = "summary"
    TASK_STATE = "task_state"


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """A typed, deletable memory item."""

    scope: MemoryScope
    kind: MemoryKind
    content: str
    source: str
    confidence: float = 1.0
    metadata: Mapping[str, str] = field(default_factory=dict)
    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        """Normalize and validate a memory item."""

        content = self.content.strip()
        source = self.source.strip()

        if not content:
            raise MemoryError("Memory content cannot be empty")
        if not source:
            raise MemoryError("Memory source cannot be empty")
        if self.confidence < 0 or self.confidence > 1:
            raise MemoryError("Memory confidence must be between 0 and 1")
        if self.expires_at is not None and self.deleted_at is not None:
            if self.deleted_at < self.created_at_or_min():
                raise MemoryError("Memory deletion time cannot be before creation")

        object.__setattr__(self, "content", content)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def is_deleted(self) -> bool:
        """Return whether the memory item is soft-deleted."""

        return self.deleted_at is not None

    @property
    def is_expired(self) -> bool:
        """Return whether the memory item has expired."""

        return self.expires_at is not None and self.expires_at <= datetime.now(UTC)

    @property
    def is_active(self) -> bool:
        """Return whether the memory item can be used as context."""

        return not self.is_deleted and not self.is_expired

    def created_at_or_min(self) -> datetime:
        """Return creation time or the earliest representable UTC datetime."""

        return self.created_at or datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class MemoryEmbedding:
    """Embedding vector for one memory item."""

    memory_id: UUID
    embedding_model: str
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        """Normalize and validate a memory embedding."""

        embedding_model = self.embedding_model.strip()
        if not embedding_model:
            raise MemoryError("Embedding model cannot be empty")
        if not self.embedding:
            raise MemoryError("Embedding cannot be empty")

        object.__setattr__(self, "embedding_model", embedding_model)
