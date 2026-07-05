"""Unit tests for structured planner application orchestration."""

import asyncio

import pytest

from kelvin_assistant.application.agent import AgentService
from kelvin_assistant.application.agent_planning import (
    AgentPlanningError,
    AgentPlanningService,
    ClarificationOutcome,
    CompletionOutcome,
    ToolArgumentsValidationError,
    ToolOutcome,
)
from kelvin_assistant.application.tool_policy import (
    DefaultToolPolicy,
    ToolPolicyContext,
)
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ToolDefinition,
    ToolExecutionTarget,
    ToolPolicyDecision,
    ToolRisk,
)
from kelvin_assistant.domain.context_guard import ContextGuard, GuardedContent
from kelvin_assistant.domain.planner import (
    ClarifyDecision,
    CompleteDecision,
    PlannerDecision,
    PlannerRequest,
    ToolDecision,
)
from kelvin_assistant.tools.registry import StaticToolRegistry


class StubContextGuard(ContextGuard):
    def __init__(self) -> None:
        pass

    def wrap(self, text: str, source: str = "unknown") -> GuardedContent:
        return GuardedContent(text=f"wrapped: {text}", is_safe=True, warnings=[])


def test_prepare_run_enters_planning_from_received() -> None:
    """A persisted received run advances before the model is called."""

    service, _ = _service(CompleteDecision("Done."))
    received = AgentRun.create(
        "Inspect the repository.",
        workspace_id="kelvin-assistant",
    )

    planned = service.prepare_run(received)

    assert planned.status is AgentStatus.PLANNING
    assert planned.version == received.version + 1


def test_prepare_run_continues_after_observation() -> None:
    """A prior tool result can feed another bounded planning step."""

    service, _ = _service(CompleteDecision("Done."))
    received = AgentRun.create("Inspect the repository.")
    planning = received.transition_to(AgentStatus.PLANNING)
    executing = planning.transition_to(AgentStatus.EXECUTING)
    observing = executing.transition_to(AgentStatus.OBSERVING)

    next_planning = service.prepare_run(observing)

    assert next_planning.status is AgentStatus.PLANNING
    assert next_planning.step_count == 1


def test_plan_next_returns_targeted_clarification() -> None:
    """A clarify decision pauses the planning run without executing tools."""

    decision = ClarifyDecision(
        question="Which file should be changed?",
        reason="The target file is missing.",
    )
    service, planner = _service(decision)
    planned = _planned_run()

    outcome = asyncio.run(
        service.plan_next(
            planned,
            policy_context=_context(),
        )
    )

    assert isinstance(outcome, ClarificationOutcome)
    assert outcome.clarification.run.status is AgentStatus.CLARIFYING
    assert outcome.clarification.request.question == decision.question
    assert planner.request is not None
    assert planner.request.remaining_steps == 12


def test_plan_next_derives_tool_risk_from_registry() -> None:
    """The model chooses a name and arguments, while registry supplies risk."""

    decision = ToolDecision(
        tool_name="file.patch",
        arguments={
            "path": "README.md",
            "old_text": "old",
            "new_text": "new",
        },
        reason="Update one documented value.",
        expected_effect="The approved text changes.",
    )
    service, _ = _service(decision)

    outcome = asyncio.run(
        service.plan_next(
            _planned_run(),
            policy_context=_context(),
        )
    )

    assert isinstance(outcome, ToolOutcome)
    assert outcome.proposal.call.risk is ToolRisk.WRITE
    assert (
        outcome.proposal.policy_result.decision is ToolPolicyDecision.REQUIRE_APPROVAL
    )
    assert outcome.proposal.run.status is AgentStatus.AWAITING_APPROVAL


def test_plan_next_rejects_invalid_tool_arguments() -> None:
    """Model arguments must satisfy the registered schema before policy."""

    decision = ToolDecision(
        tool_name="git.status",
        arguments={"include_untracked": "yes"},
        reason="Inspect repository state.",
        expected_effect="No workspace change.",
    )
    service, _ = _service(decision)

    with pytest.raises(
        ToolArgumentsValidationError,
        match="must be boolean",
    ):
        asyncio.run(
            service.plan_next(
                _planned_run(),
                policy_context=_context(),
            )
        )


def test_plan_next_rejects_unknown_tool_from_untrusted_planner() -> None:
    """A custom or compromised planner cannot bypass the registry."""

    decision = ToolDecision(
        tool_name="powershell.run",
        arguments={},
        reason="Run an arbitrary command.",
        expected_effect="Unknown.",
    )
    service, _ = _service(decision)

    with pytest.raises(AgentPlanningError, match="unknown tool"):
        asyncio.run(
            service.plan_next(
                _planned_run(),
                policy_context=_context(),
            )
        )


def test_plan_next_completes_without_tool() -> None:
    """A complete decision uses the guarded domain transition."""

    service, _ = _service(CompleteDecision(summary="No further action is required."))

    outcome = asyncio.run(
        service.plan_next(
            _planned_run(),
            policy_context=_context(),
        )
    )

    assert isinstance(outcome, CompletionOutcome)
    assert outcome.run.status is AgentStatus.COMPLETED
    assert outcome.decision.summary == "No further action is required."


def test_fail_run_uses_guarded_failure_transition() -> None:
    """Planner errors can persist a terminal failed state."""

    service, _ = _service(CompleteDecision("Done."))

    failed = service.fail_run(_planned_run())

    assert failed.status is AgentStatus.FAILED


def test_plan_next_rejects_exhausted_execution_budget() -> None:
    """The model is not called after the maximum execution step."""

    service, planner = _service(CompleteDecision("Done."))
    exhausted = AgentRun(
        id=AgentRun.create("Inspect.").id,
        goal="Inspect.",
        status=AgentStatus.PLANNING,
        step_count=1,
        max_steps=1,
        version=3,
    )

    with pytest.raises(AgentPlanningError, match="no remaining"):
        asyncio.run(
            service.plan_next(
                exhausted,
                policy_context=_context(),
            )
        )

    assert planner.request is None


def _service(
    decision: PlannerDecision,
) -> tuple[AgentPlanningService, "StubPlanner"]:
    registry = StaticToolRegistry(
        (
            ToolDefinition(
                name="git.status",
                description="Show concise Git status.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "include_untracked": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                risk=ToolRisk.READ,
                execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            ),
            ToolDefinition(
                name="file.patch",
                description="Replace one exact string.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_text": {"type": "string"},
                        "new_text": {"type": "string"},
                    },
                    "required": ("path", "old_text", "new_text"),
                    "additionalProperties": False,
                },
                risk=ToolRisk.WRITE,
                execution_target=ToolExecutionTarget.WINDOWS_CLIENT,
            ),
        )
    )
    planner = StubPlanner(decision)
    agent_service = AgentService(DefaultToolPolicy(registry))
    return (
        AgentPlanningService(
            planner=planner,
            registry=registry,
            agent_service=agent_service,
            context_guard=StubContextGuard(),
        ),
        planner,
    )


def _planned_run() -> AgentRun:
    return AgentRun.create(
        "Inspect the repository.",
        workspace_id="kelvin-assistant",
    ).transition_to(AgentStatus.PLANNING)


def _context() -> ToolPolicyContext:
    return ToolPolicyContext(
        workspace_authorized=True,
        workspace_id="kelvin-assistant",
    )


class StubPlanner:
    """Return one deterministic decision and capture its bounded request."""

    def __init__(self, decision: PlannerDecision) -> None:
        self._decision = decision
        self.request: PlannerRequest | None = None

    async def plan(self, request: PlannerRequest) -> PlannerDecision:
        self.request = request
        return self._decision
