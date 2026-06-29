"""Session storage port and provider-independent errors."""

from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.chat import ChatSession


class SessionStoreError(RuntimeError):
    """Base error raised by session storage implementations."""


class SessionNotFoundError(SessionStoreError):
    """Raised when a requested chat session does not exist."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__(f"Chat session not found: {session_id}")
        self.session_id = session_id


class SessionConflictError(SessionStoreError):
    """Raised when a chat session changed concurrently."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__(f"Chat session changed concurrently: {session_id}")
        self.session_id = session_id


class SessionStore(Protocol):
    """Persistence boundary for versioned chat sessions."""

    async def add(self, session: ChatSession) -> None:
        """Store a new session or raise a conflict if it already exists."""
        ...

    async def get(self, session_id: UUID) -> ChatSession:
        """Return an existing session or raise a not-found error."""
        ...

    async def update(
        self,
        session: ChatSession,
        expected_version: int,
    ) -> None:
        """Replace a session when its stored version matches the expectation."""
        ...
