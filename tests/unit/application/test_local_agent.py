"""Unit tests for local read-only agent orchestration."""

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from uuid import UUID

import pytest

from kelvin_assistant.application.local_agent import (
    LocalAgentClientError,
    LocalClarificationResult,
    LocalCompletionResult,
    LocalReadToolClient,
    ToolApprovalRejectedError,
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
from kelvin_assistant.domain.planner import ClarificationTurn
from kelvin_assistant.ports.agent_client import (
    AgentClarificationStep,
    AgentCompletionStep,
    AgentNextStep,
    AgentToolStep,
)
from kelvin_assistant.ports.tools import ToolPreview

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
        self.goal = ""
        self.cancelled = False
        self.plan_contexts: list[tuple[tuple[ClarificationTurn, ...], str | None]] = []

    async def create_run(self, *, goal: str, workspace_id: str) -> AgentRun:
        assert workspace_id == "kelvin-assistant"
        self.goal = goal
        return _run(AgentStatus.RECEIVED, workspace_id=self.workspace_id)

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        assert run_id == RUN_ID
        return _run(
            AgentStatus.PLANNING,
            workspace_id=self.workspace_id,
            version=1,
        )

    async def cancel_run(self, run_id: UUID) -> AgentRun:
        assert run_id == RUN_ID
        self.cancelled = True
        return _run(
            AgentStatus.CANCELLED,
            workspace_id=self.workspace_id,
            version=4,
        )

    async def plan_next(
        self,
        run_id: UUID,
        *,
        clarifications: Sequence[ClarificationTurn] = (),
        observation: str | None = None,
    ) -> AgentNextStep:
        assert run_id == RUN_ID
        self.plan_contexts.append((tuple(clarifications), observation))
        if self.submitted_result is not None:
            return AgentCompletionStep(
                run=_run(
                    AgentStatus.COMPLETED,
                    workspace_id=self.workspace_id,
                    version=4,
                ),
                summary="Repository status inspected.",
            )
        proposal = await self.propose_tool(
            run_id,
            name="git.status",
            arguments={"include_untracked": True},
            reason="Inspect the repository.",
            expected_effect="Read Git state.",
            risk=ToolRisk.READ,
        )
        return AgentToolStep(proposal=proposal)

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
        risk: ToolRisk,
    ) -> ToolProposal:
        assert run_id == RUN_ID
        assert name == "git.status"
        assert arguments == {"include_untracked": True}
        assert reason
        assert expected_effect
        assert risk is ToolRisk.READ
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

    async def resolve_approval(
        self,
        run_id: UUID,
        *,
        tool_call_id: UUID,
        approved: bool,
    ) -> ToolProposal:
        raise AssertionError("Read tool must not request approval")

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


class FakeWriteAgentApiClient:
    """Model an approval-gated backend proposal for one file patch."""

    def __init__(self) -> None:
        self.proposal: ToolProposal | None = None
        self.approved: bool | None = None
        self.submitted_result: ToolExecutionResult | None = None

    async def create_run(self, *, goal: str, workspace_id: str) -> AgentRun:
        assert goal == "Execute tool file.patch."
        return _run(AgentStatus.RECEIVED)

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        return _run(AgentStatus.PLANNING, version=1)

    async def cancel_run(self, run_id: UUID) -> AgentRun:
        return _run(AgentStatus.CANCELLED, version=4)

    async def plan_next(
        self,
        run_id: UUID,
        **kwargs: object,
    ) -> AgentToolStep:
        raise AssertionError("Manual write test must not call the planner")

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
        risk: ToolRisk,
    ) -> ToolProposal:
        assert risk is ToolRisk.WRITE
        self.proposal = ToolProposal(
            run=_run(AgentStatus.AWAITING_APPROVAL, version=2),
            call=ToolCall(
                id=CALL_ID,
                name=name,
                arguments=arguments,
                reason=reason,
                expected_effect=expected_effect,
                risk=risk,
            ),
            policy_result=ToolPolicyResult(
                decision=ToolPolicyDecision.REQUIRE_APPROVAL,
                reason="State-changing tools require explicit user approval.",
            ),
        )
        return self.proposal

    async def resolve_approval(
        self,
        run_id: UUID,
        *,
        tool_call_id: UUID,
        approved: bool,
    ) -> ToolProposal:
        assert self.proposal is not None
        assert tool_call_id == self.proposal.call.id
        self.approved = approved
        return ToolProposal(
            run=_run(
                AgentStatus.EXECUTING if approved else AgentStatus.CANCELLED,
                version=3,
            ),
            call=self.proposal.call,
            policy_result=self.proposal.policy_result,
        )

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        self.submitted_result = result
        return _run(AgentStatus.OBSERVING, version=4)


class FakePatchExecutor:
    """Expose a complete preview before recording fake file execution."""

    definition = ToolDefinition(
        name="file.patch",
        description="Replace one exact string.",
        input_schema={"type": "object"},
        risk=ToolRisk.WRITE,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )

    def __init__(self) -> None:
        self.previewed = False
        self.executed = False

    async def preview(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolPreview:
        self.previewed = True
        return ToolPreview(content="--- a/notes.txt\n+++ b/notes.txt\n-old\n+new\n")

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        self.executed = True
        return ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            succeeded=True,
            output="Updated notes.txt",
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


def test_client_runs_model_selected_tool_from_natural_language() -> None:
    """A natural-language goal can select an allowed local read executor."""

    api_client = FakeAgentApiClient()
    executor = FakeToolExecutor()
    client = LocalReadToolClient(
        api_client=api_client,
        executors={"git.status": executor},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
    )

    result = asyncio.run(client.run_goal("Show the current Git status."))

    assert api_client.goal == "Show the current Git status."
    assert isinstance(result, LocalCompletionResult)
    assert result.summary == "Repository status inspected."
    assert result.executions[0].output == "## main...origin/main"
    assert api_client.plan_contexts == [
        ((), None),
        (
            (),
            "Tool git.status succeeded.\n## main...origin/main",
        ),
    ]


@pytest.mark.parametrize(
    ("step", "expected_type"),
    [
        (
            AgentClarificationStep(
                run=_run(AgentStatus.CLARIFYING, version=1),
                question="Which file should I inspect?",
                reason="The target is missing.",
            ),
            LocalClarificationResult,
        ),
        (
            AgentCompletionStep(
                run=_run(AgentStatus.COMPLETED, version=1),
                summary="No local tool is required.",
            ),
            LocalCompletionResult,
        ),
    ],
)
def test_client_returns_non_tool_planner_decision(
    step: AgentClarificationStep | AgentCompletionStep,
    expected_type: type[object],
) -> None:
    """Clarification and completion never start a local executable."""

    class NonToolApiClient(FakeAgentApiClient):
        async def plan_next(
            self,
            run_id: UUID,
            *,
            clarifications: Sequence[ClarificationTurn] = (),
            observation: str | None = None,
        ) -> AgentClarificationStep | AgentCompletionStep:
            return step

    client = LocalReadToolClient(
        api_client=NonToolApiClient(),
        executors={"git.status": FakeToolExecutor()},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
    )

    result = asyncio.run(client.run_goal("Help with the repository."))

    assert isinstance(result, expected_type)


def test_client_answers_clarification_and_continues_to_completion() -> None:
    """One targeted answer is carried into the next bounded planner request."""

    class ClarifyingApiClient(FakeAgentApiClient):
        async def plan_next(
            self,
            run_id: UUID,
            *,
            clarifications: Sequence[ClarificationTurn] = (),
            observation: str | None = None,
        ) -> AgentNextStep:
            if not clarifications:
                return AgentClarificationStep(
                    run=_run(AgentStatus.CLARIFYING, version=1),
                    question="Which file should I inspect?",
                    reason="The target file is missing.",
                )
            assert tuple(clarifications) == (
                ClarificationTurn(
                    question="Which file should I inspect?",
                    answer="README.md",
                ),
            )
            return AgentCompletionStep(
                run=_run(AgentStatus.COMPLETED, version=2),
                summary="README.md selected.",
            )

    client = LocalReadToolClient(
        api_client=ClarifyingApiClient(),
        executors={},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
        clarification_handler=lambda question: "README.md",
    )

    result = asyncio.run(client.run_goal("Inspect a documentation file."))

    assert isinstance(result, LocalCompletionResult)
    assert result.summary == "README.md selected."


def test_client_rejects_empty_clarification_answer() -> None:
    """Whitespace cannot be submitted as meaningful planner context."""

    class ClarifyingApiClient(FakeAgentApiClient):
        async def plan_next(
            self,
            run_id: UUID,
            *,
            clarifications: Sequence[ClarificationTurn] = (),
            observation: str | None = None,
        ) -> AgentNextStep:
            return AgentClarificationStep(
                run=_run(AgentStatus.CLARIFYING, version=1),
                question="Which file should I inspect?",
                reason="The target file is missing.",
            )

    client = LocalReadToolClient(
        api_client=ClarifyingApiClient(),
        executors={},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
        clarification_handler=lambda question: " ",
    )

    with pytest.raises(
        LocalAgentClientError,
        match="answer cannot be empty",
    ):
        asyncio.run(client.run_goal("Inspect a documentation file."))


def test_client_cancels_remote_run_after_keyboard_interrupt() -> None:
    """An interrupted local prompt does not leave an active backend run."""

    class ClarifyingApiClient(FakeAgentApiClient):
        async def plan_next(
            self,
            run_id: UUID,
            *,
            clarifications: Sequence[ClarificationTurn] = (),
            observation: str | None = None,
        ) -> AgentNextStep:
            return AgentClarificationStep(
                run=_run(AgentStatus.CLARIFYING, version=1),
                question="Which file should I inspect?",
                reason="The target file is missing.",
            )

    def interrupt(question: str) -> str:
        raise KeyboardInterrupt

    api_client = ClarifyingApiClient()
    client = LocalReadToolClient(
        api_client=api_client,
        executors={},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
        clarification_handler=interrupt,
    )

    with pytest.raises(KeyboardInterrupt):
        asyncio.run(client.run_goal("Inspect a documentation file."))

    assert api_client.cancelled


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


def test_client_previews_approved_write_before_execution() -> None:
    """A write executes only after its complete preview is explicitly approved."""

    api_client = FakeWriteAgentApiClient()
    executor = FakePatchExecutor()
    shown_previews: list[str] = []

    def approve(preview: str) -> bool:
        shown_previews.append(preview)
        return True

    client = LocalReadToolClient(
        api_client=api_client,
        executors={"file.patch": executor},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
        approval_handler=approve,
    )

    result = asyncio.run(
        client.run_tool(
            "file.patch",
            {
                "path": "notes.txt",
                "old_text": "old",
                "new_text": "new",
            },
        )
    )

    assert shown_previews == ["--- a/notes.txt\n+++ b/notes.txt\n-old\n+new\n"]
    assert api_client.approved is True
    assert executor.previewed
    assert executor.executed
    assert result.execution.output == "Updated notes.txt"


def test_client_cancels_rejected_write_without_execution() -> None:
    """A negative response is persisted and never invokes the write executor."""

    api_client = FakeWriteAgentApiClient()
    executor = FakePatchExecutor()
    client = LocalReadToolClient(
        api_client=api_client,
        executors={"file.patch": executor},
        workspace_id="kelvin-assistant",
        workspace_root=Path.cwd(),
        approval_handler=lambda preview: False,
    )

    with pytest.raises(ToolApprovalRejectedError, match="rejected"):
        asyncio.run(
            client.run_tool(
                "file.patch",
                {
                    "path": "notes.txt",
                    "old_text": "old",
                    "new_text": "new",
                },
            )
        )

    assert api_client.approved is False
    assert executor.previewed
    assert not executor.executed
    assert api_client.submitted_result is None
