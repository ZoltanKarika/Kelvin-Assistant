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
    KnowledgeRepositoryConfigurationError,
    KnowledgeRepositoryUnavailableError,
    StoredKnowledgeDocument,
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


def _read_uuid(row: tuple[object, ...] | None, entity_name: str) -> UUID:
    """Read a UUID from a single-row database response."""

    if not row or row[0] is None:
        msg = f"PostgreSQL did not return a {entity_name} ID"
        raise KnowledgeRepositoryUnavailableError(msg)
    value = row[0]
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
