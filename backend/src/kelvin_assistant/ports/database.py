"""Database readiness port."""

from typing import Protocol


class DatabaseError(RuntimeError):
    """Base error raised by database adapters."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when database settings are incomplete."""


class DatabaseUnavailableError(DatabaseError):
    """Raised when the configured database cannot be reached."""


class DatabaseResponseError(DatabaseError):
    """Raised when the database returns an unexpected readiness response."""


class DatabaseClient(Protocol):
    """Interface for database infrastructure checks."""

    async def check_readiness(self) -> None:
        """Raise a database error when the database is not ready."""
        ...
