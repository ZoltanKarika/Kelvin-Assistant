"""Unit tests for the PostgreSQL database adapter."""

import asyncio
import builtins
from collections.abc import Sequence
from types import ModuleType

import pytest

from kelvin_assistant.adapters.postgres import PostgresDatabaseClient
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.ports.database import (
    DatabaseConfigurationError,
    DatabaseUnavailableError,
)


def test_postgres_readiness_requires_database_url() -> None:
    """The adapter rejects missing database configuration explicitly."""

    settings = Settings(environment="test", database_url=None)
    client = PostgresDatabaseClient(settings)

    with pytest.raises(DatabaseConfigurationError, match="Database URL"):
        asyncio.run(client.check_readiness())


def test_postgres_readiness_reports_missing_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter reports an unavailable database when psycopg is absent."""

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
    settings = Settings(
        environment="test",
        database_url="postgresql://kelvin:secret@127.0.0.1:5432/kelvin_assistant",
        database_connect_timeout=1,
    )
    client = PostgresDatabaseClient(settings)

    with pytest.raises(DatabaseUnavailableError, match="driver"):
        asyncio.run(client.check_readiness())
