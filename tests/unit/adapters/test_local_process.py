"""Unit tests for the shell-free async local process adapter."""

import asyncio
import sys
from pathlib import Path

import pytest

from kelvin_assistant.adapters.local_process import AsyncLocalProcessRunner
from kelvin_assistant.ports.processes import ProcessRequest


def test_local_process_runner_executes_structured_arguments() -> None:
    """The adapter captures stdout from an executable without a shell."""

    async def scenario() -> None:
        runner = AsyncLocalProcessRunner()

        result = await runner.run(
            ProcessRequest(
                executable=sys.executable,
                arguments=("-c", "print('kelvin-process-ok')"),
                cwd=Path.cwd(),
                timeout_seconds=5,
            )
        )

        assert result.return_code == 0
        assert result.stdout.strip() == "kelvin-process-ok"
        assert result.stderr == ""
        assert result.duration_ms >= 0

    asyncio.run(scenario())


def test_local_process_runner_kills_cancelled_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task cancellation cannot leave a child process running."""

    class FakeProcess:
        returncode = 0

        def __init__(self) -> None:
            self.communicate_calls = 0
            self.killed = False

        async def communicate(self) -> tuple[bytes, bytes]:
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                await asyncio.Event().wait()
            return b"", b""

        def kill(self) -> None:
            self.killed = True

    process = FakeProcess()

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return process

    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        create_process,
    )

    async def scenario() -> None:
        runner = AsyncLocalProcessRunner()
        task = asyncio.create_task(
            runner.run(
                ProcessRequest(
                    executable="git",
                    arguments=("status",),
                    cwd=Path.cwd(),
                    timeout_seconds=5,
                )
            )
        )
        await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    assert process.killed
    assert process.communicate_calls == 2
