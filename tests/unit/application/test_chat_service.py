"""Unit tests for the non-streaming chat application service."""

import asyncio
from collections.abc import AsyncIterator, Sequence
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

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Record chat context and stream the next configured response."""

        self.chat_calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        if not self._responses:
            msg = "No stub chat response configured"
            raise RuntimeError(msg)
        for chunk in self._responses.pop(0).split("|"):
            yield chunk

    async def check_readiness(self) -> None:
        """Report the stub provider as ready."""


class StubKnowledgeContextProvider:
    """Configurable knowledge context provider for chat tests."""

    def __init__(self, context: str | None) -> None:
        self._context = context
        self.queries: list[str] = []

    async def get_context(self, query: str) -> str | None:
        self.queries.append(query)
        return self._context


class StubMemoryContextProvider:
    """Configurable memory context provider for chat tests."""

    def __init__(self, context: str | None) -> None:
        self._context = context
        self.queries: list[str] = []

    async def get_context(self, query: str) -> str | None:
        self.queries.append(query)
        return self._context


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


def test_send_message_prepends_system_prompt_without_persisting_it() -> None:
    """The configured persona reaches the model but not session history."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Természetesen!"])
        service = ChatService(
            provider,
            store,
            system_prompt="Mindig természetes magyar nyelven válaszolj.",
        )

        result = await service.send_message("Itt vagy?")

        assert provider.chat_calls == [
            (
                ChatMessage(
                    role=ChatRole.SYSTEM,
                    content="Mindig természetes magyar nyelven válaszolj.",
                ),
                ChatMessage(role=ChatRole.USER, content="Itt vagy?"),
            )
        ]
        stored_session = await store.get(result.session_id)
        assert all(
            message.role is not ChatRole.SYSTEM for message in stored_session.messages
        )

    asyncio.run(scenario())


def test_send_message_adds_knowledge_context_without_persisting_it() -> None:
    """RAG context reaches the model but is not stored as chat history."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Az Ollama a Windows hoston fut."])
        knowledge_provider = StubKnowledgeContextProvider(
            context="[1] source=Kelvin Notes; chunk=2\nOllama a Windows hoston fut."
        )
        service = ChatService(
            provider,
            store,
            system_prompt="Te Kelvin vagy.",
            knowledge_context_provider=knowledge_provider,
        )

        result = await service.send_message("Hol fut az Ollama?")

        assert knowledge_provider.queries == ["Hol fut az Ollama?"]
        assert provider.chat_calls == [
            (
                ChatMessage(role=ChatRole.SYSTEM, content="Te Kelvin vagy."),
                ChatMessage(
                    role=ChatRole.SYSTEM,
                    content=(
                        "Use the following local knowledge base excerpts if they "
                        "are relevant to the user's question. If they are not "
                        "relevant, ignore them. Do not invent sources.\n\n"
                        "[1] source=Kelvin Notes; chunk=2\n"
                        "Ollama a Windows hoston fut."
                    ),
                ),
                ChatMessage(role=ChatRole.USER, content="Hol fut az Ollama?"),
            )
        ]
        stored_session = await store.get(result.session_id)
        assert stored_session.messages == (
            ChatMessage(role=ChatRole.USER, content="Hol fut az Ollama?"),
            ChatMessage(
                role=ChatRole.ASSISTANT,
                content="Az Ollama a Windows hoston fut.",
            ),
        )

    asyncio.run(scenario())


def test_send_message_adds_memory_context_without_persisting_it() -> None:
    """Long-term memory context reaches the model but not session history."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Lépésenként magyarázok."])
        memory_provider = StubMemoryContextProvider(
            context=(
                "[1] scope=user; kind=preference; confidence=0.90\n"
                "The user prefers step-by-step explanations."
            )
        )
        service = ChatService(
            provider,
            store,
            system_prompt="Te Kelvin vagy.",
            memory_context_provider=memory_provider,
        )

        result = await service.send_message("Magyarázd el a FastAPI-t.")

        assert memory_provider.queries == ["Magyarázd el a FastAPI-t."]
        assert provider.chat_calls == [
            (
                ChatMessage(role=ChatRole.SYSTEM, content="Te Kelvin vagy."),
                ChatMessage(
                    role=ChatRole.SYSTEM,
                    content=(
                        "Use the following long-term memories to personalize the "
                        "answer if they are relevant. Do not claim that these "
                        "memories are complete or exhaustive.\n\n"
                        "[1] scope=user; kind=preference; confidence=0.90\n"
                        "The user prefers step-by-step explanations."
                    ),
                ),
                ChatMessage(role=ChatRole.USER, content="Magyarázd el a FastAPI-t."),
            )
        ]
        stored_session = await store.get(result.session_id)
        assert stored_session.messages == (
            ChatMessage(role=ChatRole.USER, content="Magyarázd el a FastAPI-t."),
            ChatMessage(
                role=ChatRole.ASSISTANT,
                content="Lépésenként magyarázok.",
            ),
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


def test_stream_message_persists_complete_streamed_turn() -> None:
    """A streamed response is persisted only after all chunks finish."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        provider = StubLLMProvider(responses=["Szi|a!"])
        service = ChatService(provider, store)

        result = await service.stream_message("Szia!")
        chunks = [chunk async for chunk in result.chunks]

        assert chunks == ["Szi", "a!"]
        stored_session = await store.get(result.session_id)
        assert stored_session.messages == (
            ChatMessage(role=ChatRole.USER, content="Szia!"),
            ChatMessage(role=ChatRole.ASSISTANT, content="Szia!"),
        )

    asyncio.run(scenario())


def test_stream_message_does_not_persist_failed_stream() -> None:
    """A provider streaming failure leaves the session unchanged."""

    async def scenario() -> None:
        store = InMemorySessionStore()
        original = ChatSession.create()
        await store.add(original)
        provider = StubLLMProvider(
            error=LLMUnavailableError("Ollama runtime is unavailable")
        )
        service = ChatService(provider, store)

        result = await service.stream_message("Szia!", session_id=original.id)
        with pytest.raises(LLMUnavailableError):
            _ = [chunk async for chunk in result.chunks]

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
