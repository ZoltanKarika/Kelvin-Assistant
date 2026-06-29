"""Tests for the public system endpoints."""

from collections.abc import AsyncIterator, Iterator, Sequence

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.ports.database import DatabaseError, DatabaseUnavailableError
from kelvin_assistant.ports.llm import (
    LLMProviderError,
    LLMUnavailableError,
)


class StubLLMProvider:
    """Deterministic language model provider for API tests."""

    def __init__(self, readiness_error: LLMProviderError | None = None) -> None:
        self._readiness_error = readiness_error

    async def generate(self, prompt: str) -> str:
        """Return a deterministic generated response."""

        return f"generated: {prompt}"

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Return a deterministic chat response."""

        return f"chat messages: {len(messages)}"

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Return a deterministic streaming chat response."""

        yield f"chat messages: {len(messages)}"

    async def check_readiness(self) -> None:
        """Raise the configured readiness error, if any."""

        if self._readiness_error is not None:
            raise self._readiness_error


class StubDatabaseClient:
    """Deterministic database client for API tests."""

    def __init__(self, readiness_error: DatabaseError | None = None) -> None:
        self._readiness_error = readiness_error

    async def check_readiness(self) -> None:
        """Raise the configured readiness error, if any."""

        if self._readiness_error is not None:
            raise self._readiness_error


@pytest.fixture
def settings() -> Settings:
    """Create deterministic API test settings."""

    return Settings(
        app_name="Kelvin Test",
        app_version="9.9.9",
        environment="test",
        log_format="console",
        ollama_model="gemma4:test",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Create an isolated API client with a ready language model."""

    with TestClient(
        create_app(
            settings,
            llm_provider=StubLLMProvider(),
            database_client=StubDatabaseClient(),
        )
    ) as test_client:
        yield test_client


def test_root_returns_application_metadata(client: TestClient) -> None:
    """The root endpoint exposes the configured application metadata."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Kelvin Test",
        "version": "9.9.9",
        "environment": "test",
    }


def test_health_reports_ok(client: TestClient) -> None:
    """The health endpoint reports that the API process is available."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_configured_model(client: TestClient) -> None:
    """The readiness endpoint reports the ready provider and model."""

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "provider": "ollama",
        "model": "gemma4:test",
    }


def test_readiness_reports_unavailable_provider(settings: Settings) -> None:
    """The readiness endpoint returns 503 while process health stays OK."""

    provider = StubLLMProvider(
        readiness_error=LLMUnavailableError("Ollama runtime is unavailable")
    )
    with TestClient(
        create_app(
            settings,
            llm_provider=provider,
            database_client=StubDatabaseClient(),
        )
    ) as unavailable_client:
        readiness_response = unavailable_client.get("/ready")
        health_response = unavailable_client.get("/health")

    assert readiness_response.status_code == 503
    assert readiness_response.json() == {"detail": "Ollama runtime is unavailable"}
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_database_readiness_reports_ready(client: TestClient) -> None:
    """The database readiness endpoint reports the configured database."""

    response = client.get("/ready/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "provider": "postgresql"}


def test_database_readiness_reports_unavailable_database(
    settings: Settings,
) -> None:
    """Database readiness failures return 503 while health stays OK."""

    database_client = StubDatabaseClient(
        readiness_error=DatabaseUnavailableError("PostgreSQL database is unavailable")
    )
    with TestClient(
        create_app(
            settings,
            llm_provider=StubLLMProvider(),
            database_client=database_client,
        )
    ) as unavailable_client:
        readiness_response = unavailable_client.get("/ready/database")
        health_response = unavailable_client.get("/health")

    assert readiness_response.status_code == 503
    assert readiness_response.json() == {
        "detail": "PostgreSQL database is unavailable"
    }
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_version_returns_configured_version(client: TestClient) -> None:
    """The version endpoint exposes the configured application version."""

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "9.9.9"}
