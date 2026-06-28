"""Language model provider port."""

from typing import Protocol


class LLMProvider(Protocol):
    """Interface for language model providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        ...
