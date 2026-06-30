"""Unit tests for the PostgreSQL memory repository."""

import asyncio
import builtins
from collections.abc import Sequence
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace
from uuid import UUID

import pytest

from kelvin_assistant.adapters.postgres_memory import PostgresMemoryRepository
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.memory import (
    MemoryRepositoryConfigurationError,
    MemoryRepositoryUnavailableError,
)

MEMORY_ID = UUID("462df5a5-a765-4159-9a6c-ca68bd832eaa")
CREATED_AT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def test_add_requires_database_url() -> None:
    """The repository rejects missing database configuration explicitly."""

    repository = PostgresMemoryRepository(Settings(environment="test"))

    with pytest.raises(MemoryRepositoryConfigurationError, match="Database URL"):
        asyncio.run(repository.add(_memory()))


def test_add_reports_missing_driver(monkeypatch: pytest.MonkeyPatch) -> None:
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
    repository = PostgresMemoryRepository(_settings())

    with pytest.raises(MemoryRepositoryUnavailableError, match="driver"):
        asyncio.run(repository.add(_memory()))


def test_add_inserts_memory_and_returns_stored_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository stores a memory item and returns the database row."""

    cursor = FakeCursor(rows=[_memory_row()])
    fake_psycopg = _install_fake_psycopg(monkeypatch, cursor)
    repository = PostgresMemoryRepository(_settings())

    result = asyncio.run(repository.add(_memory()))

    assert result.id == MEMORY_ID
    assert result.scope is MemoryScope.USER
    assert result.kind is MemoryKind.PREFERENCE
    assert result.content == "The user prefers step-by-step explanations."
    assert result.metadata == {"topic": "communication"}
    assert result.created_at == CREATED_AT
    assert fake_psycopg.AsyncConnection.connect.calls == [
        {
            "database_url": "postgresql://kelvin:secret@127.0.0.1/db",
            "connect_timeout": 2,
        }
    ]
    assert len(cursor.executed) == 1
    assert "insert into memory_items" in cursor.executed[0].sql
    assert cursor.executed[0].params == (
        "user",
        "preference",
        "The user prefers step-by-step explanations.",
        "manual-test",
        0.9,
        '{"topic": "communication"}',
        None,
    )


def test_list_active_requires_positive_limit() -> None:
    """Active memory listing validates its limit before touching PostgreSQL."""

    repository = PostgresMemoryRepository(_settings())

    with pytest.raises(ValueError, match="limit"):
        asyncio.run(repository.list_active(limit=0))


def test_list_active_filters_scope_and_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository lists active memories with optional filters."""

    cursor = FakeCursor(all_rows=[_memory_row()])
    _install_fake_psycopg(monkeypatch, cursor)
    repository = PostgresMemoryRepository(_settings())

    results = asyncio.run(
        repository.list_active(
            scope=MemoryScope.USER,
            kind=MemoryKind.PREFERENCE,
            limit=10,
        )
    )

    assert len(results) == 1
    assert results[0].id == MEMORY_ID
    assert results[0].is_active
    assert len(cursor.executed) == 1
    assert "from memory_items" in cursor.executed[0].sql
    assert "deleted_at is null" in cursor.executed[0].sql
    assert "expires_at is null" in cursor.executed[0].sql
    assert cursor.executed[0].params == (
        "user",
        "user",
        "preference",
        "preference",
        10,
    )


def test_delete_soft_deletes_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """The repository marks a memory item as deleted instead of removing it."""

    cursor = FakeCursor()
    _install_fake_psycopg(monkeypatch, cursor)
    repository = PostgresMemoryRepository(_settings())

    asyncio.run(repository.delete(MEMORY_ID))

    assert len(cursor.executed) == 1
    assert "update memory_items" in cursor.executed[0].sql
    assert "deleted_at = now()" in cursor.executed[0].sql
    assert cursor.executed[0].params == (MEMORY_ID,)


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql://kelvin:secret@127.0.0.1/db",
        database_connect_timeout=2,
    )


def _memory() -> MemoryItem:
    return MemoryItem(
        scope=MemoryScope.USER,
        kind=MemoryKind.PREFERENCE,
        content="The user prefers step-by-step explanations.",
        source="manual-test",
        confidence=0.9,
        metadata={"topic": "communication"},
    )


def _memory_row() -> tuple[object, ...]:
    return (
        MEMORY_ID,
        "user",
        "preference",
        "The user prefers step-by-step explanations.",
        "manual-test",
        0.9,
        {"topic": "communication"},
        CREATED_AT,
        CREATED_AT,
        None,
        None,
    )


def _install_fake_psycopg(
    monkeypatch: pytest.MonkeyPatch,
    cursor: "FakeCursor",
) -> SimpleNamespace:
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
    return fake_psycopg


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
        rows: list[tuple[object, ...]] | None = None,
        all_rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self._rows = rows or []
        self._all_rows = all_rows or []
        self.executed: list[SqlCall] = []

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

    async def fetchone(self) -> tuple[object, ...] | None:
        if not self._rows:
            return None
        return self._rows.pop(0)

    async def fetchall(self) -> list[tuple[object, ...]]:
        return self._all_rows


class SqlCall(SimpleNamespace):
    sql: str
    params: tuple[object, ...]
