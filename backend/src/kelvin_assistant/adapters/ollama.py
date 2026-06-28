"""Ollama language model adapter."""

from kelvin_assistant.config.settings import get_settings
from kelvin_assistant.ports.llm import LLMProvider


class OllamaProvider(LLMProvider):
    """LLM provider backed by Ollama."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError