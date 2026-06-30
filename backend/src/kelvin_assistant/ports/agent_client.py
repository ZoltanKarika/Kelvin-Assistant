"""Port and errors for the remote agent HTTP API."""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.agent import (
    AgentRun,
    JsonValue,
    ToolExecutionResult,
    ToolProposal,
)


class AgentClientError(RuntimeError):
    """Base error raised by agent API clients."""


class AgentClientUnavailableError(AgentClientError):
    """Raised when the remote Kelvin API cannot be reached."""


class AgentClientResponseError(AgentClientError):
    """Raised when the remote Kelvin API returns an unusable response."""


class AgentApiClient(Protocol):
    """Interface used by the local Windows tool client."""

    async def create_run(
        self,
        *,
        goal: str,
        workspace_id: str,
    ) -> AgentRun:
        """Create one server-managed agent run."""
        ...

    async def begin_planning(self, run_id: UUID) -> AgentRun:
        """Move one server-managed run into planning."""
        ...

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
    ) -> ToolProposal:
        """Submit one structured read-only tool proposal."""
        ...

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        """Submit a matching local execution result."""
        ...
