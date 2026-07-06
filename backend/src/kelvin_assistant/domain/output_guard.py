import re

# Regex patterns for various secrets
_SECRET_PATTERNS: list[tuple[str, str]] = [
    # Bearer tokens
    (
        "bearer_token",
        r"\b(Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9-_.+/=]*)\b",
    ),
    # PEM private keys
    (
        "private_key",
        r"-----BEGIN[A-Z ]+PRIVATE KEY-----[\s\S]*?-----END[A-Z ]+PRIVATE KEY-----",
    ),
    # PostgreSQL connection strings
    (
        "postgres_url",
        r"postgres(ql)?://[a-zA-Z0-9_]+:[^@]+@[a-zA-Z0-9_.-]+:[0-9]+/[a-zA-Z0-9_]+",
    ),
    # Generic database connection strings with password
    ("db_connection_string", r"\w+://\w+:[^@\s]+@"),
]


def mask_secrets(text: str | None) -> str | None:
    """
    Masks common secret patterns in a given text.

    Args:
        text: The input string to sanitize.

    Returns:
        The sanitized string with secrets replaced by placeholders.
    """
    if text is None:
        return None

    sanitized_text = text
    for name, pattern in _SECRET_PATTERNS:
        sanitized_text = re.sub(pattern, f"[{name.upper()}_MASKED]", sanitized_text)

    return sanitized_text
