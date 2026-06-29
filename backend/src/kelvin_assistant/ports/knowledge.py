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


@dataclass(frozen=True, slots=True)
class ChunkEmbedding:
    """Embedding vector for one stored chunk index."""

    chunk_index: int
    embedding: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class StoredKnowledgeEmbeddings:
    """Result returned after storing chunk embeddings."""

    source_uri: str
    embedding_model: str
    embedding_count: int
    embedding_dimension: int


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    """One semantically similar knowledge chunk."""

    source_uri: str
    title: str | None
    chunk_index: int
    content: str
    metadata: dict[str, str]
    distance: float


class KnowledgeRepository(Protocol):
    """Interface for storing knowledge documents."""

    async def save_document(
        self,
        collection_name: str,
        document: KnowledgeDocument,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> StoredKnowledgeDocument:
        """Store a knowledge document and its deterministic chunks."""

    async def save_embeddings(
        self,
        collection_name: str,
        source_uri: str,
        embedding_model: str,
        embeddings: tuple[ChunkEmbedding, ...],
    ) -> StoredKnowledgeEmbeddings:
        """Store embeddings for deterministic chunk indexes."""

    async def search_similar_chunks(
        self,
        collection_name: str,
        embedding_model: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        """Return semantically similar chunks ordered by cosine distance."""


class KnowledgeSearchRepository(Protocol):
    """Interface for semantic knowledge search."""

    async def search_similar_chunks(
        self,
        collection_name: str,
        embedding_model: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        """Return semantically similar chunks ordered by cosine distance."""


class KnowledgeContextProvider(Protocol):
    """Interface for retrieving formatted knowledge context for chat."""

    async def get_context(self, query: str) -> str | None:
        """Return formatted context for a user query, or None when unavailable."""
