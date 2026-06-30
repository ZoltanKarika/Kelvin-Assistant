"""Unit tests for the shell-free async local process adapter."""

import asyncio
import sys
from pathlib import Path

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
