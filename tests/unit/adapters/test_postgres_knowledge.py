"""Unit tests for the PostgreSQL knowledge repository."""

import asyncio
import builtins
from collections.abc import Sequence
from types import ModuleType, SimpleNamespace
from uuid import UUID

import pytest

from kelvin_assistant.adapters.postgres_knowledge import PostgresKnowledgeRepository
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from kelvin_assistant.ports.knowledge import (
    ChunkEmbedding,
    KnowledgeRepositoryConfigurationError,
    KnowledgeRepositoryUnavailableError,
)

COLLECTION_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_save_document_requires_database_url() -> None:
    """The repository rejects missing database configuration explicitly."""

    repository = PostgresKnowledgeRepository(Settings(environment="test"))

    with pytest.raises(KnowledgeRepositoryConfigurationError, match="Database URL"):
        asyncio.run(
            repository.save_document(
                "manual",
                _document(),
                (_chunk(),),
            )
        )


def test_save_document_rejects_empty_collection_name() -> None:
    """Collection names must be explicit."""

    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
        )
    )

    with pytest.raises(ValueError, match="Collection name"):
        asyncio.run(repository.save_document(" ", _document(), (_chunk(),)))


def test_save_document_rejects_empty_chunks() -> None:
    """Documents must have at least one chunk before storage."""

    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
        )
    )

    with pytest.raises(ValueError, match="At least one chunk"):
        asyncio.run(repository.save_document("manual", _document(), ()))


def test_save_document_reports_missing_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing psycopg is reported as repository unavailability."""

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if name == "psycopg":
            raise ModuleNotFoundError("No module named 'psycopg'")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
        )
    )

    with pytest.raises(KnowledgeRepositoryUnavailableError, match="driver"):
        asyncio.run(repository.save_document("manual", _document(), (_chunk(),)))


def test_save_document_upserts_document_and_replaces_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository writes collection, document, and chunks in one transaction."""

    cursor = FakeCursor(rows=[(COLLECTION_ID,), (DOCUMENT_ID,)])
    connection = FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(
        AsyncConnection=SimpleNamespace(
            connect=AsyncConnect(connection),
        )
    )

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
            database_connect_timeout=2,
        )
    )

    result = asyncio.run(
        repository.save_document(
            "manual",
            _document(),
            (_chunk(),),
        )
    )

    assert result.collection_id == COLLECTION_ID
    assert result.document_id == DOCUMENT_ID
    assert result.chunk_count == 1
    assert len(result.content_hash) == 64
    assert fake_psycopg.AsyncConnection.connect.calls == [
        {
            "database_url": "postgresql://kelvin:secret@127.0.0.1/db",
            "connect_timeout": 2,
        }
    ]
    assert len(cursor.executed) == 3
    assert "insert into knowledge_collections" in cursor.executed[0].sql
    assert "insert into knowledge_documents" in cursor.executed[1].sql
    assert "delete from knowledge_chunks" in cursor.executed[2].sql
    assert len(cursor.executed_many) == 1
    assert "insert into knowledge_chunks" in cursor.executed_many[0].sql
    assert cursor.executed_many[0].params[0][1:] == (
        0,
        "Kelvin API production portja 8000.",
        '{"topic": "api"}',
    )


def test_save_embeddings_requires_database_url() -> None:
    """The repository rejects missing database configuration for embeddings."""

    repository = PostgresKnowledgeRepository(Settings(environment="test"))

    with pytest.raises(KnowledgeRepositoryConfigurationError, match="Database URL"):
        asyncio.run(
            repository.save_embeddings(
                "manual",
                "manual://kelvin-notes",
                "nomic-embed-text",
                (_embedding(),),
            )
        )


def test_save_embeddings_rejects_invalid_values() -> None:
    """Embedding storage validates its input before touching PostgreSQL."""

    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
        )
    )

    with pytest.raises(ValueError, match="Embedding dimensions"):
        asyncio.run(
            repository.save_embeddings(
                "manual",
                "manual://kelvin-notes",
                "nomic-embed-text",
                (
                    ChunkEmbedding(chunk_index=0, embedding=(0.1, 0.2)),
                    ChunkEmbedding(chunk_index=1, embedding=(0.1,)),
                ),
            )
        )


def test_save_embeddings_upserts_chunk_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository stores embeddings against existing chunk indexes."""

    cursor = FakeCursor(rows=[])
    connection = FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(
        AsyncConnection=SimpleNamespace(
            connect=AsyncConnect(connection),
        )
    )

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
            database_connect_timeout=2,
        )
    )

    result = asyncio.run(
        repository.save_embeddings(
            " manual ",
            " manual://kelvin-notes ",
            " nomic-embed-text ",
            (
                ChunkEmbedding(chunk_index=0, embedding=(0.1, 0.2, 0.3)),
                ChunkEmbedding(chunk_index=1, embedding=(0.4, 0.5, 0.6)),
            ),
        )
    )

    assert result.source_uri == "manual://kelvin-notes"
    assert result.embedding_model == "nomic-embed-text"
    assert result.embedding_count == 2
    assert result.embedding_dimension == 3
    assert fake_psycopg.AsyncConnection.connect.calls == [
        {
            "database_url": "postgresql://kelvin:secret@127.0.0.1/db",
            "connect_timeout": 2,
        }
    ]
    assert len(cursor.executed_many) == 1
    assert "insert into knowledge_embeddings" in cursor.executed_many[0].sql
    assert "from knowledge_chunks" in cursor.executed_many[0].sql
    assert cursor.executed_many[0].params == [
        (
            "nomic-embed-text",
            3,
            "[0.1,0.2,0.3]",
            "manual",
            "manual://kelvin-notes",
            0,
        ),
        (
            "nomic-embed-text",
            3,
            "[0.4,0.5,0.6]",
            "manual",
            "manual://kelvin-notes",
            1,
        ),
    ]


def test_search_similar_chunks_requires_database_url() -> None:
    """The repository rejects missing database configuration for search."""

    repository = PostgresKnowledgeRepository(Settings(environment="test"))

    with pytest.raises(KnowledgeRepositoryConfigurationError, match="Database URL"):
        asyncio.run(
            repository.search_similar_chunks(
                "manual",
                "nomic-embed-text",
                (0.1, 0.2, 0.3),
                limit=3,
            )
        )


def test_search_similar_chunks_rejects_invalid_values() -> None:
    """Semantic search validates collection, model, vector, and limit."""

    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
        )
    )

    with pytest.raises(ValueError, match="Search limit"):
        asyncio.run(
            repository.search_similar_chunks(
                "manual",
                "nomic-embed-text",
                (0.1, 0.2, 0.3),
                limit=0,
            )
        )


def test_search_similar_chunks_returns_ordered_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository searches pgvector embeddings with cosine distance."""

    cursor = FakeCursor(
        rows=[],
        all_rows=[
            (
                "manual://kelvin-notes",
                "Kelvin Notes",
                1,
                "PostgreSQL es pgvector lokalisan fut.",
                {"heading": "Database"},
                0.08,
            ),
            (
                "manual://kelvin-notes",
                "Kelvin Notes",
                0,
                "Kelvin API production portja 8000.",
                {"heading": "API"},
                0.62,
            ),
        ],
    )
    connection = FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(
        AsyncConnection=SimpleNamespace(
            connect=AsyncConnect(connection),
        )
    )

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            return fake_psycopg
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    repository = PostgresKnowledgeRepository(
        Settings(
            environment="test",
            database_url="postgresql://kelvin:secret@127.0.0.1/db",
            database_connect_timeout=2,
        )
    )

    results = asyncio.run(
        repository.search_similar_chunks(
            " manual ",
            " nomic-embed-text ",
            (0.1, 0.2, 0.3),
            limit=2,
        )
    )

    assert fake_psycopg.AsyncConnection.connect.calls == [
        {
            "database_url": "postgresql://kelvin:secret@127.0.0.1/db",
            "connect_timeout": 2,
        }
    ]
    assert len(cursor.executed) == 1
    assert "e.embedding <=>" in cursor.executed[0].sql
    assert "order by e.embedding <=>" in cursor.executed[0].sql
    assert cursor.executed[0].params == (
        "[0.1,0.2,0.3]",
        "manual",
        "nomic-embed-text",
        "[0.1,0.2,0.3]",
        2,
    )
    assert [result.chunk_index for result in results] == [1, 0]
    assert results[0].content == "PostgreSQL es pgvector lokalisan fut."
    assert results[0].metadata == {"heading": "Database"}
    assert results[0].distance == 0.08


def _document() -> KnowledgeDocument:
    return KnowledgeDocument(
        source_uri="manual://kelvin-notes",
        content="Kelvin API production portja 8000.",
        mime_type="text/plain",
        title="Kelvin Notes",
        metadata={"filename": "notes.txt"},
    )


def _chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        source_uri="manual://kelvin-notes",
        chunk_index=0,
        content="Kelvin API production portja 8000.",
        metadata={"topic": "api"},
    )


def _embedding() -> ChunkEmbedding:
    return ChunkEmbedding(chunk_index=0, embedding=(0.1, 0.2, 0.3))


class AsyncConnect:
    """Fake async psycopg connection factory."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self.calls: list[dict[str, object]] = []

    async def __call__(
        self,
        database_url: str,
        *,
        connect_timeout: int,
    ) -> "FakeConnection":
        self.calls.append(
            {
                "database_url": database_url,
                "connect_timeout": connect_timeout,
            }
        )
        return self._connection


class FakeConnection:
    """Fake async database connection."""

    def __init__(self, cursor: "FakeCursor") -> None:
        self._cursor = cursor

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return self._cursor


class FakeCursor:
    """Fake async cursor recording SQL calls."""

    def __init__(
        self,
        rows: list[tuple[UUID]],
        all_rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._rows = rows
        self._all_rows = all_rows or []
        self.executed: list[SqlCall] = []
        self.executed_many: list[SqlManyCall] = []

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    async def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append(SqlCall(sql=" ".join(sql.split()), params=params))

    async def executemany(
        self,
        sql: str,
        params_seq: list[tuple[object, ...]],
    ) -> None:
        self.executed_many.append(
            SqlManyCall(sql=" ".join(sql.split()), params=params_seq)
        )

    async def fetchone(self) -> tuple[UUID]:
        return self._rows.pop(0)

    async def fetchall(self) -> list[tuple[object, ...]]:
        return self._all_rows


class SqlCall(SimpleNamespace):
    sql: str
    params: tuple[object, ...]


class SqlManyCall(SimpleNamespace):
    sql: str
    params: list[tuple[object, ...]]
