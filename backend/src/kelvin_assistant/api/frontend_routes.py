"""Routes for the bundled browser interface."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "web"

router = APIRouter(tags=["frontend"], include_in_schema=False)


@router.get("/ui", response_class=FileResponse)
def read_chat_ui() -> FileResponse:
    """Return the entry page for the bundled chat interface."""

    return FileResponse(FRONTEND_DIR / "index.html")


@router.get("/ui/runs", response_class=FileResponse)
def read_runs_ui() -> FileResponse:
    """Return the entry page for the runs dashboard."""

    return FileResponse(FRONTEND_DIR / "runs.html")


@router.get("/ui/approvals", response_class=FileResponse)
def read_approvals_ui() -> FileResponse:
    """Return the entry page for the approvals queue."""

    return FileResponse(FRONTEND_DIR / "approvals.html")


@router.get("/ui/audit", response_class=FileResponse)
def read_audit_ui() -> FileResponse:
    """Return the entry page for the audit log viewer."""

    return FileResponse(FRONTEND_DIR / "audit.html")


@router.get("/ui/settings", response_class=FileResponse)
def read_settings_ui() -> FileResponse:
    """Return the entry page for the settings panel."""

    return FileResponse(FRONTEND_DIR / "settings.html")


@router.get("/ui/n8n", response_class=FileResponse)
def read_n8n_ui() -> FileResponse:
    """Return the entry page for the n8n status panel."""

    return FileResponse(FRONTEND_DIR / "n8n.html")
