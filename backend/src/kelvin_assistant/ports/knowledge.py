"""Ports for knowledge persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepositoryError(RuntimeError):
    """Base error raised by knowledge repositories."""


class KnowledgeRepositoryConfigurationError(KnowledgeRepositoryError):
    """Raised when repository settings are incomplete."""


class KnowledgeRepositoryUnavailableError(KnowledgeRepositoryError):
    """Raised when the knowledge repository cannot be reached."""


@dataclass(frozen=True, slots=True)
class StoredKnowledgeDocument:
    """Result returned after storing a document and its chunks."""

    collection_id: UUID
    document_id: UUID
    chunk_count: int
    content_hash: str


class KnowledgeRepository(Protocol):
    """Interface for storing knowledge documents."""

    async def save_document(
        self,
        collection_name: str,
        document: KnowledgeDocument,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> StoredKnowledgeDocument:
        """Store a knowledge document and its deterministic chunks."""
