"""Unit tests for the PostgreSQL agent run store."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

import kelvin_assistant.adapters.postgres_agent_runs as adapter_module
from kelvin_assistant.adapters.postgres_agent_runs import PostgresAgentRunStore
from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.agent import (
    AgentRun,
    AgentStatus,
    ApprovalDecision,
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
    AgentRunConflictError,
    AgentRunNotFoundError,
    AgentRunStoreConfigurationError,
)

RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
CALL_ID = UUID("22222222-2222-4222-8222-222222222222")
RESULT_ID = UUID("33333333-3333-4333-8333-333333333333")
DECIDED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def test_store_requires_database_url() -> None:
    """Persistent agent storage fails explicitly without configuration."""

    store = PostgresAgentRunStore(Settings(environment="test"))

    with pytest.raises(
        AgentRunStoreConfigurationError,
        match="Database URL",
    ):
        asyncio.run(store.get(RUN_ID))


def test_app_uses_postgres_store_when_database_is_configured() -> None:
    """Production-style settings replace the in-memory agent store."""

    app = create_app(settings=_settings())

    assert isinstance(app.state.agent_run_store, PostgresAgentRunStore)


def test_add_inserts_complete_run_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new run stores all concurrency and workspace fields."""

    cursor = FakeCursor(rows=[(RUN_ID,)])
    _install_fake_psycopg(monkeypatch, cursor)
    store = PostgresAgentRunStore(_settings())
    run = _run(AgentStatus.RECEIVED, version=0)

    asyncio.run(store.add(run))

    assert len(cursor.executed) == 1
    assert "insert into agent_runs" in cursor.executed[0].sql
    assert "on conflict (id) do nothing" in cursor.executed[0].sql
    assert cursor.executed[0].params == (
        RUN_ID,
        "Inspect the project.",
        "received",
        0,
        12,
        0,
        "kelvin-assistant",
    )


def test_add_rejects_duplicate_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate insert cannot silently overwrite audit history."""

    cursor = FakeCursor(rows=[None])
    _install_fake_psycopg(monkeypatch, cursor)

    with pytest.raises(AgentRunConflictError):
        asyncio.run(
            PostgresAgentRunStore(_settings()).add(
                _run(AgentStatus.RECEIVED, version=0)
            )
        )


def test_get_rebuilds_agent_domain_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stored scalar values are converted back into an AgentRun."""

    cursor = FakeCursor(rows=[_run_row(AgentStatus.PLANNING, version=1)])
    _install_fake_psycopg(monkeypatch, cursor)

    result = asyncio.run(PostgresAgentRunStore(_settings()).get(RUN_ID))

    assert result == _run(AgentStatus.PLANNING, version=1)
    assert cursor.executed[0].params == (RUN_ID,)


def test_get_rejects_unknown_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing rows retain the stable storage-port error contract."""

    cursor = FakeCursor(rows=[None])
    _install_fake_psycopg(monkeypatch, cursor)

    with pytest.raises(AgentRunNotFoundError):
        asyncio.run(PostgresAgentRunStore(_settings()).get(RUN_ID))


def test_update_locks_and_checks_expected_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid transition locks the row before updating its version."""

    cursor = FakeCursor(rows=[(0,)])
    _install_fake_psycopg(monkeypatch, cursor)
    store = PostgresAgentRunStore(_settings())

    asyncio.run(
        store.update(
            _run(AgentStatus.PLANNING, version=1),
            expected_version=0,
        )
    )

    assert len(cursor.executed) == 2
    assert "for update" in cursor.executed[0].sql
    assert "update agent_runs" in cursor.executed[1].sql
    assert cursor.executed[1].params[-1] == RUN_ID


def test_update_rejects_stale_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale caller loses before any update statement is issued."""

    cursor = FakeCursor(rows=[(2,)])
    _install_fake_psycopg(monkeypatch, cursor)
    store = PostgresAgentRunStore(_settings())

    with pytest.raises(AgentRunConflictError):
        asyncio.run(
            store.update(
                _run(AgentStatus.PLANNING, version=1),
                expected_version=0,
            )
        )

    assert len(cursor.executed) == 1


def test_update_proposal_persists_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run and structured proposal are written in one connection transaction."""

    cursor = FakeCursor(rows=[(1,), (CALL_ID,)])
    _install_fake_psycopg(monkeypatch, cursor)
    store = PostgresAgentRunStore(_settings())

    asyncio.run(
        store.update_proposal(
            _proposal(AgentStatus.AWAITING_APPROVAL, version=2),
            expected_version=1,
        )
    )

    assert len(cursor.executed) == 3
    proposal_call = cursor.executed[2]
    assert "insert into agent_tool_proposals" in proposal_call.sql
    assert proposal_call.params[0] == CALL_ID
    assert proposal_call.params[3] == (
        '{"path": "README.md", "old_text": "old", "new_text": "new"}'
    )
    assert proposal_call.params[9] == "pending"


def test_get_proposal_rebuilds_approved_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approval author and timestamp survive a repository round trip."""

    proposal_row = (
        CALL_ID,
        "file.patch",
        {"path": "README.md", "old_text": "old", "new_text": "new"},
        "Update documentation.",
        "Replace one exact value.",
        "write",
        "require_approval",
        "State-changing tools require explicit user approval.",
        "approved",
        "local-client",
        DECIDED_AT,
        *_run_row(AgentStatus.EXECUTING, version=3),
    )
    cursor = FakeCursor(rows=[proposal_row])
    _install_fake_psycopg(monkeypatch, cursor)

    proposal = asyncio.run(PostgresAgentRunStore(_settings()).get_proposal(RUN_ID))

    assert proposal.run.status is AgentStatus.EXECUTING
    assert proposal.call.id == CALL_ID
    assert proposal.call.arguments["path"] == "README.md"
    assert proposal.approval is not None
    assert proposal.approval == ToolApproval(
        tool_call_id=CALL_ID,
        decision=ApprovalDecision.APPROVED,
        decided_by="local-client",
        decided_at=DECIDED_AT,
    )


def test_get_proposal_distinguishes_missing_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing run and a run without an active proposal remain distinct."""

    cursor = FakeCursor(rows=[None, None])
    _install_fake_psycopg(monkeypatch, cursor)

    with pytest.raises(AgentRunNotFoundError):
        asyncio.run(PostgresAgentRunStore(_settings()).get_proposal(RUN_ID))


def test_get_proposal_reports_missing_active_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing run without an open proposal gets the proposal error."""

    cursor = FakeCursor(rows=[None, (RUN_ID,)])
    _install_fake_psycopg(monkeypatch, cursor)

    with pytest.raises(AgentProposalNotFoundError):
        asyncio.run(PostgresAgentRunStore(_settings()).get_proposal(RUN_ID))


def test_complete_proposal_stores_result_and_closes_active_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One transaction advances the run, audits output, and closes proposal."""

    cursor = FakeCursor(rows=[(3,), (CALL_ID,), (RESULT_ID,)])
    _install_fake_psycopg(monkeypatch, cursor)
    store = PostgresAgentRunStore(_settings())
    result = ToolExecutionResult(
        tool_call_id=CALL_ID,
        tool_name="file.patch",
        succeeded=True,
        output="Updated README.md",
        duration_ms=8,
    )

    asyncio.run(
        store.complete_proposal(
            _run(AgentStatus.OBSERVING, version=4),
            result,
            expected_version=3,
        )
    )

    assert len(cursor.executed) == 5
    assert "insert into agent_tool_results" in cursor.executed[3].sql
    assert cursor.executed[3].params == (
        RUN_ID,
        CALL_ID,
        "file.patch",
        True,
        "Updated README.md",
        None,
        False,
        8,
    )
    assert "closed_at = now()" in cursor.executed[4].sql


def test_get_result_rebuilds_execution_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The latest audited result maps back to the domain result."""

    cursor = FakeCursor(
        rows=[
            (
                CALL_ID,
                "git.status",
                True,
                "## main",
                None,
                False,
                5,
            )
        ]
    )
    _install_fake_psycopg(monkeypatch, cursor)

    result = asyncio.run(PostgresAgentRunStore(_settings()).get_result(RUN_ID))

    assert result == ToolExecutionResult(
        tool_call_id=CALL_ID,
        tool_name="git.status",
        succeeded=True,
        output="## main",
        duration_ms=5,
    )


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql://kelvin:secret@127.0.0.1/db",
        database_connect_timeout=2,
    )


def _run(status: AgentStatus, *, version: int) -> AgentRun:
    return AgentRun(
        id=RUN_ID,
        goal="Inspect the project.",
        status=status,
        step_count=1 if status in {AgentStatus.EXECUTING, AgentStatus.OBSERVING} else 0,
        version=version,
        workspace_id="kelvin-assistant",
    )


def _run_row(status: AgentStatus, *, version: int) -> tuple[object, ...]:
    run = _run(status, version=version)
    return (
        run.id,
        run.goal,
        run.status.value,
        run.step_count,
        run.max_steps,
        run.version,
        run.workspace_id,
    )


def _proposal(status: AgentStatus, *, version: int) -> ToolProposal:
    return ToolProposal(
        run=_run(status, version=version),
        call=ToolCall(
            id=CALL_ID,
            name="file.patch",
            arguments={
                "path": "README.md",
                "old_text": "old",
                "new_text": "new",
            },
            reason="Update documentation.",
            expected_effect="Replace one exact value.",
            risk=ToolRisk.WRITE,
        ),
        policy_result=ToolPolicyResult(
            decision=ToolPolicyDecision.REQUIRE_APPROVAL,
            reason="State-changing tools require explicit user approval.",
        ),
        approval=ToolApproval(tool_call_id=CALL_ID),
    )


def _install_fake_psycopg(
    monkeypatch: pytest.MonkeyPatch,
    cursor: "FakeCursor",
) -> None:
    connection = FakeConnection(cursor)
    fake_psycopg = SimpleNamespace(
        AsyncConnection=SimpleNamespace(
            connect=AsyncConnect(connection),
        )
    )
    monkeypatch.setattr(adapter_module, "psycopg", fake_psycopg)


class AsyncConnect:
    """Fake async psycopg connection factory."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    async def __call__(
        self,
        database_url: str,
        *,
        connect_timeout: int,
    ) -> "FakeConnection":
        assert database_url == "postgresql://kelvin:secret@127.0.0.1/db"
        assert connect_timeout == 2
        return self._connection


class FakeConnection:
    """Fake transaction context exposing one recording cursor."""

    def __init__(self, cursor: "FakeCursor") -> None:
        self._cursor = cursor

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return self._cursor


class FakeCursor:
    """Fake async cursor with ordered fetch responses."""

    def __init__(
        self,
        *,
        rows: list[tuple[object, ...] | None],
    ) -> None:
        self._rows = rows
        self.executed: list[SqlCall] = []

    async def __aenter__(self) -> "FakeCursor":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    async def execute(self, sql: str, params: tuple[object, ...]) -> None:
        self.executed.append(
            SqlCall(
                sql=" ".join(sql.split()),
                params=params,
            )
        )

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._rows.pop(0)

    async def fetchall(self) -> list[tuple[object, ...]]:
        return []


class SqlCall(SimpleNamespace):
    sql: str
    params: tuple[object, ...]
