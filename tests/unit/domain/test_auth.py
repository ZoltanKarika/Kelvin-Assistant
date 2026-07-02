"""Unit tests for scoped API authentication domain models."""

import pytest

from kelvin_assistant.domain.auth import (
    ApiAuthError,
    ApiPrincipal,
    ApiScope,
    StoredApiToken,
)


def test_api_principal_normalizes_id_and_freezes_scopes() -> None:
    """Principal IDs are trimmed and scope collections are immutable."""

    principal = ApiPrincipal(
        id=" n8n-research ",
        scopes=frozenset({ApiScope.SYSTEM_READ, ApiScope.CHAT_USE}),
    )

    assert principal.id == "n8n-research"
    assert principal.scopes == frozenset({ApiScope.SYSTEM_READ, ApiScope.CHAT_USE})
    assert principal.has_scope(ApiScope.CHAT_USE) is True
    assert principal.has_scope(ApiScope.AGENT_APPROVE) is False


@pytest.mark.parametrize(
    "principal_id",
    [
        "",
        "N8N",
        "1-client",
        "contains_space",
        "a" * 65,
    ],
)
def test_api_principal_rejects_invalid_id(principal_id: str) -> None:
    """Principal IDs use a small predictable audit-safe character set."""

    with pytest.raises(ApiAuthError, match="principal ID"):
        ApiPrincipal(
            id=principal_id,
            scopes=frozenset({ApiScope.SYSTEM_READ}),
        )


def test_api_principal_requires_at_least_one_scope() -> None:
    """A configured principal cannot authenticate with no capabilities."""

    with pytest.raises(ApiAuthError, match="at least one scope"):
        ApiPrincipal(id="empty-client", scopes=frozenset())


@pytest.mark.parametrize(
    "digest",
    [
        "",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
    ],
)
def test_stored_api_token_requires_lowercase_sha256_digest(digest: str) -> None:
    """Stored tokens accept only canonical SHA-256 hexadecimal digests."""

    principal = ApiPrincipal(
        id="n8n-research",
        scopes=frozenset({ApiScope.SYSTEM_READ}),
    )

    with pytest.raises(ApiAuthError, match="64 lowercase hexadecimal"):
        StoredApiToken(principal=principal, token_sha256=digest)
