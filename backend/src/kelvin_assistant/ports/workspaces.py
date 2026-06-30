"""Authorization port for configured agent workspaces."""

from typing import Protocol


class WorkspaceAuthorizer(Protocol):
    """Determine whether an opaque workspace identifier is configured."""

    def is_authorized(self, workspace_id: str | None) -> bool:
        """Return whether tools may target the workspace identifier."""
        ...
