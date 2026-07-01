"""Port for provider-independent structured agent planning."""

from typing import Protocol

from kelvin_assistant.domain.planner import PlannerDecision, PlannerRequest


class AgentPlannerError(RuntimeError):
    """Base error raised by structured planner adapters."""


class AgentPlannerUnavailableError(AgentPlannerError):
    """Raised when the configured planner provider cannot be reached."""


class AgentPlannerResponseError(AgentPlannerError):
    """Raised after the planner returns unusable structured output."""


class AgentPlanner(Protocol):
    """Create one validated decision for the next agent step."""

    async def plan(self, request: PlannerRequest) -> PlannerDecision:
        """Return exactly one clarify, tool, or complete decision."""
        ...
