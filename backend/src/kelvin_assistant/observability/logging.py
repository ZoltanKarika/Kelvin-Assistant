"""Structured logging utilities."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from kelvin_assistant.config.settings import Settings


class JsonFormatter(logging.Formatter):
    """Format log records as compact JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "kelvin-assistant",
        }
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class ConsoleFormatter(logging.Formatter):
    """Human readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        return f"{timestamp} | {record.levelname:<8} | {record.name} | {record.getMessage()}"


def configure_logging(settings: Settings) -> None:
    """Configure application logging once at process startup."""

    handler = logging.StreamHandler(sys.stdout)
    formatter: logging.Formatter
    if settings.log_format.lower() == "console":
        formatter = ConsoleFormatter()
    else:
        formatter = JsonFormatter()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
    logging.captureWarnings(True)

