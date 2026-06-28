"""Application entrypoint for the Kelvin Assistant API."""

from __future__ import annotations

import uvicorn

from kelvin_assistant.api.app import create_app
from kelvin_assistant.config.settings import get_settings

settings = get_settings()
app = create_app(settings)


def main() -> None:
    """Run the API server."""

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
