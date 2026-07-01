"""Pydantic response models for public endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from kelvin_assistant.domain.agent import (
    DEFAULT_MAX_AGENT_STEPS,
    MAX_AGENT_GOAL_LENGTH,
    MAX_AGENT_STEPS,
    MAX_TOOL_OUTPUT_LENGTH,
    AgentStatus,
    ApprovalDecision,
    ToolPolicyDecision,
    ToolRisk,
)
from kelvin_assistant.domain.chat import MAX_MESSAGE_LENGTH
from kelvin_assistant.domain.memory import MemoryKind, MemoryScope
from kelvin_assistant.domain.planner import (
    MAX_CLARIFICATION_ANSWER_LENGTH,
    MAX_CLARIFICATION_QUESTION_LENGTH,
    MAX_CLARIFICATION_TURNS,
    MAX_COMPLETION_SUMMARY_LENGTH,
    MAX_PLANNER_REASON_LENGTH,
)


class RootResponse(BaseModel):
    """Response payload returned by the root endpoint."""

    name: str
    version: str
    environment: str


class HealthResponse(BaseModel):
    """Health check payload."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """Readiness payload for the configured language model runtime."""

    status: Literal["ready"]
    provider: str
    model: str


class DatabaseReadinessResponse(BaseModel):
    """Readiness payload for the configured database."""

    status: Literal["ready"]
    provider: Literal["postgresql"]


class ChatRequest(BaseModel):
    """Request payload for one non-streaming conversation turn."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    session_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        """Trim message boundaries and reject whitespace-only content."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Message cannot be empty")
        return normalized_value


class ChatResponse(BaseModel):
    """Response payload for one completed conversation turn."""

    session_id: UUID
    message: str
    model: str


class AgentRunCreateRequest(BaseModel):
    """Request payload for starting one agent run."""

    goal: str = Field(min_length=1, max_length=MAX_AGENT_GOAL_LENGTH)
    max_steps: int = Field(
        default=DEFAULT_MAX_AGENT_STEPS,
        ge=1,
        le=MAX_AGENT_STEPS,
    )
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("goal", "workspace_id")
    @classmethod
    def normalize_agent_text(cls, value: str | None) -> str | None:
        """Trim agent text fields and reject whitespace-only values."""

        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Agent text cannot be empty")
        return normalized_value


class AgentRunResponse(BaseModel):
    """Public state of one server-managed agent run."""

    id: UUID
    goal: str
    status: AgentStatus
    step_count: int
    max_steps: int
    version: int
    workspace_id: str | None


class AgentToolCallRequest(BaseModel):
    """Request payload for proposing one structured agent tool call."""

    name: str = Field(min_length=3, max_length=128)
    arguments: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=2_048)
    expected_effect: str = Field(min_length=1, max_length=2_048)
    risk: ToolRisk

    @field_validator("name", "reason", "expected_effect")
    @classmethod
    def normalize_tool_text(cls, value: str) -> str:
        """Trim tool text fields and reject whitespace-only values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Tool call text cannot be empty")
        return normalized_value


class AgentToolApprovalRequest(BaseModel):
    """Request payload for resolving one pending tool approval."""

    tool_call_id: UUID
    decision: Literal["approved", "rejected"]


class AgentToolProposalResponse(BaseModel):
    """Public state of one server-managed tool proposal."""

    run: AgentRunResponse
    tool_call_id: UUID
    tool_name: str
    arguments: dict[str, object]
    reason: str
    expected_effect: str
    risk: ToolRisk
    policy_decision: ToolPolicyDecision
    policy_reason: str
    approval_status: ApprovalDecision | None


class AgentToolResultRequest(BaseModel):
    """Request payload for one completed local tool execution."""

    tool_call_id: UUID
    succeeded: bool
    output: str = Field(default="", max_length=MAX_TOOL_OUTPUT_LENGTH)
    error: str | None = Field(default=None, max_length=MAX_TOOL_OUTPUT_LENGTH)
    truncated: bool = False
    duration_ms: int = Field(default=0, ge=0)


class AgentToolResultResponse(BaseModel):
    """Public result of one completed agent tool execution."""

    run: AgentRunResponse
    tool_call_id: UUID
    tool_name: str
    succeeded: bool
    output: str
    error: str | None
    truncated: bool
    duration_ms: int


class AgentClarificationTurnRequest(BaseModel):
    """One prior planner question and user answer carried by the client."""

    question: str = Field(
        min_length=1,
        max_length=MAX_CLARIFICATION_QUESTION_LENGTH,
    )
    answer: str = Field(
        min_length=1,
        max_length=MAX_CLARIFICATION_ANSWER_LENGTH,
    )


class AgentNextRequest(BaseModel):
    """Bounded context for planning the next agent step."""

    clarifications: list[AgentClarificationTurnRequest] = Field(
        default_factory=list,
        max_length=MAX_CLARIFICATION_TURNS,
    )
    observation: str | None = Field(
        default=None,
        max_length=MAX_TOOL_OUTPUT_LENGTH,
    )


class AgentNextClarificationResponse(BaseModel):
    """Planner response requiring one targeted user answer."""

    action: Literal["clarify"] = "clarify"
    run: AgentRunResponse
    question: str = Field(max_length=MAX_CLARIFICATION_QUESTION_LENGTH)
    reason: str = Field(max_length=MAX_PLANNER_REASON_LENGTH)


class AgentNextToolResponse(BaseModel):
    """Planner response containing one policy-evaluated tool proposal."""

    action: Literal["tool"] = "tool"
    proposal: AgentToolProposalResponse


class AgentNextCompletionResponse(BaseModel):
    """Planner response completing the agent run without another tool."""

    action: Literal["complete"] = "complete"
    run: AgentRunResponse
    summary: str = Field(max_length=MAX_COMPLETION_SUMMARY_LENGTH)


type AgentNextResponse = (
    AgentNextClarificationResponse | AgentNextToolResponse | AgentNextCompletionResponse
)


class MemoryCreateRequest(BaseModel):
    """Request payload for storing one memory item."""

    scope: MemoryScope
    kind: MemoryKind
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("content", "source")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Trim text boundaries and reject whitespace-only values."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Value cannot be empty")
        return normalized_value


class MemoryResponse(BaseModel):
    """Response payload for one memory item."""

    id: UUID | None
    scope: MemoryScope
    kind: MemoryKind
    content: str
    source: str
    confidence: float
    metadata: dict[str, str]
    created_at: datetime | None
    updated_at: datetime | None
    expires_at: datetime | None


class MemoryListResponse(BaseModel):
    """Response payload for active memory listing."""

    memories: list[MemoryResponse]


class VersionResponse(BaseModel):
    """Version endpoint payload."""

    version: str
