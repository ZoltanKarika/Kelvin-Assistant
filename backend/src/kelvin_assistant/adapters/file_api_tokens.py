"""JSON-file adapter for hashed, scope-limited API tokens."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from hmac import compare_digest
from pathlib import Path
from typing import cast

from kelvin_assistant.domain.auth import (
    ApiAuthError,
    ApiPrincipal,
    ApiScope,
    StoredApiToken,
)
from kelvin_assistant.ports.auth import ApiTokenConfigurationError

MAX_BEARER_TOKEN_LENGTH = 512
_TOP_LEVEL_KEYS = frozenset({"version", "tokens"})
_TOKEN_KEYS = frozenset({"id", "token_sha256", "scopes"})


class FileApiTokenAuthenticator:
    """Authenticate tokens against an immutable configuration snapshot."""

    def __init__(self, tokens: tuple[StoredApiToken, ...]) -> None:
        """Create an authenticator from validated stored token records."""

        if not tokens:
            raise ApiTokenConfigurationError(
                "API token configuration must contain at least one token"
            )
        _reject_duplicate_records(tokens)
        self._tokens = tokens

    @classmethod
    def from_file(cls, path: Path) -> FileApiTokenAuthenticator:
        """Load and validate a versioned JSON token configuration file."""

        try:
            serialized = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ApiTokenConfigurationError(
                f"Cannot read API token configuration: {path}"
            ) from exc

        try:
            payload: object = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ApiTokenConfigurationError(
                "API token configuration is not valid JSON"
            ) from exc

        return cls(_parse_configuration(payload))

    def authenticate(self, token: str) -> ApiPrincipal | None:
        """Return a principal for a valid token using timing-safe comparison."""

        if not token or len(token) > MAX_BEARER_TOKEN_LENGTH or not token.isascii():
            return None

        candidate_digest = hash_api_token(token)
        matched_principal: ApiPrincipal | None = None

        for stored_token in self._tokens:
            if compare_digest(candidate_digest, stored_token.token_sha256):
                matched_principal = stored_token.principal

        return matched_principal


def hash_api_token(token: str) -> str:
    """Return the lowercase SHA-256 digest for one opaque ASCII token."""

    if not token:
        raise ValueError("API token cannot be empty")
    if len(token) > MAX_BEARER_TOKEN_LENGTH:
        raise ValueError("API token is too long")
    if not token.isascii():
        raise ValueError("API token must contain ASCII characters only")

    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _parse_configuration(payload: object) -> tuple[StoredApiToken, ...]:
    document = _require_mapping(payload, "API token configuration")
    _reject_unknown_keys(document, _TOP_LEVEL_KEYS, "API token configuration")

    version = document.get("version")
    if version != 1:
        raise ApiTokenConfigurationError("API token configuration version must be 1")

    raw_tokens = _require_list(document.get("tokens"), "tokens")
    if not raw_tokens:
        raise ApiTokenConfigurationError(
            "API token configuration must contain at least one token"
        )

    return tuple(
        _parse_token_record(raw_token, index=index)
        for index, raw_token in enumerate(raw_tokens)
    )


def _parse_token_record(value: object, *, index: int) -> StoredApiToken:
    context = f"token record {index}"
    record = _require_mapping(value, context)
    _reject_unknown_keys(record, _TOKEN_KEYS, context)

    principal_id = _require_string(record.get("id"), f"{context} id")
    token_sha256 = _require_string(
        record.get("token_sha256"),
        f"{context} token_sha256",
    )
    raw_scopes = _require_list(record.get("scopes"), f"{context} scopes")

    try:
        scopes = frozenset(
            ApiScope(_require_string(raw_scope, f"{context} scope"))
            for raw_scope in raw_scopes
        )
        return StoredApiToken(
            principal=ApiPrincipal(id=principal_id, scopes=scopes),
            token_sha256=token_sha256,
        )
    except ApiAuthError as exc:
        raise ApiTokenConfigurationError(
            f"Invalid API authentication data in {context}: {exc}"
        ) from exc
    except ValueError as exc:
        raise ApiTokenConfigurationError(f"Unknown API scope in {context}") from exc


def _reject_duplicate_records(tokens: tuple[StoredApiToken, ...]) -> None:
    principal_ids = [token.principal.id for token in tokens]
    token_hashes = [token.token_sha256 for token in tokens]

    if len(principal_ids) != len(set(principal_ids)):
        raise ApiTokenConfigurationError(
            "API token configuration contains duplicate principal IDs"
        )
    if len(token_hashes) != len(set(token_hashes)):
        raise ApiTokenConfigurationError(
            "API token configuration contains duplicate token digests"
        )


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ApiTokenConfigurationError(f"{context} must be an object")
    return cast(dict[str, object], value)


def _require_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ApiTokenConfigurationError(f"{context} must be an array")
    return cast(list[object], value)


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ApiTokenConfigurationError(f"{context} must be a non-empty string")
    return value


def _reject_unknown_keys(
    value: Mapping[str, object],
    allowed: frozenset[str],
    context: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ApiTokenConfigurationError(f"{context} contains unsupported fields")
