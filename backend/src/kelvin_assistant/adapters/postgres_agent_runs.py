"""PostgreSQL adapter for persistent, auditable agent runs."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Protocol, TypeVar, cast
from uuid import UUID

import psycopg

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ApprovalDecision,
    JsonValue,
    ToolApproval,
    ToolCall,
    ToolExecutionResult,
    ToolPolicyDecision,
    ToolPolicyResult,
    ToolProposal,
    ToolRisk,
)
from kelvin_assistant.ports.agent_runs import (
    AgentProposalNotFoundError,
    AgentResultNotFoundError,
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStore,
    AgentRunStoreConfigurationError,
    AgentRunStoreError,
    AgentRunStoreUnavailableError,
)

LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")


class _AgentCursor(Protocol):
    """Small async cursor surface used by the agent repository."""

    async def execute(self, sql: str, params: tuple[object, ...]) -> object:
        """Execute one SQL statement."""

    async def fetchone(self) -> tuple[object, ...] | None:
        """Fetch one row from the previous statement."""

    async def fetchall(self) -> Sequence[tuple[object, ...]]:
        """Fetch all rows from the previous statement."""


class PostgresAgentRunStore(AgentRunStore):
    """Persist versioned agent state and immutable execution audit records."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def add(self, run: AgentRun) -> None:
        """Insert one new agent run without replacing existing audit state."""

        async def operation(cursor: _AgentCursor) -> None:
            await cursor.execute(
                """
                insert into agent_runs (
                    id,
                    goal,
                    status,
                    step_count,
                    max_steps,
                    version,
                    workspace_id
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do nothing
                returning id
                """,
                _run_params(run),
            )
            if await cursor.fetchone() is None:
                raise AgentRunConflictError(run.id)

        await self._execute(operation)

    async def get(self, run_id: UUID) -> AgentRun:
        """Load the current state of one agent run."""

        async def operation(cursor: _AgentCursor) -> AgentRun:
            await cursor.execute(
                f"""
                select {_RUN_COLUMNS}
                from agent_runs
                where id = %s
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise AgentRunNotFoundError(run_id)
            return _read_run(row)

        return await self._execute(operation)

    async def update(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Update one locked run when its version matches the caller."""

        async def operation(cursor: _AgentCursor) -> None:
            await _lock_and_validate_run(
                cursor,
                run,
                expected_version=expected_version,
            )
            await _update_run(cursor, run)

        await self._execute(operation)

    async def cancel_run(
        self,
        run: AgentRun,
        *,
        expected_version: int,
    ) -> None:
        """Atomically cancel a run and close any active proposal."""

        async def operation(cursor: _AgentCursor) -> None:
            await _lock_and_validate_run(
                cursor,
                run,
                expected_version=expected_version,
            )
            await _update_run(cursor, run)
            await cursor.execute(
                """
                update agent_tool_proposals
                set
                    closed_at = now(),
                    updated_at = now()
                where run_id = %s
                  and closed_at is null
                """,
                (run.id,),
            )

        await self._execute(operation)

    async def update_proposal(
        self,
        proposal: ToolProposal,
        *,
        expected_version: int,
    ) -> None:
        """Atomically update a run and insert or resolve its active proposal."""

        async def operation(cursor: _AgentCursor) -> None:
            await _lock_and_validate_run(
                cursor,
                proposal.run,
                expected_version=expected_version,
            )
            await _update_run(cursor, proposal.run)
            await _upsert_proposal(cursor, proposal)

        await self._execute(operation)

    async def get_proposal(self, run_id: UUID) -> ToolProposal:
        """Load the active proposal and its current run state."""

        async def operation(cursor: _AgentCursor) -> ToolProposal:
            await cursor.execute(
                f"""
                select
                    p.tool_call_id,
                    p.tool_name,
                    p.arguments,
                    p.reason,
                    p.expected_effect,
                    p.risk,
                    p.policy_decision,
                    p.policy_reason,
                    p.approval_status,
                    p.approval_decided_by,
                    p.approval_decided_at,
                    {_PREFIXED_RUN_COLUMNS}
                from agent_tool_proposals p
                join agent_runs r on r.id = p.run_id
                where p.run_id = %s
                  and p.closed_at is null
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                await _ensure_run_exists(cursor, run_id)
                raise AgentProposalNotFoundError(run_id)
            return _read_proposal(row)

        return await self._execute(operation)

    async def complete_proposal(
        self,
        run: AgentRun,
        result: ToolExecutionResult,
        *,
        expected_version: int,
    ) -> None:
        """Atomically store a result, update the run, and close its proposal."""

        async def operation(cursor: _AgentCursor) -> None:
            await _lock_and_validate_run(
                cursor,
                run,
                expected_version=expected_version,
            )
            await cursor.execute(
                """
                select tool_call_id
                from agent_tool_proposals
                where run_id = %s
                  and closed_at is null
                for update
                """,
                (run.id,),
            )
            proposal_row = await cursor.fetchone()
            if proposal_row is None:
                raise AgentProposalNotFoundError(run.id)
            if _read_uuid(proposal_row[0]) != result.tool_call_id:
                raise AgentRunConflictError(run.id)

            await _update_run(cursor, run)
            await cursor.execute(
                """
                insert into agent_tool_results (
                    run_id,
                    tool_call_id,
                    tool_name,
                    succeeded,
                    output,
                    error,
                    truncated,
                    duration_ms
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (tool_call_id) do nothing
                returning id
                """,
                (
                    run.id,
                    result.tool_call_id,
                    result.tool_name,
                    result.succeeded,
                    result.output,
                    result.error,
                    result.truncated,
                    result.duration_ms,
                ),
            )
            if await cursor.fetchone() is None:
                raise AgentRunConflictError(run.id)
            await cursor.execute(
                """
                update agent_tool_proposals
                set
                    closed_at = now(),
                    updated_at = now()
                where run_id = %s
                  and tool_call_id = %s
                  and closed_at is null
                """,
                (run.id, result.tool_call_id),
            )

        await self._execute(operation)

    async def get_result(self, run_id: UUID) -> ToolExecutionResult:
        """Load the most recent tool execution result for one run."""

        async def operation(cursor: _AgentCursor) -> ToolExecutionResult:
            await cursor.execute(
                """
                select
                    tool_call_id,
                    tool_name,
                    succeeded,
                    output,
                    error,
                    truncated,
                    duration_ms
                from agent_tool_results
                where run_id = %s
                order by created_at desc
                limit 1
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                await _ensure_run_exists(cursor, run_id)
                raise AgentResultNotFoundError(run_id)
            return _read_result(row)

        return await self._execute(operation)

    async def _execute(
        self,
        operation: Callable[[_AgentCursor], Awaitable[_T]],
    ) -> _T:
        if self._settings.database_url is None:
            raise AgentRunStoreConfigurationError("Database URL is not configured")
        try:
            connection = await psycopg.AsyncConnection.connect(
                self._settings.database_url,
                connect_timeout=self._settings.database_connect_timeout,
            )
            async with connection:
                async with connection.cursor() as cursor:
                    return await operation(cast(_AgentCursor, cursor))
        except AgentRunStoreError:
            raise
        except Exception as exc:
            LOGGER.warning("PostgreSQL agent run store failed: %s", exc)
            raise AgentRunStoreUnavailableError(
                "PostgreSQL agent run store is unavailable"
            ) from exc


_RUN_COLUMNS = """
    id,
    goal,
    status,
    step_count,
    max_steps,
    version,
    workspace_id
"""

_PREFIXED_RUN_COLUMNS = """
    r.id,
    r.goal,
    r.status,
    r.step_count,
    r.max_steps,
    r.version,
    r.workspace_id
"""


def _run_params(run: AgentRun) -> tuple[object, ...]:
    return (
        run.id,
        run.goal,
        run.status.value,
        run.step_count,
        run.max_steps,
        run.version,
        run.workspace_id,
    )


async def _lock_and_validate_run(
    cursor: _AgentCursor,
    run: AgentRun,
    *,
    expected_version: int,
) -> None:
    await cursor.execute(
        """
        select version
        from agent_runs
        where id = %s
        for update
        """,
        (run.id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise AgentRunNotFoundError(run.id)
    stored_version = _read_int(row[0])
    if stored_version != expected_version or run.version != expected_version + 1:
        raise AgentRunConflictError(run.id)


async def _update_run(cursor: _AgentCursor, run: AgentRun) -> None:
    await cursor.execute(
        """
        update agent_runs
        set
            goal = %s,
            status = %s,
            step_count = %s,
            max_steps = %s,
            version = %s,
            workspace_id = %s,
            updated_at = now()
        where id = %s
        """,
        (
            run.goal,
            run.status.value,
            run.step_count,
            run.max_steps,
            run.version,
            run.workspace_id,
            run.id,
        ),
    )


async def _upsert_proposal(
    cursor: _AgentCursor,
    proposal: ToolProposal,
) -> None:
    approval = proposal.approval
    closed = proposal.run.status.is_terminal
    await cursor.execute(
        """
        insert into agent_tool_proposals (
            tool_call_id,
            run_id,
            tool_name,
            arguments,
            reason,
            expected_effect,
            risk,
            policy_decision,
            policy_reason,
            approval_status,
            approval_decided_by,
            approval_decided_at,
            closed_at
        )
        values (
            %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s,
            case when %s then now() else null end
        )
        on conflict (tool_call_id) do update
        set
            tool_name = excluded.tool_name,
            arguments = excluded.arguments,
            reason = excluded.reason,
            expected_effect = excluded.expected_effect,
            risk = excluded.risk,
            policy_decision = excluded.policy_decision,
            policy_reason = excluded.policy_reason,
            approval_status = excluded.approval_status,
            approval_decided_by = excluded.approval_decided_by,
            approval_decided_at = excluded.approval_decided_at,
            updated_at = now(),
            closed_at = excluded.closed_at
        where agent_tool_proposals.run_id = excluded.run_id
        returning tool_call_id
        """,
        (
            proposal.call.id,
            proposal.run.id,
            proposal.call.name,
            json.dumps(_thaw_json(proposal.call.arguments), ensure_ascii=False),
            proposal.call.reason,
            proposal.call.expected_effect,
            proposal.call.risk.value,
            proposal.policy_result.decision.value,
            proposal.policy_result.reason,
            approval.decision.value if approval is not None else None,
            approval.decided_by if approval is not None else None,
            approval.decided_at if approval is not None else None,
            closed,
        ),
    )
    if await cursor.fetchone() is None:
        raise AgentRunConflictError(proposal.run.id)


async def _ensure_run_exists(cursor: _AgentCursor, run_id: UUID) -> None:
    await cursor.execute(
        "select id from agent_runs where id = %s",
        (run_id,),
    )
    if await cursor.fetchone() is None:
        raise AgentRunNotFoundError(run_id)


def _read_run(row: tuple[object, ...]) -> AgentRun:
    return AgentRun(
        id=_read_uuid(row[0]),
        goal=str(row[1]),
        status=AgentStatus(str(row[2])),
        step_count=_read_int(row[3]),
        max_steps=_read_int(row[4]),
        version=_read_int(row[5]),
        workspace_id=str(row[6]) if row[6] is not None else None,
    )


def _read_proposal(row: tuple[object, ...]) -> ToolProposal:
    call_id = _read_uuid(row[0])
    approval_status = row[8]
    approval = (
        _read_approval(
            call_id,
            approval_status,
            row[9],
            row[10],
        )
        if approval_status is not None
        else None
    )
    return ToolProposal(
        run=_read_run(row[11:18]),
        call=ToolCall(
            id=call_id,
            name=str(row[1]),
            arguments=_read_json_mapping(row[2]),
            reason=str(row[3]),
            expected_effect=str(row[4]),
            risk=ToolRisk(str(row[5])),
        ),
        policy_result=ToolPolicyResult(
            decision=ToolPolicyDecision(str(row[6])),
            reason=str(row[7]),
        ),
        approval=approval,
    )


def _read_approval(
    call_id: UUID,
    status: object,
    decided_by: object,
    decided_at: object,
) -> ToolApproval:
    decision = ApprovalDecision(str(status))
    if decision is ApprovalDecision.PENDING:
        return ToolApproval(tool_call_id=call_id)
    if not isinstance(decided_at, datetime):
        raise AgentRunStoreUnavailableError(
            "PostgreSQL returned invalid approval metadata"
        )
    return ToolApproval(
        tool_call_id=call_id,
        decision=decision,
        decided_by=str(decided_by) if decided_by is not None else None,
        decided_at=decided_at,
    )


def _read_result(row: tuple[object, ...]) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool_call_id=_read_uuid(row[0]),
        tool_name=str(row[1]),
        succeeded=_read_bool(row[2]),
        output=str(row[3]),
        error=str(row[4]) if row[4] is not None else None,
        truncated=_read_bool(row[5]),
        duration_ms=_read_int(row[6]),
    )


def _read_json_mapping(value: object) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise AgentRunStoreUnavailableError(
            "PostgreSQL returned invalid tool arguments"
        )
    return MappingProxyType(
        {str(key): _freeze_json(item) for key, item in value.items()}
    )


def _freeze_json(value: object) -> JsonValue:
    if isinstance(value, dict):
        return _read_json_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise AgentRunStoreUnavailableError("PostgreSQL returned non-JSON tool arguments")


def _thaw_json(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _read_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _read_int(value: object) -> int:
    if isinstance(value, bool):
        raise AgentRunStoreUnavailableError("PostgreSQL returned an invalid integer")
    return int(str(value))


def _read_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise AgentRunStoreUnavailableError("PostgreSQL returned an invalid boolean")
    return value
