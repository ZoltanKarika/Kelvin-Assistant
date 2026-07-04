from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SanitizedContent:
    """Represents content that has been sanitized for safe use with an LLM."""

    text: str
    """The sanitized and wrapped text content."""

    injection_warnings: list[str] = field(default_factory=list)
    """A list of potential prompt injection patterns detected."""

    source_url: str | None = None
    """The original source URL of the content, if available."""

    fetched_at: datetime | None = None
    """The timestamp when the content was fetched."""


SECRET_PATTERNS = {
    "api_key_sk": r"sk-[a-zA-Z0-9]{20,}",
    "github_token": r"ghp_[a-zA-Z0-9]{36}",
    "postgres_conn_string": r"postgres(ql)?://[^:]+:[^@]+@[^\s]+",
    "env_secret_key": r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]",
    "pem_block": (
        r"-----BEGIN[A-Z\s]+PRIVATE KEY-----"
        r".*"
        r"-----END[A-Z\s]+PRIVATE KEY-----"
    ),
}

INJECTION_PATTERNS = {
    "ignore_instructions": r"ignore.*previous.*instructions",
    "system_prompt_marker": r"system:",
    "tool_code_xml": r"</?tool_code>",
}


def mask_secrets(text: str) -> str:
    """Masks common secret patterns in a string."""
    masked_text = text
    for key, pattern in SECRET_PATTERNS.items():
        flags = re.IGNORECASE
        if key == "pem_block":
            flags |= re.DOTALL
        masked_text = re.sub(
            pattern, f"[MASKED_{key.upper()}]", masked_text, flags=flags
        )
    return masked_text


def detect_injection(text: str) -> list[str]:
    """Detects common prompt injection patterns."""
    warnings = []
    for key, pattern in INJECTION_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(key)
    return warnings


def sanitize_external_content(
    text: str,
    source_url: str | None = None,
    fetched_at: datetime | None = None,
) -> SanitizedContent:
    """
    Sanitizes external content by masking secrets, detecting injections,
    and wrapping it in data delimiters."""
    warnings = detect_injection(text)
    masked_text = mask_secrets(text)

    wrapped_text = f"""--- BEGIN EXTERNAL DATA ---
{masked_text}
--- END EXTERNAL DATA ---"""

    return SanitizedContent(
        text=wrapped_text,
        injection_warnings=warnings,
        source_url=source_url,
        fetched_at=fetched_at,
    )


def is_source_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    """Checks if a URL is allowed based on a list of approved prefixes."""
    if not allowlist:
        return False

    for prefix in allowlist:
        if url.startswith(prefix):
            if len(url) == len(prefix) or url[len(prefix)] == "/":
                return True
    return False
