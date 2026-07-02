"""Domain models for scoped Kelvin API authentication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_TOKEN_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class ApiAuthError(ValueError):
    """Raised when API authentication data violates domain rules."""


class ApiScope(StrEnum):
    """One explicit Kelvin API capability."""

    SYSTEM_READ = "system:read"
    CHAT_USE = "chat:use"
    KNOWLEDGE_READ = "knowledge:read"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    AGENT_EXECUTE = "agent:execute"
    AGENT_WRITE = "agent:write"
    AGENT_APPROVE = "agent:approve"


@dataclass(frozen=True, slots=True)
class ApiPrincipal:
    """Authenticated machine identity and its exact API scopes."""

    id: str
    scopes: frozenset[ApiScope]

    def __post_init__(self) -> None:
        """Normalize and validate the principal."""

        principal_id = self.id.strip()
        scopes = frozenset(self.scopes)

        if _TOKEN_ID_PATTERN.fullmatch(principal_id) is None:
            raise ApiAuthError(
                "API principal ID must start with a lowercase letter and contain "
                "only lowercase letters, digits, or hyphens"
            )
        if not scopes:
            raise ApiAuthError("API principal must have at least one scope")

        object.__setattr__(self, "id", principal_id)
        object.__setattr__(self, "scopes", scopes)

    def has_scope(self, scope: ApiScope) -> bool:
        """Return whether the principal has the exact requested scope."""

        return scope in self.scopes


@dataclass(frozen=True, slots=True)
class StoredApiToken:
    """A principal bound to the SHA-256 digest of an opaque token."""

    principal: ApiPrincipal
    token_sha256: str

    def __post_init__(self) -> None:
        """Validate the stored token digest."""

        if _SHA256_PATTERN.fullmatch(self.token_sha256) is None:
            raise ApiAuthError(
                "Stored API token digest must be 64 lowercase hexadecimal characters"
            )
