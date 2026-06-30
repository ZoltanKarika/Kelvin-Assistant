"""Async local process runner using structured arguments and no shell."""

from __future__ import annotations

import asyncio
import subprocess
from time import monotonic

from kelvin_assistant.ports.processes import (
    ProcessRequest,
    ProcessResult,
    ProcessTimeoutError,
    ProcessUnavailableError,
)


class AsyncLocalProcessRunner:
    """Run local executables with captured output and a hard timeout."""

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Execute one request with create_subprocess_exec."""

        started_at = monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                request.executable,
                *request.arguments,
                cwd=str(request.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise ProcessUnavailableError(
                f"Cannot start executable '{request.executable}'"
            ) from exc

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=request.timeout_seconds,
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ProcessTimeoutError(
                f"Process timed out after {request.timeout_seconds} seconds"
            ) from exc

        duration_ms = int((monotonic() - started_at) * 1_000)
        return ProcessResult(
            return_code=process.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
        )
