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
