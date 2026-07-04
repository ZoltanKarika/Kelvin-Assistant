"""API contract tests for server-managed agent runs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kelvin_assistant.adapters.memory_agent_runs import InMemoryAgentRunStore
from kelvin_assistant.api.app import create_app
from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.tool_policy import DefaultToolPolicy
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import (
    AgentRun,
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.domain.planner import (
    ClarifyDecision,
    CompleteDecision,
    PlannerDecision,
    PlannerRequest,
    ToolDecision,
)
from kelvin_assistant.ports.agent_runs import AgentRunConflictError
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.planner import (
    AgentPlanner,
    AgentPlannerResponseError,
)
from kelvin_assistant.tools.registry import StaticToolRegistry


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
        "workspace_id": None,
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


def test_cancel_run_closes_active_tool_proposal() -> None:
    """Cancellation persists a terminal state and retires pending work."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        cancelled = client.post(f"/api/v1/agent/runs/{run_id}/cancel")
        active = client.get(f"/api/v1/agent/runs/{run_id}/tools/active")
        repeated = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert active.status_code == 404
    assert repeated.status_code == 409
    assert "terminal" in repeated.json()["detail"]


def test_cancel_run_returns_404_for_unknown_id() -> None:
    """Cancellation cannot create or hide an unknown run."""

    run_id = uuid4()
    with TestClient(_app()) as client:
        response = client.post(f"/api/v1/agent/runs/{run_id}/cancel")

    assert response.status_code == 404


def test_propose_read_tool_enters_execution_without_approval() -> None:
    """An allowed read proposal is persisted in executing state."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["policy_decision"] == "allow"
    assert response.json()["approval_status"] is None
    assert response.json()["run"]["status"] == "executing"
    assert response.json()["run"]["version"] == 2
    assert stored.json() == response.json()["run"]


def test_propose_write_tool_waits_for_approval() -> None:
    """A write proposal is persisted with pending approval."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("file.patch", "write"),
        )

    assert response.status_code == 200
    assert response.json()["policy_decision"] == "require_approval"
    assert response.json()["approval_status"] == "pending"
    assert response.json()["run"]["status"] == "awaiting_approval"
    assert response.json()["run"]["version"] == 2


def test_approve_write_tool_enters_execution() -> None:
    """Approval is bound to the stored tool call before execution."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("file.patch", "write"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/approval",
            json={
                "tool_call_id": proposed.json()["tool_call_id"],
                "decision": "approved",
            },
        )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"
    assert response.json()["run"]["status"] == "executing"
    assert response.json()["run"]["version"] == 3


def test_reject_write_tool_cancels_run() -> None:
    """Rejecting a pending write prevents execution."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("file.patch", "write"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/approval",
            json={
                "tool_call_id": proposed.json()["tool_call_id"],
                "decision": "rejected",
            },
        )

    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"
    assert response.json()["run"]["status"] == "cancelled"
    assert response.json()["run"]["step_count"] == 0


def test_approval_rejects_mismatched_tool_call_id() -> None:
    """A client cannot approve a different or invented tool call."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("file.patch", "write"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/approval",
            json={
                "tool_call_id": str(uuid4()),
                "decision": "approved",
            },
        )

    assert response.status_code == 409
    assert "does not match" in response.json()["detail"]


def test_unknown_tool_is_denied_without_changing_run() -> None:
    """An invented tool remains denied even in an allowed workspace."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("system.unknown", "read"),
        )

    assert response.status_code == 200
    assert response.json()["policy_decision"] == "deny"
    assert response.json()["run"]["status"] == "planning"
    assert response.json()["run"]["version"] == 1


def test_unconfigured_workspace_is_denied() -> None:
    """A client cannot self-authorize an unknown workspace ID."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Inspect another project",
                "workspace_id": "unknown-project",
            },
        )
        run_id = created.json()["id"]
        client.post(f"/api/v1/agent/runs/{run_id}/plan")
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )

    assert response.status_code == 200
    assert response.json()["policy_decision"] == "deny"
    assert "workspace" in response.json()["policy_reason"]


def test_tool_cannot_target_a_different_workspace() -> None:
    """Tool arguments cannot escape the workspace bound to the run."""

    request = _tool_request("git.status", "read")
    request["arguments"] = {"workspace": "another-project"}

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=request,
        )

    assert response.status_code == 200
    assert response.json()["policy_decision"] == "deny"
    assert "different workspace" in response.json()["policy_reason"]


def test_get_active_tool_returns_server_managed_arguments() -> None:
    """The local client can fetch the exact active proposal to execute."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        active = client.get(f"/api/v1/agent/runs/{run_id}/tools/active")

    assert active.status_code == 200
    assert active.json() == proposed.json()
    assert active.json()["arguments"] == {"workspace": "kelvin-assistant"}
    assert active.json()["risk"] == "read"


def test_submit_successful_tool_result_moves_run_to_observing() -> None:
    """A matching successful result closes the proposal and is persisted."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/result",
            json={
                "tool_call_id": proposed.json()["tool_call_id"],
                "succeeded": True,
                "output": "## main",
                "truncated": False,
                "duration_ms": 8,
            },
        )
        no_longer_active = client.get(f"/api/v1/agent/runs/{run_id}/tools/active")

    assert response.status_code == 200
    assert response.json()["succeeded"] is True
    assert response.json()["output"] == "## main"
    assert response.json()["run"]["status"] == "observing"
    assert response.json()["run"]["version"] == 3
    assert no_longer_active.status_code == 404


def test_submit_failed_tool_result_moves_run_to_failed() -> None:
    """A matching failed result terminates the run with an error."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/result",
            json={
                "tool_call_id": proposed.json()["tool_call_id"],
                "succeeded": False,
                "error": "Git is unavailable",
                "duration_ms": 2,
            },
        )

    assert response.status_code == 200
    assert response.json()["succeeded"] is False
    assert response.json()["error"] == "Git is unavailable"
    assert response.json()["run"]["status"] == "failed"


def test_submit_tool_result_rejects_mismatched_call_id() -> None:
    """A client cannot submit a result for another tool call."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/result",
            json={
                "tool_call_id": str(uuid4()),
                "succeeded": True,
                "output": "invented",
            },
        )

    assert response.status_code == 409
    assert "does not match" in response.json()["detail"]


def test_submit_tool_result_rejects_inconsistent_failure() -> None:
    """A failed result must contain an error explanation."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/result",
            json={
                "tool_call_id": proposed.json()["tool_call_id"],
                "succeeded": False,
            },
        )

    assert response.status_code == 422
    assert "requires an error" in response.json()["detail"]


def test_submit_tool_result_cannot_complete_twice() -> None:
    """Closing a proposal prevents duplicate result submission."""

    with TestClient(_app(agent_service=_tool_service())) as client:
        run_id = _create_planned_run(client)
        proposed = client.post(
            f"/api/v1/agent/runs/{run_id}/tools",
            json=_tool_request("git.status", "read"),
        )
        payload = {
            "tool_call_id": proposed.json()["tool_call_id"],
            "succeeded": True,
            "output": "## main",
        }
        first = client.post(f"/api/v1/agent/runs/{run_id}/result", json=payload)
        repeated = client.post(
            f"/api/v1/agent/runs/{run_id}/result",
            json=payload,
        )

    assert first.status_code == 200
    assert repeated.status_code == 404


def test_next_plans_and_persists_read_only_tool() -> None:
    """Natural-language planning reuses registry risk and policy evaluation."""

    planner = StubAgentPlanner(
        ToolDecision(
            tool_name="git.status",
            arguments={"include_untracked": True},
            reason="Inspect repository state.",
            expected_effect="No workspace change.",
        )
    )
    with TestClient(_app(agent_planner=planner)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Show the Git status",
                "workspace_id": "kelvin-assistant",
            },
        )
        run_id = created.json()["id"]
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={},
        )
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["action"] == "tool"
    proposal = response.json()["proposal"]
    assert proposal["tool_name"] == "git.status"
    assert proposal["risk"] == "read"
    assert proposal["policy_decision"] == "allow"
    assert proposal["run"]["status"] == "executing"
    assert stored.json()["status"] == "executing"
    assert len(planner.requests) == 1


def test_next_continues_after_targeted_clarification() -> None:
    """Client-carried clarification context can resume the persisted run."""

    planner = StubAgentPlanner(
        ClarifyDecision(
            question="Which file should be changed?",
            reason="The target file is missing.",
        ),
        CompleteDecision(summary="The target is now clear."),
    )
    with TestClient(_app(agent_planner=planner)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Update the documentation",
                "workspace_id": "kelvin-assistant",
            },
        )
        run_id = created.json()["id"]
        clarification = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={},
        )
        completion = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={
                "clarifications": [
                    {
                        "question": "Which file should be changed?",
                        "answer": "README.md",
                    }
                ]
            },
        )

    assert clarification.status_code == 200
    assert clarification.json()["action"] == "clarify"
    assert clarification.json()["run"]["status"] == "clarifying"
    assert completion.status_code == 200
    assert completion.json()["action"] == "complete"
    assert completion.json()["run"]["status"] == "completed"
    assert planner.requests[1].clarifications[0].answer == "README.md"


def test_next_rejects_tool_for_unauthorized_workspace() -> None:
    """Planner output cannot bypass deterministic workspace authorization."""

    planner = StubAgentPlanner(
        ToolDecision(
            tool_name="git.status",
            arguments={},
            reason="Inspect state.",
            expected_effect="No change.",
        )
    )
    with TestClient(_app(agent_planner=planner)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Inspect another project",
                "workspace_id": "other-project",
            },
        )
        run_id = created.json()["id"]
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={},
        )
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 403
    assert stored.json()["status"] == "failed"


def test_next_fails_run_for_invalid_planner_arguments() -> None:
    """Schema-invalid model arguments never become an executable proposal."""

    planner = StubAgentPlanner(
        ToolDecision(
            tool_name="git.status",
            arguments={"include_untracked": "yes"},
            reason="Inspect state.",
            expected_effect="No change.",
        )
    )
    with TestClient(_app(agent_planner=planner)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Inspect repository",
                "workspace_id": "kelvin-assistant",
            },
        )
        run_id = created.json()["id"]
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={},
        )
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 502
    assert "must be boolean" in response.json()["detail"]
    assert stored.json()["status"] == "failed"


def test_next_fails_run_for_unusable_planner_response() -> None:
    """Two invalid LLM responses leave an auditable failed run."""

    planner = StubAgentPlanner(
        error=AgentPlannerResponseError("invalid structured output twice")
    )
    with TestClient(_app(agent_planner=planner)) as client:
        created = client.post(
            "/api/v1/agent/runs",
            json={
                "goal": "Inspect repository",
                "workspace_id": "kelvin-assistant",
            },
        )
        run_id = created.json()["id"]
        response = client.post(
            f"/api/v1/agent/runs/{run_id}/next",
            json={},
        )
        stored = client.get(f"/api/v1/agent/runs/{run_id}")

    assert response.status_code == 502
    assert stored.json()["status"] == "failed"


def _app(
    *,
    agent_run_store: InMemoryAgentRunStore | None = None,
    agent_service: AgentService | None = None,
    agent_planner: AgentPlanner | None = None,
) -> FastAPI:
    return create_app(
        Settings(
            app_name="Kelvin Test",
            app_version="0.6.0-test",
            environment="test",
            log_format="console",
            agent_workspace_ids=("kelvin-assistant",),
        ),
        llm_provider=StubLLMProvider(),
        agent_run_store=agent_run_store,
        agent_service=agent_service,
        agent_planner=agent_planner,
    )


def _create_planned_run(client: TestClient) -> str:
    created = client.post(
        "/api/v1/agent/runs",
        json={
            "goal": "Inspect the repository",
            "workspace_id": "kelvin-assistant",
        },
    )
    run_id: str = created.json()["id"]
    planned = client.post(f"/api/v1/agent/runs/{run_id}/plan")
    assert planned.status_code == 200
    return run_id


def _tool_request(name: str, risk: str) -> dict[str, object]:
    return {
        "name": name,
        "arguments": {"workspace": "kelvin-assistant"},
        "reason": "Complete the requested task.",
        "expected_effect": "Apply the registered operation.",
        "risk": risk,
    }


def _tool_service() -> AgentService:
    definitions = (
        ToolDefinition(
            name="git.status",
            description="Show repository state.",
            input_schema={"type": "object"},
            risk=ToolRisk.READ,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
        ),
        ToolDefinition(
            name="file.patch",
            description="Apply a file patch.",
            input_schema={"type": "object"},
            risk=ToolRisk.WRITE,
            execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
        ),
    )
    return AgentService(DefaultToolPolicy(StaticToolRegistry(definitions)))


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


class StubAgentPlanner:
    """Return queued structured decisions or one stable planner error."""

    def __init__(
        self,
        *decisions: PlannerDecision,
        error: AgentPlannerResponseError | None = None,
    ) -> None:
        self._decisions = list(decisions)
        self._error = error
        self.requests: list[PlannerRequest] = []

    async def plan(self, request: PlannerRequest) -> PlannerDecision:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._decisions.pop(0)


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
