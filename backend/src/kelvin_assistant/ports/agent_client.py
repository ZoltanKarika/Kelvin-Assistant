"""Port and errors for the remote agent HTTP API."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.agent import (
    AgentRun,
    JsonValue,
    ToolExecutionResult,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.domain.planner import ClarificationTurn


class AgentClientError(RuntimeError):
    """Base error raised by agent API clients."""


class AgentClientUnavailableError(AgentClientError):
    """Raised when the remote Kelvin API cannot be reached."""


class AgentClientResponseError(AgentClientError):
    """Raised when the remote Kelvin API returns an unusable response."""


@dataclass(frozen=True, slots=True)
class AgentClarificationStep:
    """Remote planner decision requiring one user answer."""

    run: AgentRun
    question: str
    reason: str


@dataclass(frozen=True, slots=True)
class AgentToolStep:
    """Remote planner decision containing one policy-evaluated tool."""

    proposal: ToolProposal


@dataclass(frozen=True, slots=True)
class AgentCompletionStep:
    """Remote planner decision completing the current run."""

    run: AgentRun
    summary: str


type AgentNextStep = AgentClarificationStep | AgentToolStep | AgentCompletionStep


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

    async def plan_next(
        self,
        run_id: UUID,
        *,
        clarifications: Sequence[ClarificationTurn] = (),
        observation: str | None = None,
    ) -> AgentNextStep:
        """Request one model-planned and policy-evaluated next step."""
        ...

    async def propose_tool(
        self,
        run_id: UUID,
        *,
        name: str,
        arguments: Mapping[str, JsonValue],
        reason: str,
        expected_effect: str,
        risk: ToolRisk,
    ) -> ToolProposal:
        """Submit one structured tool proposal."""
        ...

    async def resolve_approval(
        self,
        run_id: UUID,
        *,
        tool_call_id: UUID,
        approved: bool,
    ) -> ToolProposal:
        """Resolve one pending tool proposal with an explicit user decision."""
        ...

    async def submit_result(
        self,
        run_id: UUID,
        result: ToolExecutionResult,
    ) -> AgentRun:
        """Submit a matching local execution result."""
        ...
