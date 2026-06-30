"""Unit tests for agent domain models and lifecycle rules."""

from datetime import UTC, datetime
from types import MappingProxyType
from uuid import uuid4

import pytest

from kelvin_assistant.domain.agent import (
    MAX_AGENT_GOAL_LENGTH,
    AgentDomainError,
    AgentRun,
    AgentStatus,
    AgentStepLimitError,
    ApprovalDecision,
    ClarificationRequest,
    InvalidAgentTransitionError,
    ToolApproval,
    ToolCall,
    ToolExecutionResult,
    ToolRisk,
)


def test_agent_run_create_normalizes_goal() -> None:
    """A new run starts in the received state with a normalized goal."""

    run = AgentRun.create("  Inspect the repository status.  ")

    assert run.goal == "Inspect the repository status."
    assert run.status is AgentStatus.RECEIVED
    assert run.step_count == 0
    assert run.max_steps == 12
    assert run.version == 0
    assert run.status.is_terminal is False


def test_agent_run_normalizes_workspace_identifier() -> None:
    """A run stores an opaque normalized workspace ID, never a host path."""

    run = AgentRun.create(
        "Inspect the project",
        workspace_id=" kelvin-assistant ",
    )

    assert run.workspace_id == "kelvin-assistant"

    with pytest.raises(AgentDomainError, match="Workspace ID"):
        AgentRun.create("Inspect the project", workspace_id="Kelvin Project")


@pytest.mark.parametrize(
    ("goal", "max_steps"),
    [
        ("", 12),
        ("x" * (MAX_AGENT_GOAL_LENGTH + 1), 12),
        ("Inspect the repository", 0),
        ("Inspect the repository", 101),
    ],
)
def test_agent_run_rejects_invalid_creation_values(
    goal: str,
    max_steps: int,
) -> None:
    """A run requires a goal and a bounded positive step limit."""

    with pytest.raises(AgentDomainError):
        AgentRun.create(goal, max_steps=max_steps)


def test_agent_run_follows_read_only_execution_lifecycle() -> None:
    """A read-only plan can execute without an approval state."""

    received = AgentRun.create("Show Git status")
    planning = received.transition_to(AgentStatus.PLANNING)
    executing = planning.transition_to(AgentStatus.EXECUTING)
    observing = executing.transition_to(AgentStatus.OBSERVING)
    completed = observing.transition_to(AgentStatus.COMPLETED)

    assert received.status is AgentStatus.RECEIVED
    assert planning.status is AgentStatus.PLANNING
    assert executing.status is AgentStatus.EXECUTING
    assert executing.step_count == 1
    assert executing.version == 2
    assert observing.status is AgentStatus.OBSERVING
    assert completed.status is AgentStatus.COMPLETED
    assert completed.version == 4
    assert completed.status.is_terminal is True


def test_agent_run_follows_approval_lifecycle() -> None:
    """A modifying plan can wait for approval before execution."""

    run = AgentRun.create("Format the Python files")
    run = run.transition_to(AgentStatus.PLANNING)
    run = run.transition_to(AgentStatus.AWAITING_APPROVAL)
    run = run.transition_to(AgentStatus.EXECUTING)

    assert run.status is AgentStatus.EXECUTING
    assert run.step_count == 1


@pytest.mark.parametrize(
    ("current", "next_status"),
    [
        (AgentStatus.RECEIVED, AgentStatus.EXECUTING),
        (AgentStatus.CLARIFYING, AgentStatus.COMPLETED),
        (AgentStatus.AWAITING_APPROVAL, AgentStatus.COMPLETED),
        (AgentStatus.EXECUTING, AgentStatus.COMPLETED),
        (AgentStatus.COMPLETED, AgentStatus.PLANNING),
        (AgentStatus.CANCELLED, AgentStatus.PLANNING),
        (AgentStatus.FAILED, AgentStatus.PLANNING),
    ],
)
def test_agent_run_rejects_invalid_transitions(
    current: AgentStatus,
    next_status: AgentStatus,
) -> None:
    """Unsupported transitions cannot bypass lifecycle safeguards."""

    run = AgentRun(
        id=uuid4(),
        goal="Test transition",
        status=current,
    )

    with pytest.raises(InvalidAgentTransitionError):
        run.transition_to(next_status)


def test_agent_run_enforces_execution_step_limit() -> None:
    """A run cannot start another execution after reaching its limit."""

    run = AgentRun.create("Perform bounded work", max_steps=1)
    run = run.transition_to(AgentStatus.PLANNING)
    run = run.transition_to(AgentStatus.EXECUTING)
    run = run.transition_to(AgentStatus.OBSERVING)
    run = run.transition_to(AgentStatus.PLANNING)

    with pytest.raises(AgentStepLimitError, match="step limit"):
        run.transition_to(AgentStatus.EXECUTING)


def test_tool_call_normalizes_and_freezes_arguments() -> None:
    """Tool calls expose immutable structured arguments."""

    call = ToolCall(
        name=" git.status ",
        arguments={
            " workspace ": "C:\\project",
            "options": {"include_untracked": True},
            "patterns": ("*.py", "*.md"),
        },
        reason="  Inspect repository state.  ",
        expected_effect="  No state change.  ",
        risk=ToolRisk.READ,
    )

    assert call.name == "git.status"
    assert call.reason == "Inspect repository state."
    assert call.expected_effect == "No state change."
    assert call.arguments["workspace"] == "C:\\project"
    assert isinstance(call.arguments, MappingProxyType)
    assert isinstance(call.arguments["options"], MappingProxyType)

    with pytest.raises(TypeError):
        call.arguments["workspace"] = "C:\\other"  # type: ignore[index]


@pytest.mark.parametrize(
    "name",
    ["", "status", "Git.status", "git status", "git.STATUS"],
)
def test_tool_call_rejects_invalid_names(name: str) -> None:
    """Tool names require a stable lowercase namespace and operation."""

    with pytest.raises(AgentDomainError, match="Tool name"):
        ToolCall(
            name=name,
            arguments={},
            reason="Inspect state",
            expected_effect="No state change",
            risk=ToolRisk.READ,
        )


def test_tool_risk_identifies_approval_requirement() -> None:
    """Only read operations can proceed without user approval."""

    assert ToolRisk.READ.requires_approval is False
    assert ToolRisk.WRITE.requires_approval is True
    assert ToolRisk.DESTRUCTIVE.requires_approval is True
    assert ToolRisk.PRIVILEGED.requires_approval is True


def test_clarification_request_normalizes_required_text() -> None:
    """Clarification requests contain a focused question and reason."""

    clarification = ClarificationRequest(
        question="  Which project should I inspect?  ",
        reason="  No workspace was provided.  ",
    )

    assert clarification.question == "Which project should I inspect?"
    assert clarification.reason == "No workspace was provided."

    with pytest.raises(AgentDomainError, match="question"):
        ClarificationRequest(question="", reason="Missing workspace")


def test_tool_approval_validates_decision_metadata() -> None:
    """Only completed decisions contain author and timestamp metadata."""

    call_id = uuid4()
    pending = ToolApproval(tool_call_id=call_id)
    approved = ToolApproval(
        tool_call_id=call_id,
        decision=ApprovalDecision.APPROVED,
        decided_by=" zoltan ",
        decided_at=datetime.now(UTC),
    )

    assert pending.decision is ApprovalDecision.PENDING
    assert approved.decided_by == "zoltan"

    with pytest.raises(AgentDomainError, match="requires"):
        ToolApproval(
            tool_call_id=call_id,
            decision=ApprovalDecision.REJECTED,
        )


def test_tool_execution_result_rejects_inconsistent_success() -> None:
    """A successful result cannot simultaneously contain an error."""

    with pytest.raises(AgentDomainError, match="Successful"):
        ToolExecutionResult(
            tool_call_id=uuid4(),
            tool_name="git.status",
            succeeded=True,
            error="unexpected",
        )
