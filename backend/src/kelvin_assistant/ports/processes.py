"""Port for safe local process execution without a shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProcessRunnerError(RuntimeError):
    """Base error raised by local process runners."""


class ProcessTimeoutError(ProcessRunnerError):
    """Raised when a local process exceeds its configured timeout."""


class ProcessUnavailableError(ProcessRunnerError):
    """Raised when a configured executable cannot be started."""


@dataclass(frozen=True, slots=True)
class ProcessRequest:
    """A structured process request that never contains shell text."""

    executable: str
    arguments: tuple[str, ...]
    cwd: Path
    timeout_seconds: int

    def __post_init__(self) -> None:
        """Validate process request boundaries."""

        if not self.executable.strip():
            raise ValueError("Process executable cannot be empty")
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            raise ValueError("Process timeout must be between 1 and 300 seconds")


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """Captured process output and timing."""

    return_code: int
    stdout: str
    stderr: str
    duration_ms: int


class ProcessRunner(Protocol):
    """Execute a structured process request without invoking a shell."""

    async def run(self, request: ProcessRequest) -> ProcessResult:
        """Execute one process and return its captured result."""
        ...
