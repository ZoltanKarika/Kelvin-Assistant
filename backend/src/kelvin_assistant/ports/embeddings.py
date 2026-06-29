"""Embedding provider port."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProviderError(RuntimeError):
    """Base error raised by embedding providers."""


class EmbeddingUnavailableError(EmbeddingProviderError):
    """Raised when the configured embedding runtime cannot be reached."""


class EmbeddingResponseError(EmbeddingProviderError):
    """Raised when an embedding runtime returns an unusable response."""


class EmbeddingProvider(Protocol):
    """Interface for text embedding providers."""

    async def embed_text(self, text: str) -> tuple[float, ...]:
        """Create one embedding vector for the given text."""
