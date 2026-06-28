"""Pydantic response models for public endpoints."""

from typing import Literal

from pydantic import BaseModel


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


class VersionResponse(BaseModel):
    """Version endpoint payload."""

    version: str
