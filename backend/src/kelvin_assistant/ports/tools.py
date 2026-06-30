"""Ports for discovering registered agent tools."""

from pathlib import Path
from typing import Protocol

from kelvin_assistant.domain.agent import (
    ToolCall,
    ToolDefinition,
    ToolExecutionResult,
)


class ToolRegistryError(LookupError):
    """Base error raised by tool registries."""


class DuplicateToolError(ToolRegistryError):
    """Raised when two definitions use the same tool name."""


class UnknownToolError(ToolRegistryError):
    """Raised when a requested tool is not registered."""


class ToolExecutionError(RuntimeError):
    """Raised when a tool call violates executor boundaries."""


class ToolRegistry(Protocol):
    """Read-only catalog of tools available to the agent."""

    def get(self, name: str) -> ToolDefinition:
        """Return one registered definition or raise UnknownToolError."""
        ...

    def list_all(self) -> tuple[ToolDefinition, ...]:
        """Return all definitions in deterministic name order."""
        ...


class ToolExecutor(Protocol):
    """Execute one structured tool inside a trusted local workspace."""

    @property
    def definition(self) -> ToolDefinition:
        """Return the exact tool definition implemented by this executor."""
        ...

    async def execute(
        self,
        call: ToolCall,
        *,
        workspace_root: Path,
    ) -> ToolExecutionResult:
        """Execute a validated call without using a shell."""
        ...
