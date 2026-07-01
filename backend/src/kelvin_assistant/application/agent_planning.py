"""Application orchestration for one structured planner decision."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from kelvin_assistant.application.agent import (
    AgentClarification,
    AgentService,
)
from kelvin_assistant.application.tool_policy import ToolPolicyContext
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ClarificationRequest,
    JsonValue,
    ToolCall,
    ToolDefinition,
    ToolProposal,
)
from kelvin_assistant.domain.planner import (
    ClarificationTurn,
    ClarifyDecision,
    CompleteDecision,
    PlannerDecision,
    PlannerRequest,
    ToolDecision,
)
from kelvin_assistant.ports.planner import AgentPlanner
from kelvin_assistant.ports.tools import ToolRegistry, UnknownToolError


class AgentPlanningError(RuntimeError):
    """Raised when a planner decision cannot safely advance a run."""


class ToolArgumentsValidationError(AgentPlanningError):
    """Raised when model arguments violate the registered tool schema."""


@dataclass(frozen=True, slots=True)
class ClarificationOutcome:
    """A run paused for one planner-generated question."""

    clarification: AgentClarification
    decision: ClarifyDecision


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """A policy-evaluated proposal created from a planner tool decision."""

    proposal: ToolProposal
    decision: ToolDecision


@dataclass(frozen=True, slots=True)
class CompletionOutcome:
    """A planner-completed run with a user-facing summary."""

    run: AgentRun
    decision: CompleteDecision


type PlanningOutcome = ClarificationOutcome | ToolOutcome | CompletionOutcome


class AgentPlanningService:
    """Bridge model decisions to deterministic agent domain operations."""

    def __init__(
        self,
        *,
        planner: AgentPlanner,
        registry: ToolRegistry,
        agent_service: AgentService,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._agent_service = agent_service

    def prepare_run(self, run: AgentRun) -> AgentRun:
        """Move a runnable state into planning before calling the model."""

        if run.status in {AgentStatus.RECEIVED, AgentStatus.CLARIFYING}:
            return self._agent_service.begin_planning(run)
        if run.status is AgentStatus.OBSERVING:
            return self._agent_service.continue_planning(run)
        if run.status is AgentStatus.PLANNING:
            return run
        raise AgentPlanningError(
            f"Cannot plan next step from agent status {run.status}"
        )

    async def plan_next(
        self,
        run: AgentRun,
        *,
        clarifications: Sequence[ClarificationTurn] = (),
        observation: str | None = None,
        policy_context: ToolPolicyContext,
    ) -> PlanningOutcome:
        """Create and deterministically evaluate the next planner decision."""

        if run.status is not AgentStatus.PLANNING:
            raise AgentPlanningError("Planner requires a run in planning state")
        remaining_steps = run.max_steps - run.step_count
        if remaining_steps < 1:
            raise AgentPlanningError("Agent run has no remaining execution steps")
        request = PlannerRequest.create(
            run.goal,
            self._registry.list_all(),
            remaining_steps=remaining_steps,
            clarifications=clarifications,
            observation=observation,
        )
        decision = await self._planner.plan(request)
        return self.apply_decision(
            run,
            decision,
            policy_context=policy_context,
        )

    def apply_decision(
        self,
        run: AgentRun,
        decision: PlannerDecision,
        *,
        policy_context: ToolPolicyContext,
    ) -> PlanningOutcome:
        """Validate one planner decision without making external calls."""

        if run.status is not AgentStatus.PLANNING:
            raise AgentPlanningError("Planner decision requires planning state")
        if isinstance(decision, ClarifyDecision):
            clarification = self._agent_service.request_clarification(
                run,
                ClarificationRequest(
                    question=decision.question,
                    reason=decision.reason,
                ),
            )
            return ClarificationOutcome(
                clarification=clarification,
                decision=decision,
            )
        if isinstance(decision, CompleteDecision):
            return CompletionOutcome(
                run=self._agent_service.complete_run(run),
                decision=decision,
            )

        try:
            definition = self._registry.get(decision.tool_name)
        except UnknownToolError as exc:
            raise AgentPlanningError(
                f"Planner selected an unknown tool: {decision.tool_name}"
            ) from exc
        validate_tool_arguments(definition, decision.arguments)
        proposal = self._agent_service.propose_tool(
            run,
            ToolCall(
                name=definition.name,
                arguments=decision.arguments,
                reason=decision.reason,
                expected_effect=decision.expected_effect,
                risk=definition.risk,
            ),
            context=policy_context,
        )
        return ToolOutcome(proposal=proposal, decision=decision)

    def fail_run(self, run: AgentRun) -> AgentRun:
        """Expose the guarded failure transition for API orchestration."""

        return self._agent_service.fail_run(run)


def validate_tool_arguments(
    definition: ToolDefinition,
    arguments: Mapping[str, JsonValue],
) -> None:
    """Validate the JSON-schema subset used by Kelvin's registered tools."""

    schema = definition.input_schema
    properties_value = schema.get("properties", {})
    if not isinstance(properties_value, Mapping):
        raise ToolArgumentsValidationError(
            f"Tool '{definition.name}' has an invalid properties schema"
        )
    properties = properties_value
    required_value = schema.get("required", ())
    if not isinstance(required_value, tuple):
        raise ToolArgumentsValidationError(
            f"Tool '{definition.name}' has an invalid required schema"
        )
    required = {item for item in required_value if isinstance(item, str)}
    if len(required) != len(required_value):
        raise ToolArgumentsValidationError(
            f"Tool '{definition.name}' has an invalid required schema"
        )

    missing = required - set(arguments)
    if missing:
        raise ToolArgumentsValidationError(
            f"Tool '{definition.name}' is missing arguments: "
            f"{', '.join(sorted(missing))}"
        )
    if schema.get("additionalProperties") is False:
        unknown = set(arguments) - set(properties)
        if unknown:
            raise ToolArgumentsValidationError(
                f"Tool '{definition.name}' has unsupported arguments: "
                f"{', '.join(sorted(unknown))}"
            )

    for name, value in arguments.items():
        property_schema = properties.get(name)
        if property_schema is None:
            continue
        if not isinstance(property_schema, Mapping):
            raise ToolArgumentsValidationError(
                f"Tool '{definition.name}' has an invalid schema for '{name}'"
            )
        _validate_argument_value(
            definition.name,
            name,
            value,
            property_schema,
        )


def _validate_argument_value(
    tool_name: str,
    argument_name: str,
    value: JsonValue,
    schema: Mapping[str, JsonValue],
) -> None:
    expected_type = schema.get("type")
    valid = (
        (expected_type == "string" and isinstance(value, str))
        or (expected_type == "boolean" and isinstance(value, bool))
        or (
            expected_type == "integer"
            and isinstance(value, int)
            and not isinstance(value, bool)
        )
        or (
            expected_type == "number"
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
        or (expected_type == "object" and isinstance(value, Mapping))
        or (expected_type == "array" and isinstance(value, tuple))
    )
    if not valid:
        raise ToolArgumentsValidationError(
            f"Tool '{tool_name}' argument '{argument_name}' must be {expected_type}"
        )
    if expected_type in {"integer", "number"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ToolArgumentsValidationError(
                f"Tool '{tool_name}' argument '{argument_name}' must be {expected_type}"
            )
        minimum = _schema_number(schema.get("minimum"))
        maximum = _schema_number(schema.get("maximum"))
        if minimum is not None and value < minimum:
            raise ToolArgumentsValidationError(
                f"Tool '{tool_name}' argument '{argument_name}' "
                f"must be at least {minimum}"
            )
        if maximum is not None and value > maximum:
            raise ToolArgumentsValidationError(
                f"Tool '{tool_name}' argument '{argument_name}' cannot exceed {maximum}"
            )


def _schema_number(value: JsonValue | None) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value
