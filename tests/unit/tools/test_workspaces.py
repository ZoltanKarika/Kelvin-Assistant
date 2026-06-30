"""Unit tests for configured workspace authorization."""

from kelvin_assistant.tools.workspaces import StaticWorkspaceAuthorizer


def test_workspace_authorizer_uses_normalized_allowlist() -> None:
    """Only exact configured opaque identifiers are authorized."""

    authorizer = StaticWorkspaceAuthorizer([" kelvin-assistant ", "another-project"])

    assert authorizer.is_authorized("kelvin-assistant") is True
    assert authorizer.is_authorized("another-project") is True
    assert authorizer.is_authorized("unknown-project") is False
    assert authorizer.is_authorized(None) is False
