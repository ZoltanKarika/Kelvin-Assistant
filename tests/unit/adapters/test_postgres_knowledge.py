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

    def __init__(self, rows: list[tuple[UUID]]) -> None:
        self._rows = rows
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


class SqlCall(SimpleNamespace):
    sql: str
    params: tuple[object, ...]


class SqlManyCall(SimpleNamespace):
    sql: str
    params: list[tuple[object, ...]]
