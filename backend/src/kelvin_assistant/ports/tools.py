"""Ports for discovering registered agent tools."""

from typing import Protocol

from kelvin_assistant.domain.agent import ToolDefinition


class ToolRegistryError(LookupError):
    """Base error raised by tool registries."""


class DuplicateToolError(ToolRegistryError):
    """Raised when two definitions use the same tool name."""


class UnknownToolError(ToolRegistryError):
    """Raised when a requested tool is not registered."""


class ToolRegistry(Protocol):
    """Read-only catalog of tools available to the agent."""

    def get(self, name: str) -> ToolDefinition:
        """Return one registered definition or raise UnknownToolError."""
        ...

    def list_all(self) -> tuple[ToolDefinition, ...]:
        """Return all definitions in deterministic name order."""
        ...
