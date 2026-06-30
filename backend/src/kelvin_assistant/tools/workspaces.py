"""Static allowlist for server-configured agent workspace identifiers."""

from collections.abc import Iterable


class StaticWorkspaceAuthorizer:
    """Authorize opaque workspace identifiers from local configuration."""

    def __init__(self, workspace_ids: Iterable[str] = ()) -> None:
        """Create an immutable normalized workspace allowlist."""

        self._workspace_ids = frozenset(
            workspace_id.strip()
            for workspace_id in workspace_ids
            if workspace_id.strip()
        )

    def is_authorized(self, workspace_id: str | None) -> bool:
        """Return whether the identifier exists in the allowlist."""

        return workspace_id is not None and workspace_id in self._workspace_ids
