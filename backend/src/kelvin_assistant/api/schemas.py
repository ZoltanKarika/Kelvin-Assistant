"""Pydantic response models for public endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from kelvin_assistant.domain.chat import MAX_MESSAGE_LENGTH


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


class VersionResponse(BaseModel):
    """Version endpoint payload."""

    version: str
