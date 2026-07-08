"""Tests for the public system endpoints."""

from collections.abc import AsyncIterator, Iterator, Sequence

import pytest
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.file_api_tokens import (
    FileApiTokenAuthenticator,
    hash_api_token,
)
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.auth import ApiPrincipal, ApiScope, StoredApiToken
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


def test_runtime_status_reports_degraded_without_database(client: TestClient) -> None:
    """The status endpoint summarizes optional and required runtime components."""

    response = client.get("/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"

    components = {component["name"]: component for component in data["components"]}
    assert components["api"] == {
        "name": "api",
        "status": "ready",
        "required": True,
        "detail": "FastAPI process is running.",
    }
    assert components["auth"]["status"] == "disabled"
    assert components["auth"]["required"] is False
    assert components["llm"]["status"] == "ready"
    assert components["llm"]["required"] is True
    assert components["database"]["status"] == "unconfigured"
    assert components["database"]["required"] is False
    assert components["n8n"]["status"] == "unconfigured"
    assert components["n8n"]["required"] is False


def test_runtime_status_reports_ready_when_required_components_are_ready(
    settings: Settings,
) -> None:
    """Configured auth, LLM, and database produce an overall ready status."""

    ready_settings = settings.model_copy(
        update={
            "api_auth_mode": "required",
            "api_token_file": "api-tokens.json",
            "database_url": "postgresql://kelvin:test@localhost/kelvin",
            "n8n_url": "http://n8n.local:5678",
        }
    )
    with TestClient(
        create_app(
            ready_settings,
            llm_provider=StubLLMProvider(),
            database_client=StubDatabaseClient(),
            api_authenticator=_system_read_authenticator(),
        )
    ) as ready_client:
        response = ready_client.get(
            "/status",
            headers={"Authorization": "Bearer kelvin-status-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    components = {component["name"]: component for component in data["components"]}
    assert components["auth"]["status"] == "ready"
    assert components["database"]["status"] == "ready"
    assert components["n8n"]["status"] == "ready"


def test_runtime_status_reports_unavailable_provider(settings: Settings) -> None:
    """A required LLM failure makes aggregate runtime status unavailable."""

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
        response = unavailable_client.get("/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    components = {component["name"]: component for component in data["components"]}
    assert components["llm"]["status"] == "unavailable"
    assert components["llm"]["detail"] == "Ollama runtime is unavailable"


def test_runtime_status_reports_unavailable_database(settings: Settings) -> None:
    """A configured database failure makes aggregate runtime status unavailable."""

    database_settings = settings.model_copy(
        update={"database_url": "postgresql://kelvin:test@localhost/kelvin"}
    )
    database_client = StubDatabaseClient(
        readiness_error=DatabaseUnavailableError("PostgreSQL database is unavailable")
    )
    with TestClient(
        create_app(
            database_settings,
            llm_provider=StubLLMProvider(),
            database_client=database_client,
        )
    ) as unavailable_client:
        response = unavailable_client.get("/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    components = {component["name"]: component for component in data["components"]}
    assert components["database"]["status"] == "unavailable"
    assert components["database"]["required"] is True


def test_runtime_status_reports_unavailable_production_without_auth(
    settings: Settings,
) -> None:
    """Production runtime status highlights disabled API auth as unavailable."""

    production_settings = settings.model_copy(update={"environment": "production"})
    with TestClient(
        create_app(
            production_settings,
            llm_provider=StubLLMProvider(),
            database_client=StubDatabaseClient(),
        )
    ) as production_client:
        response = production_client.get("/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    components = {component["name"]: component for component in data["components"]}
    assert components["auth"]["status"] == "disabled"
    assert components["auth"]["required"] is True


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
    assert readiness_response.json() == {"detail": "PostgreSQL database is unavailable"}
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_version_returns_configured_version(client: TestClient) -> None:
    """The version endpoint exposes the configured application version."""

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "9.9.9"}


def _system_read_authenticator() -> FileApiTokenAuthenticator:
    return FileApiTokenAuthenticator(
        (
            StoredApiToken(
                principal=ApiPrincipal(
                    id="status-monitor",
                    scopes=frozenset({ApiScope.SYSTEM_READ}),
                ),
                token_sha256=hash_api_token("kelvin-status-token"),
            ),
        )
    )
