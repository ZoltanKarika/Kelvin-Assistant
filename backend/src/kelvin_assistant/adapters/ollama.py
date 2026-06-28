"""Ollama language model adapter."""

import logging

import httpx2

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.ports.llm import (
    LLMProvider,
    LLMResponseError,
    LLMUnavailableError,
)

LOGGER = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider backed by Ollama."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the adapter with injectable runtime dependencies."""

        self.settings = settings or get_settings()
        self._transport = transport

    async def generate(self, prompt: str) -> str:
        """Generate a response using the configured Ollama model."""

        try:
            async with httpx2.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self.settings.ollama_timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    "/api/generate",
                    json={
                        "model": self.settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
            response.raise_for_status()
        except httpx2.RequestError as exc:
            LOGGER.warning("Ollama runtime is unavailable: %s", exc)
            raise LLMUnavailableError("Ollama runtime is unavailable") from exc
        except httpx2.HTTPStatusError as exc:
            status_code = exc.response.status_code
            LOGGER.warning("Ollama returned HTTP status %d", status_code)
            raise LLMResponseError(
                f"Ollama returned HTTP status {status_code}"
            ) from exc

        try:
            data = response.json()
            result = data["response"]
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Ollama returned an invalid response body")
            raise LLMResponseError("Ollama returned an invalid response") from exc

        if not isinstance(result, str):
            LOGGER.warning("Ollama response field is not text")
            raise LLMResponseError("Ollama returned an invalid response")

        return result
