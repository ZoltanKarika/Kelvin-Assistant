"""Authentication boundary for scoped Kelvin API tokens."""

from __future__ import annotations

from typing import Protocol

from kelvin_assistant.domain.auth import ApiPrincipal


class ApiTokenConfigurationError(RuntimeError):
    """Raised when the API token configuration cannot be trusted."""


class ApiTokenAuthenticator(Protocol):
    """Authenticate opaque API tokens without exposing stored secrets."""

    def authenticate(self, token: str) -> ApiPrincipal | None:
        """Return the matching principal, or None for an invalid token."""

        ...
