"""FastAPI dependencies."""

from fastapi import Request

from kelvin_assistant.config.settings import Settings


def get_runtime_settings(request: Request) -> Settings:
    """Return the settings object attached to the app state."""

    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        msg = "Application settings are not configured."
        raise RuntimeError(msg)
    return settings

