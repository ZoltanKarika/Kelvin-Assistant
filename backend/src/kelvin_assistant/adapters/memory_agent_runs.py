"""In-memory storage adapter for versioned agent runs."""

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from kelvin_assistant.domain.agent import (
    AgentRun,
    ToolExecutionResult,
    ToolProposal,
)
from kelvin_assistant.ports.agent_runs import (
    AgentProposalNotFoundError,
    AgentResultNotFoundError,
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStore,
)


class InMemoryAgentRunStore(AgentRunStore):
    """Store immutable agent runs in process memory."""

    def __init__(self) -> None:
        self._runs: dict[UUID, AgentRun] = {}
        self._proposals: dict[UUID, ToolProposal] = {}
        self._results: dict[UUID, ToolExecutionResult] = {}
        self._proposals_history: dict[UUID, list[ToolProposal]] = {}
        self._results_history: dict[UUID, list[ToolExecutionResult]] = {}
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

    async def cancel_run(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Cancel one run and remove its active proposal atomically."""

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
            self._proposals.pop(run.id, None)

            # Update history proposals for this run
            history = self._proposals_history.get(run.id, [])
            for i, p in enumerate(history):
                if run.status.is_terminal:
                    history[i] = replace(p, run=run)

    async def update_proposal(
        self,
        proposal: ToolProposal,
        *,
        expected_version: int,
    ) -> None:
        """Atomically store a proposal and its updated agent run."""

        async with self._lock:
            stored_run = self._runs.get(proposal.run.id)
            if stored_run is None:
                raise AgentRunNotFoundError(proposal.run.id)
            if (
                stored_run.version != expected_version
                or proposal.run.version != expected_version + 1
            ):
                raise AgentRunConflictError(proposal.run.id)
            self._runs[proposal.run.id] = proposal.run
            self._proposals[proposal.run.id] = proposal

            # Update proposal history
            history = self._proposals_history.setdefault(proposal.run.id, [])
            for i, p in enumerate(history):
                if p.call.id == proposal.call.id:
                    history[i] = proposal
                    break
            else:
                history.append(proposal)

    async def get_proposal(self, run_id: UUID) -> ToolProposal:
        """Return the active server-managed proposal for a run."""

        async with self._lock:
            if run_id not in self._runs:
                raise AgentRunNotFoundError(run_id)
            proposal = self._proposals.get(run_id)
            if proposal is None:
                raise AgentProposalNotFoundError(run_id)
            return proposal

    async def complete_proposal(
        self,
        run: AgentRun,
        result: ToolExecutionResult,
        *,
        expected_version: int,
    ) -> None:
        """Atomically finish the active proposal and store its result."""

        async with self._lock:
            stored_run = self._runs.get(run.id)
            if stored_run is None:
                raise AgentRunNotFoundError(run.id)
            proposal = self._proposals.get(run.id)
            if proposal is None:
                raise AgentProposalNotFoundError(run.id)
            if proposal.call.id != result.tool_call_id:
                raise AgentRunConflictError(run.id)
            if (
                stored_run.version != expected_version
                or run.version != expected_version + 1
            ):
                raise AgentRunConflictError(run.id)
            self._runs[run.id] = run
            self._results[run.id] = result
            del self._proposals[run.id]

            # In history, find the proposal and close it
            history = self._proposals_history.get(run.id, [])
            for i, p in enumerate(history):
                if p.call.id == result.tool_call_id:
                    history[i] = replace(p, run=run)
                    break

            # Append to result history
            self._results_history.setdefault(run.id, []).append(result)

    async def get_result(self, run_id: UUID) -> ToolExecutionResult:
        """Return the latest stored tool execution result."""

        async with self._lock:
            if run_id not in self._runs:
                raise AgentRunNotFoundError(run_id)
            result = self._results.get(run_id)
            if result is None:
                raise AgentResultNotFoundError(run_id)
            return result

    async def list_runs(self) -> Sequence[AgentRun]:
        """List all stored agent runs sorted by creation time descending."""

        async with self._lock:
            return sorted(
                self._runs.values(),
                key=lambda r: r.created_at or datetime.min,
                reverse=True,
            )

    async def get_run_steps(
        self, run_id: UUID
    ) -> Sequence[tuple[ToolProposal, ToolExecutionResult | None]]:
        """Return all proposals and results for a run, sorted by creation time."""

        async with self._lock:
            proposals = self._proposals_history.get(run_id, [])
            results = {r.tool_call_id: r for r in self._results_history.get(run_id, [])}
            return [(p, results.get(p.call.id)) for p in proposals]
