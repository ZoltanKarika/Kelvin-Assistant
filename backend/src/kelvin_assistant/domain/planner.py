"""Provider-independent domain models for structured agent planning."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from kelvin_assistant.domain.agent import (
    MAX_AGENT_GOAL_LENGTH,
    MAX_AGENT_STEPS,
    MAX_TOOL_OUTPUT_LENGTH,
    JsonValue,
    ToolDefinition,
)

MAX_CLARIFICATION_TURNS = 4
MAX_PLANNER_REASON_LENGTH = 2_048
MAX_CLARIFICATION_QUESTION_LENGTH = 2_048
MAX_CLARIFICATION_ANSWER_LENGTH = 8_192
MAX_COMPLETION_SUMMARY_LENGTH = 8_192
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class PlannerDomainError(ValueError):
    """Raised when planner input or output violates its safe contract."""


class PlannerAction(StrEnum):
    """Supported structured decisions returned by an agent planner."""

    CLARIFY = "clarify"
    TOOL = "tool"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class ClarificationTurn:
    """One bounded planner question and its user-provided answer."""

    question: str
    answer: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "question",
            _required_text(
                self.question,
                "Clarification question",
                MAX_CLARIFICATION_QUESTION_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "answer",
            _required_text(
                self.answer,
                "Clarification answer",
                MAX_CLARIFICATION_ANSWER_LENGTH,
            ),
        )


@dataclass(frozen=True, slots=True)
class PlannerRequest:
    """Bounded context supplied to a provider-specific planner adapter."""

    goal: str
    tools: tuple[ToolDefinition, ...]
    remaining_steps: int
    clarifications: tuple[ClarificationTurn, ...] = ()
    observation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "goal",
            _required_text(
                self.goal,
                "Planner goal",
                MAX_AGENT_GOAL_LENGTH,
            ),
        )
        object.__setattr__(self, "tools", _validate_tools(self.tools))
        if self.remaining_steps < 1 or self.remaining_steps > MAX_AGENT_STEPS:
            raise PlannerDomainError(
                f"Planner remaining steps must be between 1 and {MAX_AGENT_STEPS}"
            )
        if len(self.clarifications) > MAX_CLARIFICATION_TURNS:
            raise PlannerDomainError(
                f"Planner context cannot exceed {MAX_CLARIFICATION_TURNS} "
                "clarification turns"
            )
        object.__setattr__(
            self,
            "clarifications",
            tuple(self.clarifications),
        )
        if self.observation is not None:
            normalized_observation = self.observation.strip()
            if not normalized_observation:
                object.__setattr__(self, "observation", None)
            elif len(normalized_observation) > MAX_TOOL_OUTPUT_LENGTH:
                raise PlannerDomainError(
                    f"Planner observation cannot exceed "
                    f"{MAX_TOOL_OUTPUT_LENGTH} characters"
                )
            else:
                object.__setattr__(
                    self,
                    "observation",
                    normalized_observation,
                )

    @classmethod
    def create(
        cls,
        goal: str,
        tools: Sequence[ToolDefinition],
        *,
        remaining_steps: int,
        clarifications: Sequence[ClarificationTurn] = (),
        observation: str | None = None,
    ) -> PlannerRequest:
        """Create a request while freezing caller-owned sequences."""

        return cls(
            goal=goal,
            tools=tuple(tools),
            remaining_steps=remaining_steps,
            clarifications=tuple(clarifications),
            observation=observation,
        )


@dataclass(frozen=True, slots=True)
class ClarifyDecision:
    """Request one targeted piece of missing information."""

    question: str
    reason: str
    action: PlannerAction = field(
        default=PlannerAction.CLARIFY,
        init=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "question",
            _required_text(
                self.question,
                "Clarification question",
                MAX_CLARIFICATION_QUESTION_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "reason",
            _planner_reason(self.reason),
        )


@dataclass(frozen=True, slots=True)
class ToolDecision:
    """Propose one registered tool name with JSON-compatible arguments."""

    tool_name: str
    arguments: Mapping[str, JsonValue]
    reason: str
    expected_effect: str
    action: PlannerAction = field(
        default=PlannerAction.TOOL,
        init=False,
    )

    def __post_init__(self) -> None:
        normalized_name = self.tool_name.strip()
        if not _TOOL_NAME_PATTERN.fullmatch(normalized_name):
            raise PlannerDomainError(
                "Planner tool name must use a lowercase namespace and operation"
            )
        object.__setattr__(self, "tool_name", normalized_name)
        object.__setattr__(
            self,
            "arguments",
            _freeze_json_mapping(self.arguments),
        )
        object.__setattr__(self, "reason", _planner_reason(self.reason))
        object.__setattr__(
            self,
            "expected_effect",
            _required_text(
                self.expected_effect,
                "Planner expected effect",
                MAX_PLANNER_REASON_LENGTH,
            ),
        )


@dataclass(frozen=True, slots=True)
class CompleteDecision:
    """Finish a run without proposing another tool."""

    summary: str
    action: PlannerAction = field(
        default=PlannerAction.COMPLETE,
        init=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "summary",
            _required_text(
                self.summary,
                "Planner completion summary",
                MAX_COMPLETION_SUMMARY_LENGTH,
            ),
        )


type PlannerDecision = ClarifyDecision | ToolDecision | CompleteDecision


def _required_text(value: str, field_name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise PlannerDomainError(f"{field_name} cannot be empty")
    if len(normalized) > maximum:
        raise PlannerDomainError(f"{field_name} cannot exceed {maximum} characters")
    return normalized


def _planner_reason(value: str) -> str:
    return _required_text(
        value,
        "Planner reason",
        MAX_PLANNER_REASON_LENGTH,
    )


def _validate_tools(
    tools: tuple[ToolDefinition, ...],
) -> tuple[ToolDefinition, ...]:
    frozen_tools = tuple(tools)
    if not frozen_tools:
        raise PlannerDomainError("Planner requires at least one registered tool")
    names = [tool.name for tool in frozen_tools]
    if len(names) != len(set(names)):
        raise PlannerDomainError("Planner tools must have unique names")
    return frozen_tools


def _freeze_json_mapping(
    value: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    frozen: dict[str, JsonValue] = {}
    for key, item in value.items():
        normalized_key = key.strip()
        if not normalized_key:
            raise PlannerDomainError("Planner argument keys cannot be empty")
        frozen[normalized_key] = _freeze_json(item)
    return MappingProxyType(frozen)


def _freeze_json(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value)
    if isinstance(value, tuple):
        return tuple(_freeze_json(item) for item in value)
    return value
