"""PostgreSQL database adapter."""

import logging
from typing import Any

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.ports.database import (
    DatabaseConfigurationError,
    DatabaseResponseError,
    DatabaseUnavailableError,
)

LOGGER = logging.getLogger(__name__)


class PostgresDatabaseClient:
    """Database client backed by PostgreSQL."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the adapter with runtime settings."""

        self._settings = settings or get_settings()

    async def check_readiness(self) -> None:
        """Check that PostgreSQL accepts a simple query."""

        if self._settings.database_url is None:
            msg = "Database URL is not configured"
            raise DatabaseConfigurationError(msg)

        try:
            import psycopg
        except ModuleNotFoundError as exc:
            LOGGER.warning("PostgreSQL driver is not installed")
            raise DatabaseUnavailableError(
                "PostgreSQL driver is not installed"
            ) from exc

        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("select 1")
                    row: Any = await cursor.fetchone()
        except Exception as exc:
            LOGGER.warning("PostgreSQL database is unavailable: %s", exc)
            raise DatabaseUnavailableError(
                "PostgreSQL database is unavailable"
            ) from exc

        if row != (1,):
            LOGGER.warning("PostgreSQL readiness query returned an invalid row")
            raise DatabaseResponseError("PostgreSQL returned an invalid response")
