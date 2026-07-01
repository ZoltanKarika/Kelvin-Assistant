"""Unit tests for provider-independent planner domain models."""

from types import MappingProxyType

import pytest

from kelvin_assistant.domain.agent import (
    ToolDefinition,
    ToolExecutionTarget,
    ToolRisk,
)
from kelvin_assistant.domain.planner import (
    MAX_CLARIFICATION_TURNS,
    ClarificationTurn,
    ClarifyDecision,
    CompleteDecision,
    PlannerAction,
    PlannerDomainError,
    PlannerRequest,
    ToolDecision,
)


def test_request_freezes_tools_and_normalizes_context() -> None:
    """Planner input cannot change through caller-owned mutable sequences."""

    tools = [_tool("git.status")]
    request = PlannerRequest.create(
        "  Inspect the repository.  ",
        tools,
        remaining_steps=3,
        clarifications=[
            ClarificationTurn(
                question=" Which repository? ",
                answer=" The current workspace. ",
            )
        ],
        observation="  ## main  ",
    )
    tools.append(_tool("git.diff"))

    assert request.goal == "Inspect the repository."
    assert [tool.name for tool in request.tools] == ["git.status"]
    assert request.clarifications[0].question == "Which repository?"
    assert request.clarifications[0].answer == "The current workspace."
    assert request.observation == "## main"


def test_request_requires_registered_tools() -> None:
    """A planner cannot invent actions without a supplied registry view."""

    with pytest.raises(PlannerDomainError, match="at least one"):
        PlannerRequest.create(
            "Inspect the repository.",
            (),
            remaining_steps=1,
        )


def test_request_rejects_duplicate_tool_names() -> None:
    """Ambiguous duplicate definitions fail before reaching the model."""

    with pytest.raises(PlannerDomainError, match="unique"):
        PlannerRequest.create(
            "Inspect the repository.",
            (_tool("git.status"), _tool("git.status")),
            remaining_steps=1,
        )


def test_request_rejects_exhausted_step_budget() -> None:
    """The planner is not called once no execution step remains."""

    with pytest.raises(PlannerDomainError, match="remaining steps"):
        PlannerRequest.create(
            "Inspect the repository.",
            (_tool("git.status"),),
            remaining_steps=0,
        )


def test_request_limits_clarification_history() -> None:
    """Unbounded conversation history cannot inflate planner context."""

    turns = tuple(
        ClarificationTurn(question=f"Question {index}?", answer="Answer.")
        for index in range(MAX_CLARIFICATION_TURNS + 1)
    )

    with pytest.raises(PlannerDomainError, match="clarification turns"):
        PlannerRequest.create(
            "Inspect the repository.",
            (_tool("git.status"),),
            remaining_steps=1,
            clarifications=turns,
        )


def test_blank_observation_is_removed() -> None:
    """Whitespace-only observations are not sent to the provider."""

    request = PlannerRequest.create(
        "Inspect the repository.",
        (_tool("git.status"),),
        remaining_steps=1,
        observation="   ",
    )

    assert request.observation is None


def test_clarify_decision_normalizes_required_text() -> None:
    """A clarification contains one targeted question and its reason."""

    decision = ClarifyDecision(
        question=" Which file? ",
        reason=" The target is missing. ",
    )

    assert decision.action is PlannerAction.CLARIFY
    assert decision.question == "Which file?"
    assert decision.reason == "The target is missing."


def test_tool_decision_freezes_nested_arguments() -> None:
    """Structured tool arguments are immutable after validation."""

    decision = ToolDecision(
        tool_name=" git.status ",
        arguments={
            "include_untracked": True,
            "options": {"paths": ("backend", "tests")},
        },
        reason="Inspect repository state.",
        expected_effect="No workspace change.",
    )

    assert decision.action is PlannerAction.TOOL
    assert decision.tool_name == "git.status"
    assert isinstance(decision.arguments, MappingProxyType)
    assert isinstance(decision.arguments["options"], MappingProxyType)


def test_tool_decision_rejects_non_namespaced_name() -> None:
    """Planner output must use the same stable tool naming convention."""

    with pytest.raises(PlannerDomainError, match="namespace"):
        ToolDecision(
            tool_name="status",
            arguments={},
            reason="Inspect state.",
            expected_effect="No change.",
        )


def test_tool_decision_rejects_blank_argument_key() -> None:
    """Malformed argument objects fail before registry validation."""

    with pytest.raises(PlannerDomainError, match="keys"):
        ToolDecision(
            tool_name="git.status",
            arguments={" ": True},
            reason="Inspect state.",
            expected_effect="No change.",
        )


def test_complete_decision_requires_summary() -> None:
    """Completion cannot silently return an empty user-facing result."""

    with pytest.raises(PlannerDomainError, match="summary"):
        CompleteDecision(summary=" ")


def test_decision_types_have_stable_discriminators() -> None:
    """API adapters can serialize the union through a stable action field."""

    assert ClarifyDecision("Question?", "Reason.").action == "clarify"
    assert (
        ToolDecision(
            "git.status",
            {},
            "Inspect state.",
            "No change.",
        ).action
        == "tool"
    )
    assert CompleteDecision("Finished.").action == "complete"


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"Execute {name}.",
        input_schema={"type": "object"},
        risk=ToolRisk.READ,
        execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
    )
