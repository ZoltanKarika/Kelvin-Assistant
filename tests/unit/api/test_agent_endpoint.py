"""API contract tests for server-managed agent runs."""

from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.memory_agent_runs import InMemoryAgentRunStore
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import AgentRun
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.ports.agent_runs import AgentRunConflictError
from kelvin_assistant.ports.llm import LLMProvider


def test_create_agent_run_persists_server_managed_state() -> None:
    """POST /agent/runs creates received state with a server UUID."""

    with TestClient(_app()) as client:
        response = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "  Inspect the repository.  ",
                "max_steps": 5,
            },
        )
        stored = client.get(f"/api/v1/agent/runs/{response.json()['id']}")

    assert response.status_code == 201
    assert response.json() == stored.json()
    assert response.json() == {
        "id": response.json()["id"],
        "goal": "Inspect the repository.",
        "status": "received",
        "step_count": 0,
        "max_steps": 5,
        "version": 0,
    }
    assert UUID(response.json()["id"])


def test_create_agent_run_rejects_invalid_input() -> None:
    """Agent goals and step limits are validated at the API boundary."""

    with TestClient(_app()) as client:
        whitespace = client.post(
            "/api/v1/agent/runs",
            json={"goal": "   "},
        )
        invalid_steps = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Inspect the repository", "max_steps": 0},
        )

    assert whitespace.status_code == 422
    assert invalid_steps.status_code == 422


def test_get_agent_run_returns_404_for_unknown_id() -> None:
    """Unknown server-side run identifiers are not created implicitly."""

    run_id = uuid4()
    with TestClient(_app()) as client:
        response = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Agent run not found: {run_id}"}


def test_begin_planning_updates_status_and_version() -> None:
    """POST /plan performs one persisted lifecycle transition."""

    with TestClient(_app()) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Inspect the repository"},
        )
        run_id = created.json()["id"]
        planned = client.post(f"/api/v1/agent/runs/{run_id}/plan")
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert planned.status_code == 200
    assert planned.json()["status"] == "planning"
    assert planned.json()["version"] == 1
    assert stored.json() == planned.json()


def test_begin_planning_rejects_repeated_transition() -> None:
    """A run already in planning cannot repeat the state transition."""

    with TestClient(_app()) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Inspect the repository"},
        )
        run_id = created.json()["id"]
        first = client.post(f"/api/v1/agent/runs/{run_id}/plan")
        repeated = client.post(f"/api/v1/agent/runs/{run_id}/plan")

    assert first.status_code == 200
    assert repeated.status_code == 409
    assert "Cannot begin planning" in repeated.json()["detail"]


def test_begin_planning_returns_404_for_unknown_id() -> None:
    """Planning cannot start for a missing server-managed run."""

    run_id = uuid4()
    with TestClient(_app()) as client:
        response = client.post(f"/api/v1/agent/runs/{run_id}/plan")

    assert response.status_code == 404


def test_begin_planning_translates_concurrent_update_to_409() -> None:
    """Optimistic locking conflicts have a stable HTTP response."""

    store = ConflictAgentRunStore()
    with TestClient(_app(agent_run_store=store)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={"goal": "Inspect the repository"},
        )
        run_id = created.json()["id"]
        response = client.post(f"/api/v1/agent/runs/{run_id}/plan")

    assert response.status_code == 409
    assert "changed concurrently" in response.json()["detail"]


def _app(
    *,
    agent_run_store: InMemoryAgentRunStore | None = None,
) -> FastAPI:
    return create_app(
        Settings(
            app_name="Kelvin Test",
            app_version="0.6.0-test",
            environment="test",
            log_format="console",
        ),
        llm_provider=StubLLMProvider(),
        agent_run_store=agent_run_store,
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


class ConflictAgentRunStore(InMemoryAgentRunStore):
    """Store that simulates an optimistic locking conflict."""

    async def update(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Reject every update after successful creation."""

        _ = expected_version
        raise AgentRunConflictError(run.id)
