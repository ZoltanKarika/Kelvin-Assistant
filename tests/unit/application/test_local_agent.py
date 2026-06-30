"""Unit tests for local read-only agent orchestration."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import pytest

from kelvin_assistant.application.local_agent import (
    LocalAgentClientError,
    LocalReadToolClient,
)
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    JsonValue,
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutionTarget,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)

RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
CALL_ID = UUID("22222222-2222-4222-8222-222222222222")


def _run(
    status: AgentStatus,
    *,
    workspace_id: str = "kelvin-assistant",
    version: int = 0,
) -> AgentRun:
    return AgentRun(
        id=RUN_ID,
        goal="Execute read-only tool git.status.",
        status=status,
        step_count=1 if status in {AgentStatus.EXECUTING, AgentStatus.OBSERVING} else 0,
        version=version,
        workspace_id=workspace_id,
    )


class FakeAgentApiClient:
    """Return deterministic remote states and record the submitted result."""

    def __init__(
        self,
        *,
        decision: ToolPolicyDecision = ToolPolicyDecision.ALLOW,
        workspace_id: str = "kelvin-assistant",
    ) -> None:
        self.decision = decision
        self.workspace_id = workspace_id
        self.submitted_result: ToolExecutionResult | None = None

    async def create_run(self, *, goal: str, workspace_id: str) -> AgentRun:
        assert goal == "Execute read-only tool git.status."
        assert workspace_id == "kelvin-assistant"
        return _run(AgentStatus.RECEIVED, workspace_id=self.workspace_id)

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        assert run_id == RUN_ID
        return _run(
            AgentStatus.PLANNING,
            workspace_id=self.workspace_id,
            version=1,
        )

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
    ) -> ToolProposal:
        assert run_id == RUN_ID
        assert name == "git.status"
        assert arguments == {"include_untracked": True}
        assert reason
        assert expected_effect
        proposal_status = (
            AgentStatus.EXECUTING
            if self.decision is ToolPolicyDecision.ALLOW
            else AgentStatus.PLANNING
        )
        return ToolProposal(
            run=_run(
                proposal_status,
                workspace_id=self.workspace_id,
                version=2,
            ),
            call=ToolCall(
                id=CALL_ID,
                name=name,
                arguments=arguments,
                reason=reason,
                expected_effect=expected_effect,
                risk=ToolRisk.READ,
            ),
            policy_result=ToolPolicyResult(
                decision=self.decision,
                reason="Read-only tool is allowed.",
            ),
        )

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        assert run_id == RUN_ID
        self.submitted_result = result
        return _run(
            AgentStatus.OBSERVING if result.succeeded else AgentStatus.FAILED,
            workspace_id=self.workspace_id,
            version=3,
        )


class FakeToolExecutor:
    """Return a successful result without starting a real local process."""

    definition = ToolDefinition(
        name="git.status",
        description="Read concise Git status.",
        input_schema={"type": "object"},
        risk=ToolRisk.READ,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )

    def __init__(self) -> None:
        self.workspace_root: Path | None = None

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        self.workspace_root = workspace_root
        return ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            succeeded=True,
            output="## main...origin/main",
            duration_ms=4,
        )


def test_client_runs_allowed_tool_and_submits_result() -> None:
    """An allowed proposal executes locally and returns to the remote run."""

    workspace_root = Path.cwd()
    api_client = FakeAgentApiClient()
    executor = FakeToolExecutor()
    client = LocalReadToolClient(
        api_client=api_client,
        executors={"git.status": executor},
        workspace_id="kelvin-assistant",
        workspace_root=workspace_root,
    )

    result = asyncio.run(client.run_tool("git.status", {"include_untracked": True}))

    assert result.run.status is AgentStatus.OBSERVING
    assert result.execution.output == "## main...origin/main"
    assert executor.workspace_root == workspace_root
    assert api_client.submitted_result == result.execution


def test_client_rejects_remote_workspace_mismatch() -> None:
    """The VM cannot silently redirect execution to another workspace ID."""

    client = LocalReadToolClient(
        api_client=FakeAgentApiClient(workspace_id="other-project"),
        executors={"git.status": FakeToolExecutor()},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
    )

    with pytest.raises(
        LocalAgentClientError,
        match="different workspace",
    ):
        asyncio.run(client.run_tool("git.status", {"include_untracked": True}))


def test_client_does_not_execute_denied_proposal() -> None:
    """The local client obeys the deterministic backend policy decision."""

    executor = FakeToolExecutor()
    client = LocalReadToolClient(
        api_client=FakeAgentApiClient(decision=ToolPolicyDecision.DENY),
        executors={"git.status": executor},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
    )

    with pytest.raises(LocalAgentClientError, match="was not allowed"):
        asyncio.run(client.run_tool("git.status", {"include_untracked": True}))

    assert executor.workspace_root is None


def test_client_rejects_unregistered_local_executor() -> None:
    """Only explicitly registered local executors can be invoked."""

    client = LocalReadToolClient(
        api_client=FakeAgentApiClient(),
        executors={},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
    )

    with pytest.raises(LocalAgentClientError, match="not registered"):
        asyncio.run(client.run_tool("git.status", {}))
