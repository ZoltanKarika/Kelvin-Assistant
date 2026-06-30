"""Framework-independent agent domain models and state rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4

DEFAULT_MAX_AGENT_STEPS = 12
MAX_AGENT_STEPS = 100
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | tuple[JsonValue, ...] | Mapping[str, JsonValue]


class AgentDomainError(ValueError):
    """Raised when an agent domain object violates an invariant."""


class InvalidAgentTransitionError(AgentDomainError):
    """Raised when an agent run attempts an unsupported state transition."""


class AgentStepLimitError(AgentDomainError):
    """Raised when an agent run would exceed its execution step limit."""


class AgentStatus(StrEnum):
    """Lifecycle states of one agent run."""

    RECEIVED = "received"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Return whether no further transition is allowed."""

        return self in {
            AgentStatus.COMPLETED,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }


class ToolRisk(StrEnum):
    """Risk assigned to a registered tool operation by deterministic policy."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    PRIVILEGED = "privileged"

    @property
    def requires_approval(self) -> bool:
        """Return whether the operation must not execute automatically."""

        return self is not ToolRisk.READ


class ToolExecutionTarget(StrEnum):
    """Trusted runtime responsible for executing a tool."""

    WINDOWS_CLIENT = "windows_client"
    BACKEND = "backend"


class ApprovalDecision(StrEnum):
    """User decision for one proposed tool call."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


_ALLOWED_TRANSITIONS: Mapping[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.RECEIVED: frozenset(
        {
            AgentStatus.CLARIFYING,
            AgentStatus.PLANNING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.CLARIFYING: frozenset(
        {
            AgentStatus.PLANNING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.PLANNING: frozenset(
        {
            AgentStatus.AWAITING_APPROVAL,
            AgentStatus.EXECUTING,
            AgentStatus.COMPLETED,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.AWAITING_APPROVAL: frozenset(
        {
            AgentStatus.EXECUTING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.EXECUTING: frozenset(
        {
            AgentStatus.OBSERVING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.OBSERVING: frozenset(
        {
            AgentStatus.PLANNING,
            AgentStatus.COMPLETED,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        }
    ),
    AgentStatus.COMPLETED: frozenset(),
    AgentStatus.CANCELLED: frozenset(),
    AgentStatus.FAILED: frozenset(),
}


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AgentDomainError(f"{field_name} cannot be empty")
    return normalized


def _normalize_tool_name(value: str) -> str:
    name = value.strip()
    if not _TOOL_NAME_PATTERN.fullmatch(name):
        raise AgentDomainError("Tool name must use a lowercase namespace and operation")
    return name


def _freeze_json(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        for key, item in value.items():
            normalized_key = key.strip()
            if not normalized_key:
                raise AgentDomainError("Tool argument keys cannot be empty")
            frozen[normalized_key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_json_mapping(value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise AgentDomainError("Expected a JSON object")
    return frozen


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    """A targeted question required before an agent can safely plan."""

    question: str
    reason: str

    def __post_init__(self) -> None:
        """Normalize and validate clarification text."""

        object.__setattr__(
            self,
            "question",
            _normalize_required_text(self.question, "Clarification question"),
        )
        object.__setattr__(
            self,
            "reason",
            _normalize_required_text(self.reason, "Clarification reason"),
        )


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Metadata and JSON input schema for one registered tool."""

    name: str
    description: str
    input_schema: Mapping[str, JsonValue]
    risk: ToolRisk
    execution_target: ToolExecutionTarget
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        """Normalize and validate tool metadata."""

        object.__setattr__(self, "name", _normalize_tool_name(self.name))
        object.__setattr__(
            self,
            "description",
            _normalize_required_text(self.description, "Tool description"),
        )
        object.__setattr__(
            self,
            "input_schema",
            _freeze_json_mapping(self.input_schema),
        )
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            raise AgentDomainError("Tool timeout must be between 1 and 300 seconds")


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A validated, structured request to invoke one registered tool."""

    name: str
    arguments: Mapping[str, JsonValue]
    reason: str
    expected_effect: str
    risk: ToolRisk
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Normalize text and freeze tool arguments."""

        object.__setattr__(self, "name", _normalize_tool_name(self.name))
        object.__setattr__(
            self,
            "reason",
            _normalize_required_text(self.reason, "Tool call reason"),
        )
        object.__setattr__(
            self,
            "expected_effect",
            _normalize_required_text(
                self.expected_effect,
                "Tool call expected effect",
            ),
        )
        object.__setattr__(
            self,
            "arguments",
            _freeze_json_mapping(self.arguments),
        )


@dataclass(frozen=True, slots=True)
class ToolApproval:
    """A pending or completed user decision for one tool call."""

    tool_call_id: UUID
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate decision metadata consistency."""

        decided_by = self.decided_by.strip() if self.decided_by is not None else None

        if self.decision is ApprovalDecision.PENDING:
            if decided_by is not None or self.decided_at is not None:
                raise AgentDomainError(
                    "Pending approval cannot contain decision metadata"
                )
        elif not decided_by or self.decided_at is None:
            raise AgentDomainError(
                "Completed approval requires decision author and timestamp"
            )

        object.__setattr__(self, "decided_by", decided_by)


@dataclass(frozen=True, slots=True)
class AgentRun:
    """An immutable agent execution with guarded state transitions."""

    id: UUID
    goal: str
    status: AgentStatus = AgentStatus.RECEIVED
    step_count: int = 0
    max_steps: int = DEFAULT_MAX_AGENT_STEPS

    def __post_init__(self) -> None:
        """Normalize and validate run invariants."""

        object.__setattr__(
            self,
            "goal",
            _normalize_required_text(self.goal, "Agent goal"),
        )
        if self.max_steps < 1 or self.max_steps > MAX_AGENT_STEPS:
            raise AgentDomainError(
                f"Agent max steps must be between 1 and {MAX_AGENT_STEPS}"
            )
        if self.step_count < 0 or self.step_count > self.max_steps:
            raise AgentDomainError("Agent step count is outside the allowed range")

    @classmethod
    def create(
        cls,
        goal: str,
        *,
        max_steps: int = DEFAULT_MAX_AGENT_STEPS,
    ) -> AgentRun:
        """Create a new run in the received state."""

        return cls(id=uuid4(), goal=goal, max_steps=max_steps)

    def transition_to(self, next_status: AgentStatus) -> AgentRun:
        """Return a new run after one valid lifecycle transition."""

        if next_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidAgentTransitionError(
                f"Cannot transition agent run from {self.status} to {next_status}"
            )

        next_step_count = self.step_count
        if next_status is AgentStatus.EXECUTING:
            if self.step_count >= self.max_steps:
                raise AgentStepLimitError(
                    f"Agent run reached its {self.max_steps} step limit"
                )
            next_step_count += 1

        return replace(
            self,
            status=next_status,
            step_count=next_step_count,
        )
