"""PostgreSQL memory repository adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.memory import (
    MemoryRepositoryConfigurationError,
    MemoryRepositoryUnavailableError,
)

LOGGER = logging.getLogger(__name__)


class _MemoryCursor(Protocol):
    """Small async cursor surface used by the repository."""

    async def execute(self, sql: str, params: tuple[object, ...]) -> object:
        """Execute one SQL statement."""

    async def fetchone(self) -> tuple[object, ...] | None:
        """Fetch one row from the previous statement."""

    async def fetchall(self) -> Sequence[tuple[object, ...]]:
        """Fetch all rows from the previous statement."""


class PostgresMemoryRepository:
    """Memory repository backed by PostgreSQL."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the repository with runtime settings."""

        self._settings = settings or get_settings()

    async def add(self, memory: MemoryItem) -> MemoryItem:
        """Store one memory item and return the database version."""

        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise MemoryRepositoryConfigurationError(msg)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_MemoryCursor, cursor)
                    return await _insert_memory(typed_cursor, memory)
        except Exception as exc:
            LOGGER.warning("Failed to store memory item: %s", exc)
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL memory repository is unavailable"
            ) from exc

    async def list_active(
        self,
        *,
        scope: MemoryScope | None = None,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> tuple[MemoryItem, ...]:
        """List active memory items, optionally filtered by scope and kind."""

        if limit <= 0:
            msg = "Memory list limit must be positive"
            raise ValueError(msg)
        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise MemoryRepositoryConfigurationError(msg)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_MemoryCursor, cursor)
                    return await _list_active_memory(
                        typed_cursor,
                        scope=scope,
                        kind=kind,
                        limit=limit,
                    )
        except Exception as exc:
            LOGGER.warning("Failed to list memory items: %s", exc)
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL memory repository is unavailable"
            ) from exc

    async def delete(self, memory_id: UUID) -> None:
        """Soft-delete one memory item."""

        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise MemoryRepositoryConfigurationError(msg)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    typed_cursor = cast(_MemoryCursor, cursor)
                    await _soft_delete_memory(typed_cursor, memory_id)
        except Exception as exc:
            LOGGER.warning("Failed to delete memory item: %s", exc)
            raise MemoryRepositoryUnavailableError(
                "PostgreSQL memory repository is unavailable"
            ) from exc


async def _insert_memory(cursor: _MemoryCursor, memory: MemoryItem) -> MemoryItem:
    """Insert a memory item and return the stored row."""

    await cursor.execute(
        """
        insert into memory_items (
            scope,
            kind,
            content,
            source,
            confidence,
            metadata,
            expires_at
        )
        values (%s, %s, %s, %s, %s, %s::jsonb, %s)
        returning
            id,
            scope,
            kind,
            content,
            source,
            confidence,
            metadata,
            created_at,
            updated_at,
            expires_at,
            deleted_at
        """,
        (
            memory.scope.value,
            memory.kind.value,
            memory.content,
            memory.source,
            memory.confidence,
            json.dumps(dict(memory.metadata), ensure_ascii=False),
            memory.expires_at,
        ),
    )
    row = await cursor.fetchone()
    if row is None:
        msg = "PostgreSQL did not return a stored memory item"
        raise MemoryRepositoryUnavailableError(msg)
    return _read_memory_item(row)


async def _list_active_memory(
    cursor: _MemoryCursor,
    *,
    scope: MemoryScope | None,
    kind: MemoryKind | None,
    limit: int,
) -> tuple[MemoryItem, ...]:
    """List active memory items from PostgreSQL."""

    scope_filter = scope.value if scope is not None else None
    kind_filter = kind.value if kind is not None else None
    await cursor.execute(
        """
        select
            id,
            scope,
            kind,
            content,
            source,
            confidence,
            metadata,
            created_at,
            updated_at,
            expires_at,
            deleted_at
        from memory_items
        where deleted_at is null
          and (expires_at is null or expires_at > now())
          and (%s::text is null or scope = %s)
          and (%s::text is null or kind = %s)
        order by updated_at desc, created_at desc
        limit %s
        """,
        (
            scope_filter,
            scope_filter,
            kind_filter,
            kind_filter,
            limit,
        ),
    )
    rows = await cursor.fetchall()
    return tuple(_read_memory_item(row) for row in rows)


async def _soft_delete_memory(cursor: _MemoryCursor, memory_id: UUID) -> None:
    """Mark one memory item as deleted."""

    await cursor.execute(
        """
        update memory_items
        set
            deleted_at = now(),
            updated_at = now()
        where id = %s
          and deleted_at is null
        """,
        (memory_id,),
    )


def _read_memory_item(row: tuple[object, ...]) -> MemoryItem:
    """Read one memory row from PostgreSQL."""

    metadata = row[6]
    if not isinstance(metadata, dict):
        metadata = {}

    return MemoryItem(
        id=_read_uuid(row[0]),
        scope=MemoryScope(str(row[1])),
        kind=MemoryKind(str(row[2])),
        content=str(row[3]),
        source=str(row[4]),
        confidence=_read_float(row[5]),
        metadata={str(key): str(value) for key, value in metadata.items()},
        created_at=_read_optional_datetime(row[7]),
        updated_at=_read_optional_datetime(row[8]),
        expires_at=_read_optional_datetime(row[9]),
        deleted_at=_read_optional_datetime(row[10]),
    )


def _read_uuid(value: object) -> UUID:
    """Read a UUID from a PostgreSQL value."""

    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _read_float(value: object) -> float:
    """Read a float from a PostgreSQL value."""

    if isinstance(value, bool):
        return float(str(value))
    if isinstance(value, int | float):
        return float(value)
    return float(str(value))


def _read_optional_datetime(value: object) -> datetime | None:
    """Read an optional datetime from a PostgreSQL value."""

    if value is None or isinstance(value, datetime):
        return value
    msg = "PostgreSQL returned an invalid memory timestamp"
    raise MemoryRepositoryUnavailableError(msg)
