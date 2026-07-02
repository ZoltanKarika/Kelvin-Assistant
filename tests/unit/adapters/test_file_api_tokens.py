"""Unit tests for the hashed JSON API token adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kelvin_assistant.adapters.file_api_tokens import (
    FileApiTokenAuthenticator,
    hash_api_token,
)
from kelvin_assistant.domain.auth import ApiScope
from kelvin_assistant.ports.auth import ApiTokenConfigurationError

RAW_TOKEN = "kelvin-test-" + ("a" * 64)


def test_file_authenticator_loads_and_authenticates_valid_token(
    tmp_path: Path,
) -> None:
    """A valid raw token resolves to the configured scoped principal."""

    path = _write_configuration(tmp_path)
    authenticator = FileApiTokenAuthenticator.from_file(path)

    principal = authenticator.authenticate(RAW_TOKEN)

    assert principal is not None
    assert principal.id == "n8n-research"
    assert principal.scopes == frozenset(
        {
            ApiScope.SYSTEM_READ,
            ApiScope.CHAT_USE,
            ApiScope.KNOWLEDGE_READ,
        }
    )
    assert authenticator.authenticate("wrong-token") is None


def test_authenticator_uses_timing_safe_digest_comparison(tmp_path: Path) -> None:
    """Token verification delegates digest equality to compare_digest."""

    authenticator = FileApiTokenAuthenticator.from_file(_write_configuration(tmp_path))

    with patch(
        "kelvin_assistant.adapters.file_api_tokens.compare_digest",
        return_value=False,
    ) as timing_safe_compare:
        assert authenticator.authenticate("wrong-token") is None

    timing_safe_compare.assert_called_once()


@pytest.mark.parametrize(
    "token",
    [
        "",
        "ékezetes-token",
        "a" * 513,
    ],
)
def test_authenticator_rejects_invalid_bearer_token_without_hashing(
    tmp_path: Path,
    token: str,
) -> None:
    """Malformed bearer values fail closed before digest comparison."""

    authenticator = FileApiTokenAuthenticator.from_file(_write_configuration(tmp_path))

    with patch(
        "kelvin_assistant.adapters.file_api_tokens.hash_api_token"
    ) as token_hasher:
        assert authenticator.authenticate(token) is None

    token_hasher.assert_not_called()


def test_hash_api_token_returns_canonical_sha256() -> None:
    """Token hashing is deterministic and produces lowercase hexadecimal."""

    digest = hash_api_token("kelvin-test-token")

    assert digest == (
        "afd8e3def9a2aa31efeb7fae918e3872fc031a24c0b7215c046dc3a9e2851aa1"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", 2, "version must be 1"),
        ("tokens", [], "at least one token"),
        ("tokens", "not-an-array", "must be an array"),
    ],
)
def test_configuration_rejects_invalid_top_level_values(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    """Version and token collection failures produce safe config errors."""

    payload = _valid_payload()
    payload[field] = value
    path = _write_payload(tmp_path, payload)

    with pytest.raises(ApiTokenConfigurationError, match=message):
        FileApiTokenAuthenticator.from_file(path)


def test_configuration_rejects_unknown_scope_without_leaking_digest(
    tmp_path: Path,
) -> None:
    """Unknown capabilities fail closed without including token hashes."""

    payload = _valid_payload()
    records = payload["tokens"]
    assert isinstance(records, list)
    record = records[0]
    assert isinstance(record, dict)
    record["scopes"] = ["system:read", "root:everything"]
    path = _write_payload(tmp_path, payload)

    with pytest.raises(
        ApiTokenConfigurationError,
        match="Unknown API scope",
    ) as error:
        FileApiTokenAuthenticator.from_file(path)

    assert hash_api_token(RAW_TOKEN) not in str(error.value)


def test_configuration_rejects_plaintext_token_field(tmp_path: Path) -> None:
    """A raw token cannot accidentally be stored in Kelvin configuration."""

    payload = _valid_payload()
    records = payload["tokens"]
    assert isinstance(records, list)
    record = records[0]
    assert isinstance(record, dict)
    record["token"] = RAW_TOKEN
    path = _write_payload(tmp_path, payload)

    with pytest.raises(
        ApiTokenConfigurationError,
        match="unsupported fields",
    ) as error:
        FileApiTokenAuthenticator.from_file(path)

    assert RAW_TOKEN not in str(error.value)


@pytest.mark.parametrize("duplicate_field", ["id", "token_sha256"])
def test_configuration_rejects_duplicate_records(
    tmp_path: Path,
    duplicate_field: str,
) -> None:
    """Principal IDs and token digests are unique audit identities."""

    payload = _valid_payload()
    records = payload["tokens"]
    assert isinstance(records, list)
    first = records[0]
    assert isinstance(first, dict)
    second = {
        "id": "windows-client",
        "token_sha256": hash_api_token("different-token"),
        "scopes": ["agent:execute"],
    }
    second[duplicate_field] = first[duplicate_field]
    records.append(second)
    path = _write_payload(tmp_path, payload)

    with pytest.raises(ApiTokenConfigurationError, match="duplicate"):
        FileApiTokenAuthenticator.from_file(path)


def test_configuration_rejects_missing_and_malformed_file(tmp_path: Path) -> None:
    """Unreadable or malformed configuration fails closed."""

    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ApiTokenConfigurationError, match="Cannot read"):
        FileApiTokenAuthenticator.from_file(missing)
    with pytest.raises(ApiTokenConfigurationError, match="not valid JSON"):
        FileApiTokenAuthenticator.from_file(malformed)


def _write_configuration(tmp_path: Path) -> Path:
    return _write_payload(tmp_path, _valid_payload())


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "api-tokens.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_payload() -> dict[str, object]:
    return {
        "version": 1,
        "tokens": [
            {
                "id": "n8n-research",
                "token_sha256": hash_api_token(RAW_TOKEN),
                "scopes": [
                    "system:read",
                    "chat:use",
                    "knowledge:read",
                ],
            }
        ],
    }
