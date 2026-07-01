"""Unit tests for the remote Kelvin agent HTTP adapter."""

import asyncio
import json
from uuid import UUID

import httpx2
import pytest

from kelvin_assistant.adapters.agent_http import HttpAgentApiClient
from kelvin_assistant.domain.agent import (
    AgentStatus,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolRisk,
)
from kelvin_assistant.domain.planner import ClarificationTurn
from kelvin_assistant.ports.agent_client import (
    AgentClarificationStep,
    AgentClientResponseError,
    AgentClientUnavailableError,
    AgentCompletionStep,
    AgentToolStep,
)

RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
CALL_ID = UUID("22222222-2222-4222-8222-222222222222")


def _run_payload(status: str, version: int) -> dict[str, object]:
    return {
        "id": str(RUN_ID),
        "goal": "Execute read-only tool git.status.",
        "status": status,
        "step_count": 1 if status in {"executing", "observing"} else 0,
        "max_steps": 12,
        "version": version,
        "workspace_id": "kelvin-assistant",
    }


def test_client_completes_remote_read_tool_lifecycle() -> None:
    """The adapter maps all client lifecycle calls to versioned API requests."""

    requests: list[tuple[str, str, object]] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        path = request.url.path
        if path == "/api/v1/agent/runs":
            return httpx2.Response(201, json=_run_payload("received", 0))
        if path.endswith("/plan"):
            return httpx2.Response(200, json=_run_payload("planning", 1))
        if path.endswith("/tools"):
            return httpx2.Response(
                200,
                json={
                    "run": _run_payload("executing", 2),
                    "tool_call_id": str(CALL_ID),
                    "tool_name": "git.status",
                    "arguments": {"include_untracked": True},
                    "reason": "Inspect the local repository.",
                    "expected_effect": "Read Git state.",
                    "risk": "read",
                    "policy_decision": "allow",
                    "policy_reason": "Read-only tool is allowed.",
                    "approval_status": None,
                },
            )
        if path.endswith("/result"):
            return httpx2.Response(
                200,
                json={
                    "run": _run_payload("observing", 3),
                    "tool_call_id": str(CALL_ID),
                    "tool_name": "git.status",
                    "succeeded": True,
                    "output": "## main",
                    "error": None,
                    "truncated": False,
                    "duration_ms": 12,
                },
            )
        raise AssertionError(f"Unexpected request path: {path}")

    client = HttpAgentApiClient(
        "http://kelvin.test:8000/",
        transport=httpx2.MockTransport(handle_request),
    )

    async def exercise_client() -> tuple[AgentStatus, ToolPolicyDecision]:
        created = await client.create_run(
            goal="Execute read-only tool git.status.",
            workspace_id="kelvin-assistant",
        )
        planned = await client.begin_planning(created.id)
        proposal = await client.propose_tool(
            planned.id,
            name="git.status",
            arguments={"include_untracked": True},
            reason="Inspect the local repository.",
            expected_effect="Read Git state.",
            risk=ToolRisk.READ,
        )
        completed = await client.submit_result(
            proposal.run.id,
            ToolExecutionResult(
                tool_call_id=proposal.call.id,
                tool_name=proposal.call.name,
                succeeded=True,
                output="## main",
                duration_ms=12,
            ),
        )
        return completed.status, proposal.policy_result.decision

    status, decision = asyncio.run(exercise_client())

    assert status is AgentStatus.OBSERVING
    assert decision is ToolPolicyDecision.ALLOW
    expected_requests: list[tuple[str, str, object]] = [
        (
            "POST",
            "/api/v1/agent/runs",
            {
                "goal": "Execute read-only tool git.status.",
                "workspace_id": "kelvin-assistant",
            },
        ),
        ("POST", f"/api/v1/agent/runs/{RUN_ID}/plan", None),
        (
            "POST",
            f"/api/v1/agent/runs/{RUN_ID}/tools",
            {
                "name": "git.status",
                "arguments": {"include_untracked": True},
                "reason": "Inspect the local repository.",
                "expected_effect": "Read Git state.",
                "risk": "read",
            },
        ),
        (
            "POST",
            f"/api/v1/agent/runs/{RUN_ID}/result",
            {
                "tool_call_id": str(CALL_ID),
                "succeeded": True,
                "output": "## main",
                "error": None,
                "truncated": False,
                "duration_ms": 12,
            },
        ),
    ]
    assert requests == expected_requests


def test_client_translates_http_rejection() -> None:
    """A backend policy or validation failure becomes a client response error."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            409,
            json={"detail": "Agent run is not planning"},
            request=request,
        )

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(handle_request),
    )

    with pytest.raises(
        AgentClientResponseError,
        match="Agent run is not planning",
    ):
        asyncio.run(client.begin_planning(RUN_ID))


def test_client_cancels_remote_run() -> None:
    """The adapter maps local interruption to the versioned cancel endpoint."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.path == f"/api/v1/agent/runs/{RUN_ID}/cancel"
        assert not request.content
        return httpx2.Response(200, json=_run_payload("cancelled", 2))

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(handle_request),
    )

    cancelled = asyncio.run(client.cancel_run(RUN_ID))

    assert cancelled.status is AgentStatus.CANCELLED


@pytest.mark.parametrize(
    ("response_payload", "expected_type"),
    [
        (
            {
                "action": "clarify",
                "run": _run_payload("clarifying", 1),
                "question": "Which file should I inspect?",
                "reason": "The target file is missing.",
            },
            AgentClarificationStep,
        ),
        (
            {
                "action": "tool",
                "proposal": {
                    "run": _run_payload("executing", 2),
                    "tool_call_id": str(CALL_ID),
                    "tool_name": "git.status",
                    "arguments": {"include_untracked": True},
                    "reason": "Inspect the repository.",
                    "expected_effect": "Read Git state.",
                    "risk": "read",
                    "policy_decision": "allow",
                    "policy_reason": "Read-only tool is allowed.",
                    "approval_status": None,
                },
            },
            AgentToolStep,
        ),
        (
            {
                "action": "complete",
                "run": _run_payload("completed", 1),
                "summary": "No tool is required.",
            },
            AgentCompletionStep,
        ),
    ],
)
def test_client_parses_structured_planner_actions(
    response_payload: dict[str, object],
    expected_type: type[object],
) -> None:
    """Every planner action becomes one explicit client-side result type."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == f"/api/v1/agent/runs/{RUN_ID}/next"
        assert json.loads(request.content) == {
            "clarifications": [
                {
                    "question": "Which file?",
                    "answer": "README.md",
                }
            ],
            "observation": "Previous step succeeded.",
        }
        return httpx2.Response(200, json=response_payload)

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(handle_request),
    )

    step = asyncio.run(
        client.plan_next(
            RUN_ID,
            clarifications=(
                ClarificationTurn(
                    question="Which file?",
                    answer="README.md",
                ),
            ),
            observation="Previous step succeeded.",
        )
    )

    assert isinstance(step, expected_type)


def test_client_rejects_unknown_planner_action() -> None:
    """An unknown action cannot silently cross the client trust boundary."""

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(
            lambda request: httpx2.Response(
                200,
                json={"action": "run_shell"},
            )
        ),
    )

    with pytest.raises(
        AgentClientResponseError,
        match="invalid planner response",
    ):
        asyncio.run(client.plan_next(RUN_ID))


def test_client_submits_explicit_write_approval() -> None:
    """Approval is bound to the exact server-issued tool call identifier."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == f"/api/v1/agent/runs/{RUN_ID}/approval"
        assert json.loads(request.content) == {
            "tool_call_id": str(CALL_ID),
            "decision": "approved",
        }
        return httpx2.Response(
            200,
            json={
                "run": _run_payload("executing", 3),
                "tool_call_id": str(CALL_ID),
                "tool_name": "file.patch",
                "arguments": {
                    "path": "notes.txt",
                    "old_text": "old",
                    "new_text": "new",
                },
                "reason": "Update the documented value.",
                "expected_effect": "Apply the approved workspace change.",
                "risk": "write",
                "policy_decision": "require_approval",
                "policy_reason": "State-changing tools require approval.",
                "approval_status": "approved",
            },
        )

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(handle_request),
    )

    proposal = asyncio.run(
        client.resolve_approval(
            RUN_ID,
            tool_call_id=CALL_ID,
            approved=True,
        )
    )

    assert proposal.run.status is AgentStatus.EXECUTING
    assert proposal.call.name == "file.patch"
    assert proposal.call.risk is ToolRisk.WRITE


def test_client_translates_connection_failure() -> None:
    """An unreachable VM becomes a stable client availability error."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    client = HttpAgentApiClient(
        "http://kelvin.test:8000",
        transport=httpx2.MockTransport(handle_request),
    )

    with pytest.raises(
        AgentClientUnavailableError,
        match="Kelvin agent API is unavailable",
    ):
        asyncio.run(
            client.create_run(
                goal="Inspect the repository.",
                workspace_id="kelvin-assistant",
            )
        )
