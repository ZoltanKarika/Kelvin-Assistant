"""Pydantic response models for public endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from kelvin_assistant.domain.agent import (
    DEFAULT_MAX_AGENT_STEPS,
    MAX_AGENT_GOAL_LENGTH,
    MAX_AGENT_STEPS,
    AgentStatus,
)
from kelvin_assistant.domain.chat import MAX_MESSAGE_LENGTH
from kelvin_assistant.domain.memory import MemoryKind, MemoryScope


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

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        """Trim goal boundaries and reject whitespace-only content."""

        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Agent goal cannot be empty")
        return normalized_value


class AgentRunResponse(BaseModel):
    """Public state of one server-managed agent run."""

    id: UUID
    goal: str
    status: AgentStatus
    step_count: int
    max_steps: int
    version: int


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
