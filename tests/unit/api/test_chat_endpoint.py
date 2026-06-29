"""API contract tests for the non-streaming chat endpoint."""

import asyncio
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.memory_sessions import InMemorySessionStore
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage, ChatRole, ChatSession
from kelvin_assistant.ports.llm import (
    LLMProviderError,
    LLMResponseError,
    LLMUnavailableError,
)
from kelvin_assistant.ports.sessions import SessionConflictError


class StubLLMProvider:
    """Configurable language model provider for API contract tests."""

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
        """Record context and return the next configured response."""

        self.chat_calls.append(tuple(messages))
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)

    async def check_readiness(self) -> None:
        """Report the stub provider as ready."""


class ConflictSessionStore(InMemorySessionStore):
    """Session store that simulates an optimistic locking conflict."""

    async def update(
        self,
        session: ChatSession,
        expected_version: int,
    ) -> None:
        """Reject every update as a concurrent change."""

        raise SessionConflictError(session.id)


@pytest.fixture
def settings() -> Settings:
    """Create deterministic API settings."""

    return Settings(
        app_name="Kelvin Test",
        app_version="0.3.0-test",
        environment="test",
        log_format="console",
        ollama_model="gemma4:test",
    )


def test_chat_creates_new_session(settings: Settings) -> None:
    """A request without session ID returns and persists a new session."""

    provider = StubLLMProvider(responses=["Szia!"])
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post("/api/v1/chat", json={"message": "  Szia!  "})

    assert response.status_code == 200
    body = response.json()
    assert UUID(body["session_id"])
    assert body["message"] == "Szia!"
    assert body["model"] == "gemma4:test"
    assert provider.chat_calls[0][0].role is ChatRole.SYSTEM


def test_chat_continues_existing_session(settings: Settings) -> None:
    """A returned session ID can be used for a subsequent turn."""

    provider = StubLLMProvider(responses=["Első válasz", "Második válasz"])
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        first = client.post("/api/v1/chat", json={"message": "Első kérdés"})
        session_id = first.json()["session_id"]

        second = client.post(
            "/api/v1/chat",
            json={"message": "Második kérdés", "session_id": session_id},
        )

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id
    assert len(provider.chat_calls[1]) == 4


def test_chat_rejects_whitespace_only_message(settings: Settings) -> None:
    """Whitespace-only input is rejected before model invocation."""

    provider = StubLLMProvider(responses=["Nem használható"])
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post("/api/v1/chat", json={"message": "   "})

    assert response.status_code == 422
    assert provider.chat_calls == []


def test_chat_returns_404_for_unknown_session(settings: Settings) -> None:
    """An unknown session identifier is not replaced silently."""

    provider = StubLLMProvider(responses=["Nem használható"])
    session_id = uuid4()
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Szia!", "session_id": str(session_id)},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": f"Chat session not found: {session_id}"}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LLMUnavailableError("Ollama runtime is unavailable"), 503),
        (LLMResponseError("Ollama returned an invalid chat response"), 502),
    ],
)
def test_chat_translates_provider_error(
    settings: Settings,
    error: LLMProviderError,
    expected_status: int,
) -> None:
    """Provider failures are translated to stable HTTP status codes."""

    provider = StubLLMProvider(error=error)
    with TestClient(create_app(settings, llm_provider=provider)) as client:
        response = client.post("/api/v1/chat", json={"message": "Szia!"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_chat_returns_409_for_concurrent_update(settings: Settings) -> None:
    """An optimistic locking conflict becomes an HTTP 409 response."""

    provider = StubLLMProvider(responses=["Első válasz", "Második válasz"])
    store = ConflictSessionStore()
    initial = ChatSession.create().append_turn("Első kérdés", "Első válasz")

    async def add_initial_session() -> None:
        await store.add(initial)

    asyncio.run(add_initial_session())
    with TestClient(
        create_app(settings, llm_provider=provider, session_store=store)
    ) as client:
        response = client.post(
            "/api/v1/chat",
            json={"message": "Második kérdés", "session_id": str(initial.id)},
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": f"Chat session changed concurrently: {initial.id}"
    }
