"""Language model provider port."""

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from kelvin_assistant.domain.chat import ChatMessage


class LLMProviderError(RuntimeError):
    """Base error raised by language model providers."""


class LLMUnavailableError(LLMProviderError):
    """Raised when the configured language model runtime cannot be reached."""


class LLMResponseError(LLMProviderError):
    """Raised when a language model runtime returns an unusable response."""


class LLMProvider(Protocol):
    """Interface for language model providers."""

    async def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        ...

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Generate an assistant response for structured chat messages."""
        ...

    def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Stream an assistant response for structured chat messages."""
        ...

    async def check_readiness(self) -> None:
        """Raise a provider error when the configured model is not ready."""
        ...
