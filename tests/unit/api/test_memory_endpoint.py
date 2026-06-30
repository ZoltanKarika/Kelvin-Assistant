"""API contract tests for memory endpoints."""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.application.memory import MemoryService
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.domain.memory import MemoryItem, MemoryKind, MemoryScope
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.memory import (
    MemoryRepositoryUnavailableError,
    MemorySearchResult,
)

MEMORY_ID = UUID("462df5a5-a765-4159-9a6c-ca68bd832eaa")
CREATED_AT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def test_create_memory_stores_typed_memory() -> None:
    """POST /memory stores one typed memory item."""

    repository = FakeMemoryRepository(stored_memory=_memory())
    with TestClient(_app(repository)) as client:
        response = client.post(
            "/api/v1/memory",
            json={
                "scope": "user",
                "kind": "preference",
                "content": "  The user prefers step-by-step explanations.  ",
                "source": " chat ",
                "confidence": 0.9,
                "metadata": {"topic": "communication"},
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(MEMORY_ID),
        "scope": "user",
        "kind": "preference",
        "content": "The user prefers step-by-step explanations.",
        "source": "chat",
        "confidence": 0.9,
        "metadata": {"topic": "communication"},
        "created_at": "2026-06-30T12:00:00Z",
        "updated_at": None,
        "expires_at": None,
    }
    assert len(repository.added) == 1
    assert repository.added[0].content == "The user prefers step-by-step explanations."


def test_create_memory_rejects_whitespace_content() -> None:
    """POST /memory rejects empty text before reaching the service."""

    repository = FakeMemoryRepository()
    with TestClient(_app(repository)) as client:
        response = client.post(
            "/api/v1/memory",
            json={
                "scope": "user",
                "kind": "preference",
                "content": "   ",
                "source": "chat",
            },
        )

    assert response.status_code == 422
    assert repository.added == []


def test_list_memory_returns_active_memories_with_filters() -> None:
    """GET /memory returns active memories and forwards filters."""

    repository = FakeMemoryRepository(active_memories=(_memory(),))
    with TestClient(_app(repository)) as client:
        response = client.get(
            "/api/v1/memory",
            params={
                "scope": "user",
                "kind": "preference",
                "limit": "10",
            },
        )

    assert response.status_code == 200
    assert response.json()["memories"][0]["id"] == str(MEMORY_ID)
    assert repository.list_calls == [
        {
            "scope": MemoryScope.USER,
            "kind": MemoryKind.PREFERENCE,
            "limit": 10,
        }
    ]


def test_list_memory_rejects_invalid_limit() -> None:
    """GET /memory validates list limits at the API boundary."""

    repository = FakeMemoryRepository()
    with TestClient(_app(repository)) as client:
        response = client.get("/api/v1/memory", params={"limit": "0"})

    assert response.status_code == 422
    assert repository.list_calls == []


def test_delete_memory_soft_deletes_item() -> None:
    """DELETE /memory/{id} delegates forgetting to the memory service."""

    repository = FakeMemoryRepository()
    with TestClient(_app(repository)) as client:
        response = client.delete(f"/api/v1/memory/{MEMORY_ID}")

    assert response.status_code == 204
    assert response.content == b""
    assert repository.deleted == [MEMORY_ID]


def test_memory_repository_error_becomes_503() -> None:
    """Repository failures are translated into a stable HTTP status."""

    repository = FakeMemoryRepository(
        error=MemoryRepositoryUnavailableError("PostgreSQL is unavailable")
    )
    with TestClient(_app(repository)) as client:
        response = client.get("/api/v1/memory")

    assert response.status_code == 503
    assert response.json() == {"detail": "PostgreSQL is unavailable"}


def _app(repository: "FakeMemoryRepository") -> FastAPI:
    return create_app(
        Settings(
            app_name="Kelvin Test",
            app_version="0.5.0-test",
            environment="test",
            log_format="console",
        ),
        llm_provider=StubLLMProvider(),
        memory_service=MemoryService(repository),
    )


def _memory() -> MemoryItem:
    return MemoryItem(
        id=MEMORY_ID,
        scope=MemoryScope.USER,
        kind=MemoryKind.PREFERENCE,
        content="The user prefers step-by-step explanations.",
        source="chat",
        confidence=0.9,
        metadata={"topic": "communication"},
        created_at=CREATED_AT,
    )


class StubLLMProvider(LLMProvider):
    """Minimal language model provider for app construction."""

    async def generate(self, prompt: str) -> str:
        """Return a deterministic generated response."""

        return f"generated: {prompt}"

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Return a deterministic chat response."""

        _ = messages
        return "ok"

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Return a deterministic streamed response."""

        _ = messages
        yield "ok"

    async def check_readiness(self) -> None:
        """Report the stub provider as ready."""


class FakeMemoryRepository:
    """Fake repository used by memory API tests."""

    def __init__(
        self,
        *,
        stored_memory: MemoryItem | None = None,
        active_memories: tuple[MemoryItem, ...] = (),
        error: MemoryRepositoryUnavailableError | None = None,
    ) -> None:
        self._stored_memory = stored_memory
        self._active_memories = active_memories
        self._error = error
        self.added: list[MemoryItem] = []
        self.deleted: list[UUID] = []
        self.list_calls: list[dict[str, object]] = []

    async def add(self, memory: MemoryItem) -> MemoryItem:
        if self._error is not None:
            raise self._error
        self.added.append(memory)
        return self._stored_memory or memory

    async def list_active(
        self,
        *,
        scope: MemoryScope | None = None,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> tuple[MemoryItem, ...]:
        if self._error is not None:
            raise self._error
        self.list_calls.append(
            {
                "scope": scope,
                "kind": kind,
                "limit": limit,
            }
        )
        return self._active_memories

    async def delete(self, memory_id: UUID) -> None:
        if self._error is not None:
            raise self._error
        self.deleted.append(memory_id)

    async def search(
        self,
        query_embedding: tuple[float, ...],
        *,
        embedding_model: str,
        limit: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        _ = (query_embedding, embedding_model, limit)
        return ()
