"""In-memory storage adapter for versioned agent runs."""

import asyncio
from uuid import UUID

from kelvin_assistant.domain.agent import AgentRun
from kelvin_assistant.ports.agent_runs import (
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStore,
)


class InMemoryAgentRunStore(AgentRunStore):
    """Store immutable agent runs in process memory."""

    def __init__(self) -> None:
        self._runs: dict[UUID, AgentRun] = {}
        self._lock = asyncio.Lock()

    async def add(self, run: AgentRun) -> None:
        """Store a new run unless its identifier already exists."""

        async with self._lock:
            if run.id in self._runs:
                raise AgentRunConflictError(run.id)
            self._runs[run.id] = run

    async def get(self, run_id: UUID) -> AgentRun:
        """Return a run by identifier."""

        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise AgentRunNotFoundError(run_id)
            return run

    async def update(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Atomically replace a run using optimistic version checking."""

        async with self._lock:
            stored_run = self._runs.get(run.id)
            if stored_run is None:
                raise AgentRunNotFoundError(run.id)
            if (
                stored_run.version != expected_version
                or run.version != expected_version + 1
            ):
                raise AgentRunConflictError(run.id)
            self._runs[run.id] = run
