"""Unit tests for the in-memory session storage adapter."""

import asyncio
from uuid import uuid4

import pytest

from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.domain.chat import ChatSession
from kelvin_assistant.ports.sessions import (
    SessionConflictError,
    SessionNotFoundError,
)


def test_add_and_get_session() -> None:
    """A newly added immutable session can be retrieved unchanged."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        session = ChatSession.create()

        await store.add(session)

        assert await store.get(session.id) == session

    asyncio.run(scenario())


def test_get_rejects_unknown_session() -> None:
    """Looking up an unknown identifier raises a stable domain error."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        session_id = uuid4()

        with pytest.raises(
            SessionNotFoundError,
            match=f"Chat session not found: {session_id}",
        ):
            await store.get(session_id)

    asyncio.run(scenario())


def test_add_rejects_duplicate_session() -> None:
    """A duplicate identifier cannot silently replace session state."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        session = ChatSession.create()
        await store.add(session)

        with pytest.raises(SessionConflictError):
            await store.add(session)

    asyncio.run(scenario())


def test_update_replaces_expected_session_version() -> None:
    """An update succeeds when the stored version matches the expectation."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        original = ChatSession.create()
        updated = original.append_turn("Szia!", "Szia!")
        await store.add(original)

        await store.update(updated, expected_version=0)

        assert await store.get(original.id) == updated

    asyncio.run(scenario())


def test_update_rejects_stale_session_version() -> None:
    """Only the first update based on a session version can succeed."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        original = ChatSession.create()
        first_update = original.append_turn("Első", "Első válasz")
        stale_update = original.append_turn("Második", "Második válasz")
        await store.add(original)
        await store.update(first_update, expected_version=0)

        with pytest.raises(
            SessionConflictError,
            match=f"Chat session changed concurrently: {original.id}",
        ):
            await store.update(stale_update, expected_version=0)

    asyncio.run(scenario())


def test_update_rejects_unknown_session() -> None:
    """An update cannot create a missing session implicitly."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        session = ChatSession.create().append_turn("Szia!", "Szia!")

        with pytest.raises(SessionNotFoundError):
            await store.update(session, expected_version=0)

    asyncio.run(scenario())
