"""Persistence port for versioned agent runs."""

from typing import Protocol
from uuid import UUID

from kelvin_assistant.domain.agent import AgentRun, ToolProposal


class AgentRunStoreError(RuntimeError):
    """Base error raised by agent run storage implementations."""


class AgentRunNotFoundError(AgentRunStoreError):
    """Raised when a requested agent run does not exist."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Agent run not found: {run_id}")
        self.run_id = run_id


class AgentRunConflictError(AgentRunStoreError):
    """Raised when an agent run changed concurrently."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Agent run changed concurrently: {run_id}")
        self.run_id = run_id


class AgentProposalNotFoundError(AgentRunStoreError):
    """Raised when a run has no server-managed tool proposal."""

    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"Agent tool proposal not found: {run_id}")
        self.run_id = run_id


class AgentRunStore(Protocol):
    """Persistence boundary for immutable, versioned agent runs."""

    async def add(self, run: AgentRun) -> None:
        """Store a new run or raise a conflict if it already exists."""
        ...

    async def get(self, run_id: UUID) -> AgentRun:
        """Return an existing run or raise a not-found error."""
        ...

    async def update(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Replace a run when its stored version matches the expectation."""
        ...

    async def update_proposal(
        self,
        proposal: ToolProposal,
        *,
        expected_version: int,
    ) -> None:
        """Atomically store a proposal and its updated agent run."""
        ...

    async def get_proposal(self, run_id: UUID) -> ToolProposal:
        """Return the active proposal for a run or raise not-found."""
        ...
