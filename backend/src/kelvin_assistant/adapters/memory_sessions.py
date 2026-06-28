"""In-memory session storage adapter."""

import asyncio
from uuid import UUID

from kelvin_assistant.domain.chat import ChatSession
from kelvin_assistant.ports.sessions import (
    SessionConflictError,
    SessionNotFoundError,
    SessionStore,
)


class InMemorySessionStore(SessionStore):
    """Store immutable chat sessions in process memory."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, ChatSession] = {}
        self._lock = asyncio.Lock()

    async def add(self, session: ChatSession) -> None:
        """Store a new session unless its identifier already exists."""

        async with self._lock:
            if session.id in self._sessions:
                raise SessionConflictError(session.id)
            self._sessions[session.id] = session

    async def get(self, session_id: UUID) -> ChatSession:
        """Return a session by identifier."""

        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            return session

    async def update(
        self,
        session: ChatSession,
        expected_version: int,
    ) -> None:
        """Atomically replace a session using optimistic version checking."""

        async with self._lock:
            stored_session = self._sessions.get(session.id)
            if stored_session is None:
                raise SessionNotFoundError(session.id)
            if (
                stored_session.version != expected_version
                or session.version != expected_version + 1
            ):
                raise SessionConflictError(session.id)
            self._sessions[session.id] = session
