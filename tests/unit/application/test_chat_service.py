"""Unit tests for the non-streaming chat application service."""

import asyncio
from collections.abc import Sequence
from uuid import uuid4

import pytest

from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.application.chat import ChatService
from kelvin_assistant.domain.chat import ChatMessage, ChatRole, ChatSession
from kelvin_assistant.ports.llm import (
    LLMProviderError,
    LLMUnavailableError,
)
from kelvin_assistant.ports.sessions import SessionNotFoundError


class StubLLMProvider:
    """Configurable language model provider for application tests."""

    def __init__(
        self,
        responses: list[str] | None = None,
        error: LLMProviderError | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.chat_calls: list[tuple[ChatMessage, ...]] = []

    async def generate(self, prompt: str) -> str:
        """Return a deterministic generated response."""

        return f"generated: {prompt}"

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Record chat context and return the next configured response."""

        self.chat_calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        if not self._responses:
            msg = "No stub chat response configured"
            raise RuntimeError(msg)
        return self._responses.pop(0)

    async def check_readiness(self) -> None:
        """Report the stub provider as ready."""


def test_send_message_creates_and_persists_new_session() -> None:
    """A successful first turn creates a session containing both messages."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Szia!"])
        service = ChatService(provider, store)

        result = await service.send_message("  Szia!  ")

        stored_session = await store.get(result.session_id)
        assert result.message == "Szia!"
        assert stored_session.version == 1
        assert stored_session.messages == (
            ChatMessage(role=ChatRole.USER, content="Szia!"),
            ChatMessage(role=ChatRole.ASSISTANT, content="Szia!"),
        )
        assert provider.chat_calls == [
            (ChatMessage(role=ChatRole.USER, content="Szia!"),)
        ]

    asyncio.run(scenario())


def test_send_message_continues_existing_session_with_history() -> None:
    """A later turn sends prior messages and updates the same session."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Első válasz", "Második válasz"])
        service = ChatService(provider, store)
        first_result = await service.send_message("Első kérdés")

        second_result = await service.send_message(
            "Második kérdés",
            session_id=first_result.session_id,
        )

        stored_session = await store.get(first_result.session_id)
        assert second_result.session_id == first_result.session_id
        assert stored_session.version == 2
        assert provider.chat_calls[1] == (
            ChatMessage(role=ChatRole.USER, content="Első kérdés"),
            ChatMessage(role=ChatRole.ASSISTANT, content="Első válasz"),
            ChatMessage(role=ChatRole.USER, content="Második kérdés"),
        )

    asyncio.run(scenario())


def test_send_message_limits_model_history_without_deleting_session() -> None:
    """Only recent turns reach the model while full session history remains."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["V1", "V2", "V3"])
        service = ChatService(provider, store, history_turn_limit=1)
        first = await service.send_message("K1")
        await service.send_message("K2", session_id=first.session_id)

        await service.send_message("K3", session_id=first.session_id)

        stored_session = await store.get(first.session_id)
        assert len(stored_session.messages) == 6
        assert provider.chat_calls[2] == (
            ChatMessage(role=ChatRole.USER, content="K2"),
            ChatMessage(role=ChatRole.ASSISTANT, content="V2"),
            ChatMessage(role=ChatRole.USER, content="K3"),
        )

    asyncio.run(scenario())


def test_send_message_does_not_persist_failed_model_turn() -> None:
    """A provider failure leaves existing session state unchanged."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        original = ChatSession.create()
        await store.add(original)
        provider = StubLLMProvider(
            error=LLMUnavailableError("Ollama runtime is unavailable")
        )
        service = ChatService(provider, store)

        with pytest.raises(LLMUnavailableError):
            await service.send_message("Szia!", session_id=original.id)

        assert await store.get(original.id) == original

    asyncio.run(scenario())


def test_send_message_rejects_unknown_session() -> None:
    """An unknown session identifier is not replaced by a new session."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Nem használható"])
        service = ChatService(provider, store)
        session_id = uuid4()

        with pytest.raises(SessionNotFoundError):
            await service.send_message("Szia!", session_id=session_id)

        assert provider.chat_calls == []

    asyncio.run(scenario())


def test_chat_service_rejects_non_positive_history_limit() -> None:
    """A context policy must retain at least one previous turn."""

    with pytest.raises(ValueError, match="history_turn_limit must be positive"):
        ChatService(
            StubLLMProvider(),
            InMemorySessionStore(),
            history_turn_limit=0,
        )
