"""Unit tests for the in-memory agent run store."""

import asyncio
from uuid import uuid4

import pytest

from kelvin_assistant.adapters.memory_agent_runs import InMemoryAgentRunStore
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ToolCall,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.ports.agent_runs import (
    AgentProposalNotFoundError,
    AgentRunConflictError,
    AgentRunNotFoundError,
)


def test_add_and_get_agent_run() -> None:
    """A newly added immutable agent run can be retrieved unchanged."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        run = AgentRun.create("Inspect the project")

        await store.add(run)

        assert await store.get(run.id) == run

    asyncio.run(scenario())


def test_get_rejects_unknown_agent_run() -> None:
    """Looking up an unknown identifier raises a stable storage error."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        run_id = uuid4()

        with pytest.raises(
            AgentRunNotFoundError,
            match=f"Agent run not found: {run_id}",
        ):
            await store.get(run_id)

    asyncio.run(scenario())


def test_add_rejects_duplicate_agent_run() -> None:
    """A duplicate identifier cannot silently replace agent state."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        run = AgentRun.create("Inspect the project")
        await store.add(run)

        with pytest.raises(AgentRunConflictError):
            await store.add(run)

    asyncio.run(scenario())


def test_update_replaces_expected_agent_run_version() -> None:
    """An update succeeds when the stored version matches the expectation."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        original = AgentRun.create("Inspect the project")
        updated = original.transition_to(AgentStatus.PLANNING)
        await store.add(original)

        await store.update(updated, expected_version=0)

        assert await store.get(original.id) == updated
        assert updated.version == 1

    asyncio.run(scenario())


def test_update_rejects_unknown_agent_run() -> None:
    """An update cannot create a missing run implicitly."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        run = AgentRun.create("Inspect the project").transition_to(AgentStatus.PLANNING)

        with pytest.raises(AgentRunNotFoundError):
            await store.update(run, expected_version=0)

    asyncio.run(scenario())


def test_update_rejects_stale_agent_run_version() -> None:
    """A stale state transition cannot overwrite a newer stored run."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        original = AgentRun.create("Inspect the project")
        planning = original.transition_to(AgentStatus.PLANNING)
        clarifying = original.transition_to(AgentStatus.CLARIFYING)
        await store.add(original)
        await store.update(planning, expected_version=0)

        with pytest.raises(
            AgentRunConflictError,
            match=f"Agent run changed concurrently: {original.id}",
        ):
            await store.update(clarifying, expected_version=0)

    asyncio.run(scenario())


def test_concurrent_updates_allow_exactly_one_winner() -> None:
    """The store serializes competing updates from the same run version."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        original = AgentRun.create("Inspect the project")
        planning = original.transition_to(AgentStatus.PLANNING)
        clarifying = original.transition_to(AgentStatus.CLARIFYING)
        await store.add(original)

        results = await asyncio.gather(
            store.update(planning, expected_version=0),
            store.update(clarifying, expected_version=0),
            return_exceptions=True,
        )

        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, AgentRunConflictError) for result in results) == 1
        assert (await store.get(original.id)).version == 1

    asyncio.run(scenario())


def test_update_proposal_atomically_persists_run_and_tool_call() -> None:
    """Proposal storage updates run state and tool data under one lock."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        original = AgentRun.create("Inspect the project")
        planning = original.transition_to(AgentStatus.PLANNING)
        awaiting = planning.transition_to(AgentStatus.AWAITING_APPROVAL)
        proposal = ToolProposal(
            run=awaiting,
            call=ToolCall(
                name="file.patch",
                arguments={"workspace": "kelvin-assistant"},
                reason="Update one file.",
                expected_effect="The file content changes.",
                risk=ToolRisk.WRITE,
            ),
            policy_result=ToolPolicyResult(
                decision=ToolPolicyDecision.REQUIRE_APPROVAL,
                reason="Write operations require approval.",
            ),
        )
        await store.add(planning)

        await store.update_proposal(
            proposal,
            expected_version=planning.version,
        )

        assert await store.get(original.id) == awaiting
        assert await store.get_proposal(original.id) == proposal

    asyncio.run(scenario())


def test_complete_proposal_atomically_stores_result_and_closes_call() -> None:
    """Completing a proposal updates run, stores result, and removes active call."""

    async def scenario() -> None:
        store = InMemoryAgentRunStore()
        planning = AgentRun.create("Inspect the project").transition_to(
            AgentStatus.PLANNING
        )
        executing = planning.transition_to(AgentStatus.EXECUTING)
        call = ToolCall(
            name="git.status",
            arguments={},
            reason="Inspect repository state.",
            expected_effect="No state change.",
            risk=ToolRisk.READ,
        )
        proposal = ToolProposal(
            run=executing,
            call=call,
            policy_result=ToolPolicyResult(
                decision=ToolPolicyDecision.ALLOW,
                reason="Read-only tool is allowed.",
            ),
        )
        observed = executing.transition_to(AgentStatus.OBSERVING)
        result = ToolExecutionResult(
            tool_call_id=call.id,
            tool_name=call.name,
            succeeded=True,
            output="## main",
        )
        await store.add(planning)
        await store.update_proposal(
            proposal,
            expected_version=planning.version,
        )

        await store.complete_proposal(
            observed,
            result,
            expected_version=executing.version,
        )

        assert await store.get(planning.id) == observed
        assert await store.get_result(planning.id) == result
        with pytest.raises(AgentProposalNotFoundError):
            await store.get_proposal(planning.id)

    asyncio.run(scenario())
