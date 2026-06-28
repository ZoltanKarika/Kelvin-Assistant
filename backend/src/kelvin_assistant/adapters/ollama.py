"""Ollama language model adapter."""

import httpx2

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.ports.llm import LLMProvider


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
        data = response.json()
        return str(data["response"])
