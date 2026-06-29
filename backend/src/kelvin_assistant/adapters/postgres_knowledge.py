"""PostgreSQL knowledge repository adapter."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Protocol, cast
from uuid import UUID

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from kelvin_assistant.ports.knowledge import (
    ChunkEmbedding,
    KnowledgeRepositoryConfigurationError,
    KnowledgeRepositoryUnavailableError,
    KnowledgeSearchResult,
    StoredKnowledgeDocument,
    StoredKnowledgeEmbeddings,
)

LOGGER = logging.getLogger(__name__)


class _KnowledgeCursor(Protocol):
    """Small async cursor surface used by the repository."""

    async def execute(self, sql: str, params: tuple[object, ...]) -> object:
        """Execute one SQL statement."""

    async def executemany(
        self,
        sql: str,
        params_seq: Sequence[tuple[object, ...]],
    ) -> object:
        """Execute one SQL statement with multiple parameter sets."""

    async def fetchone(self) -> tuple[object, ...] | None:
        """Fetch one row from the previous statement."""

    async def fetchall(self) -> Sequence[tuple[object, ...]]:
        """Fetch all rows from the previous statement."""


class PostgresKnowledgeRepository:
    """Knowledge repository backed by PostgreSQL."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the repository with runtime settings."""

        self._settings = settings or get_settings()

    async def save_document(
        self,
        collection_name: str,
        document: KnowledgeDocument,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> StoredKnowledgeDocument:
        """Store a document and replace its chunks atomically."""

        normalized_collection_name = collection_name.strip()
        if not normalized_collection_name:
            msg = "Collection name cannot be empty"
            raise ValueError(msg)
        if not chunks:
            msg = "At least one chunk is required"
            raise ValueError(msg)
        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise KnowledgeRepositoryConfigurationError(msg)

        content_hash = _content_hash(document)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_KnowledgeCursor, cursor)
                    collection_id = await _upsert_collection(
                        typed_cursor,
                        normalized_collection_name,
                    )
                    document_id = await _upsert_document(
                        typed_cursor,
                        collection_id,
                        document,
                        content_hash,
                    )
                    await _replace_chunks(typed_cursor, document_id, chunks)
        except Exception as exc:
            LOGGER.warning("Failed to store knowledge document: %s", exc)
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL knowledge repository is unavailable"
            ) from exc

        return StoredKnowledgeDocument(
            collection_id=collection_id,
            document_id=document_id,
            chunk_count=len(chunks),
            content_hash=content_hash,
        )

    async def save_embeddings(
        self,
        collection_name: str,
        source_uri: str,
        embedding_model: str,
        embeddings: tuple[ChunkEmbedding, ...],
    ) -> StoredKnowledgeEmbeddings:
        """Store embeddings for chunk indexes in one document."""

        normalized_collection_name = collection_name.strip()
        normalized_source_uri = source_uri.strip()
        normalized_embedding_model = embedding_model.strip()
        if not normalized_collection_name:
            msg = "Collection name cannot be empty"
            raise ValueError(msg)
        if not normalized_source_uri:
            msg = "Source URI cannot be empty"
            raise ValueError(msg)
        if not normalized_embedding_model:
            msg = "Embedding model cannot be empty"
            raise ValueError(msg)
        if not embeddings:
            msg = "At least one embedding is required"
            raise ValueError(msg)
        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise KnowledgeRepositoryConfigurationError(msg)

        embedding_dimension = _embedding_dimension(embeddings)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_KnowledgeCursor, cursor)
                    await _upsert_embeddings(
                        typed_cursor,
                        normalized_collection_name,
                        normalized_source_uri,
                        normalized_embedding_model,
                        embedding_dimension,
                        embeddings,
                    )
        except Exception as exc:
            LOGGER.warning("Failed to store knowledge embeddings: %s", exc)
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL knowledge repository is unavailable"
            ) from exc

        return StoredKnowledgeEmbeddings(
            source_uri=normalized_source_uri,
            embedding_model=normalized_embedding_model,
            embedding_count=len(embeddings),
            embedding_dimension=embedding_dimension,
        )

    async def search_similar_chunks(
        self,
        collection_name: str,
        embedding_model: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        """Return semantically similar chunks ordered by cosine distance."""

        normalized_collection_name = collection_name.strip()
        normalized_embedding_model = embedding_model.strip()
        if not normalized_collection_name:
            msg = "Collection name cannot be empty"
            raise ValueError(msg)
        if not normalized_embedding_model:
            msg = "Embedding model cannot be empty"
            raise ValueError(msg)
        if not query_embedding:
            msg = "Query embedding cannot be empty"
            raise ValueError(msg)
        if limit <= 0:
            msg = "Search limit must be positive"
            raise ValueError(msg)
        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise KnowledgeRepositoryConfigurationError(msg)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_KnowledgeCursor, cursor)
                    return await _search_similar_chunks(
                        typed_cursor,
                        normalized_collection_name,
                        normalized_embedding_model,
                        query_embedding,
                        limit,
                    )
        except Exception as exc:
            LOGGER.warning("Failed to search knowledge embeddings: %s", exc)
            raise KnowledgeRepositoryUnavailableError(
                "PostgreSQL knowledge repository is unavailable"
            ) from exc


def _content_hash(document: KnowledgeDocument) -> str:
    """Return a stable SHA-256 hash for the document content."""

    return hashlib.sha256(document.content.encode("utf-8")).hexdigest()


async def _upsert_collection(
    cursor: _KnowledgeCursor,
    collection_name: str,
) -> UUID:
    """Insert or update a collection and return its ID."""

    await cursor.execute(
        """
        insert into knowledge_collections (name)
        values (%s)
        on conflict (name)
        do update set updated_at = now()
        returning id
        """,
        (collection_name,),
    )
    row = await cursor.fetchone()
    return _read_uuid(row, "collection")


async def _upsert_document(
    cursor: _KnowledgeCursor,
    collection_id: UUID,
    document: KnowledgeDocument,
    content_hash: str,
) -> UUID:
    """Insert or update a document and return its ID."""

    await cursor.execute(
        """
        insert into knowledge_documents (
            collection_id,
            source_uri,
            title,
            content_hash,
            mime_type,
            metadata
        )
        values (%s, %s, %s, %s, %s, %s::jsonb)
        on conflict (collection_id, source_uri)
        do update set
            title = excluded.title,
            content_hash = excluded.content_hash,
            mime_type = excluded.mime_type,
            metadata = excluded.metadata,
            updated_at = now()
        returning id
        """,
        (
            collection_id,
            document.source_uri,
            document.title,
            content_hash,
            document.mime_type,
            json.dumps(dict(document.metadata), ensure_ascii=False),
        ),
    )
    row = await cursor.fetchone()
    return _read_uuid(row, "document")


async def _replace_chunks(
    cursor: _KnowledgeCursor,
    document_id: UUID,
    chunks: tuple[KnowledgeChunk, ...],
) -> None:
    """Replace all chunks for a document."""

    await cursor.execute(
        "delete from knowledge_chunks where document_id = %s",
        (document_id,),
    )
    await cursor.executemany(
        """
        insert into knowledge_chunks (
            document_id,
            chunk_index,
            content,
            metadata
        )
        values (%s, %s, %s, %s::jsonb)
        """,
        [
            (
                document_id,
                chunk.chunk_index,
                chunk.content,
                json.dumps(dict(chunk.metadata), ensure_ascii=False),
            )
            for chunk in chunks
        ],
    )


async def _upsert_embeddings(
    cursor: _KnowledgeCursor,
    collection_name: str,
    source_uri: str,
    embedding_model: str,
    embedding_dimension: int,
    embeddings: tuple[ChunkEmbedding, ...],
) -> None:
    """Insert or update embeddings for stored chunk indexes."""

    await cursor.executemany(
        """
        insert into knowledge_embeddings (
            chunk_id,
            embedding_model,
            embedding_dimension,
            embedding
        )
        select
            ch.id,
            %s,
            %s,
            %s::vector
        from knowledge_chunks ch
        join knowledge_documents d on d.id = ch.document_id
        join knowledge_collections c on c.id = d.collection_id
        where c.name = %s
          and d.source_uri = %s
          and ch.chunk_index = %s
        on conflict (chunk_id, embedding_model)
        do update set
            embedding_dimension = excluded.embedding_dimension,
            embedding = excluded.embedding,
            created_at = now()
        """,
        [
            (
                embedding_model,
                embedding_dimension,
                _to_pgvector(embedding.embedding),
                collection_name,
                source_uri,
                embedding.chunk_index,
            )
            for embedding in embeddings
        ],
    )


async def _search_similar_chunks(
    cursor: _KnowledgeCursor,
    collection_name: str,
    embedding_model: str,
    query_embedding: tuple[float, ...],
    limit: int,
) -> tuple[KnowledgeSearchResult, ...]:
    """Search stored embeddings by cosine distance."""

    await cursor.execute(
        """
        select
            d.source_uri,
            d.title,
            ch.chunk_index,
            ch.content,
            ch.metadata,
            e.embedding <=> %s::vector as distance
        from knowledge_embeddings e
        join knowledge_chunks ch on ch.id = e.chunk_id
        join knowledge_documents d on d.id = ch.document_id
        join knowledge_collections c on c.id = d.collection_id
        where c.name = %s
          and e.embedding_model = %s
        order by e.embedding <=> %s::vector
        limit %s
        """,
        (
            _to_pgvector(query_embedding),
            collection_name,
            embedding_model,
            _to_pgvector(query_embedding),
            limit,
        ),
    )
    rows = await cursor.fetchall()
    return tuple(_read_search_result(row) for row in rows)


def _read_search_result(row: tuple[object, ...]) -> KnowledgeSearchResult:
    """Read one search result row from PostgreSQL."""

    metadata = row[4]
    if not isinstance(metadata, dict):
        metadata = {}
    chunk_index = row[2]
    distance = row[5]
    if not isinstance(chunk_index, int):
        chunk_index = int(str(chunk_index))
    if isinstance(distance, bool) or not isinstance(distance, int | float):
        distance = float(str(distance))

    return KnowledgeSearchResult(
        source_uri=str(row[0]),
        title=str(row[1]) if row[1] is not None else None,
        chunk_index=chunk_index,
        content=str(row[3]),
        metadata={str(key): str(value) for key, value in metadata.items()},
        distance=float(distance),
    )


def _embedding_dimension(embeddings: tuple[ChunkEmbedding, ...]) -> int:
    """Validate embedding dimensions and return the shared dimension."""

    first_dimension = len(embeddings[0].embedding)
    if first_dimension == 0:
        msg = "Embedding cannot be empty"
        raise ValueError(msg)
    for embedding in embeddings:
        if embedding.chunk_index < 0:
            msg = "Chunk index cannot be negative"
            raise ValueError(msg)
        if len(embedding.embedding) != first_dimension:
            msg = "Embedding dimensions must match"
            raise ValueError(msg)
    return first_dimension


def _to_pgvector(embedding: tuple[float, ...]) -> str:
    """Serialize an embedding tuple into pgvector text format."""

    return "[" + ",".join(str(value) for value in embedding) + "]"


def _read_uuid(row: tuple[object, ...] | None, entity_name: str) -> UUID:
    """Read a UUID from a single-row database response."""

    if not row or row[0] is None:
        msg = f"PostgreSQL did not return a {entity_name} ID"
        raise KnowledgeRepositoryUnavailableError(msg)
    value = row[0]
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
