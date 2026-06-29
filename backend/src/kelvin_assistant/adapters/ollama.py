"""Ollama language model adapter."""

import json
import logging
from collections.abc import AsyncIterator, Sequence

import httpx2

from kelvin_assistant.config.settings import Settings, get_settings
from kelvin_assistant.domain.chat import ChatMessage
from kelvin_assistant.ports.embeddings import (
    EmbeddingProvider,
    EmbeddingResponseError,
    EmbeddingUnavailableError,
)
from kelvin_assistant.ports.llm import (
    LLMProvider,
    LLMResponseError,
    LLMUnavailableError,
)

LOGGER = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Ollama."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        """Initialize the adapter with injectable runtime dependencies."""

        self.settings = settings or get_settings()
        self._transport = transport

    async def embed_text(self, text: str) -> tuple[float, ...]:
        """Create one embedding vector using the configured Ollama model."""

        normalized_text = text.strip()
        if not normalized_text:
            msg = "Text to embed cannot be empty"
            raise ValueError(msg)

        response = await self._request(
            "POST",
            "/api/embed",
            payload={
                "model": self.settings.ollama_embedding_model,
                "input": normalized_text,
            },
        )

        embedding = _parse_embedding_response(response)
        if len(embedding) != self.settings.embedding_dimension:
            LOGGER.warning(
                "Ollama embedding dimension mismatch: expected %s, got %s",
                self.settings.embedding_dimension,
                len(embedding),
            )
            raise EmbeddingResponseError("Ollama returned an invalid embedding")

        return embedding

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object],
    ) -> httpx2.Response:
        """Send an embedding request and translate Ollama errors."""

        try:
            async with httpx2.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self.settings.ollama_timeout,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
            response.raise_for_status()
        except httpx2.RequestError as exc:
            LOGGER.warning("Ollama embedding runtime is unavailable: %s", exc)
            raise EmbeddingUnavailableError(
                "Ollama embedding runtime is unavailable"
            ) from exc
        except httpx2.HTTPStatusError as exc:
            status_code = exc.response.status_code
            LOGGER.warning("Ollama embedding returned HTTP status %d", status_code)
            raise EmbeddingResponseError(
                f"Ollama embedding returned HTTP status {status_code}"
            ) from exc

        return response


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

        response = await self._request(
            "POST",
            "/api/generate",
            payload={
                "model": self.settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
        )

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

    async def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Generate a response from structured conversation messages."""

        response = await self._request(
            "POST",
            "/api/chat",
            payload={
                "model": self.settings.ollama_model,
                "messages": [
                    {
                        "role": message.role.value,
                        "content": message.content,
                    }
                    for message in messages
                ],
                "stream": False,
            },
        )

        try:
            data = response.json()
            message = data["message"]
            result = message["content"]
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Ollama returned an invalid chat response body")
            raise LLMResponseError("Ollama returned an invalid chat response") from exc

        if not isinstance(result, str):
            LOGGER.warning("Ollama chat response field is not text")
            raise LLMResponseError("Ollama returned an invalid chat response")

        return result

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Stream a response from structured conversation messages."""

        payload: dict[str, object] = {
            "model": self.settings.ollama_model,
            "messages": [
                {
                    "role": message.role.value,
                    "content": message.content,
                }
                for message in messages
            ],
            "stream": True,
        }

        try:
            async with httpx2.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self.settings.ollama_timeout,
                transport=self._transport,
            ) as client:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = self._parse_stream_line(line)
                        if chunk:
                            yield chunk
        except httpx2.RequestError as exc:
            LOGGER.warning("Ollama runtime is unavailable: %s", exc)
            raise LLMUnavailableError("Ollama runtime is unavailable") from exc
        except httpx2.HTTPStatusError as exc:
            status_code = exc.response.status_code
            LOGGER.warning("Ollama returned HTTP status %d", status_code)
            raise LLMResponseError(
                f"Ollama returned HTTP status {status_code}"
            ) from exc

    async def check_readiness(self) -> None:
        """Check that Ollama is reachable and the configured model exists."""

        response = await self._request("GET", "/api/tags")

        try:
            data = response.json()
            models = data["models"]
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Ollama returned an invalid model list")
            raise LLMResponseError("Ollama returned an invalid model list") from exc

        if not isinstance(models, list):
            LOGGER.warning("Ollama model list is not an array")
            raise LLMResponseError("Ollama returned an invalid model list")

        model_names: set[str] = set()
        for model in models:
            if not isinstance(model, dict):
                LOGGER.warning("Ollama model list contains an invalid entry")
                raise LLMResponseError("Ollama returned an invalid model list")
            for key in ("name", "model"):
                value = model.get(key)
                if isinstance(value, str):
                    model_names.add(value)

        if self.settings.ollama_model not in model_names:
            LOGGER.warning(
                "Configured Ollama model is not installed: %s",
                self.settings.ollama_model,
            )
            raise LLMResponseError(
                f"Configured Ollama model is not installed: "
                f"{self.settings.ollama_model}"
            )

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> httpx2.Response:
        """Send a request and translate transport-level Ollama errors."""

        try:
            async with httpx2.AsyncClient(
                base_url=self.settings.ollama_base_url,
                timeout=self.settings.ollama_timeout,
                transport=self._transport,
            ) as client:
                if payload is None:
                    response = await client.request(method, path)
                else:
                    response = await client.request(method, path, json=payload)
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

        return response

    def _parse_stream_line(self, line: str) -> str | None:
        """Parse one Ollama chat streaming JSON line into optional text."""

        try:
            data = json.loads(line)
            if data.get("done") is True:
                return None
            message = data["message"]
            content = message["content"]
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Ollama returned an invalid streaming chat chunk")
            raise LLMResponseError(
                "Ollama returned an invalid streaming chat chunk"
            ) from exc

        if not isinstance(content, str):
            LOGGER.warning("Ollama streaming chat chunk is not text")
            raise LLMResponseError("Ollama returned an invalid streaming chat chunk")

        return content


def _parse_embedding_response(response: httpx2.Response) -> tuple[float, ...]:
    """Parse one Ollama embedding response."""

    try:
        data = response.json()
        raw_embedding = _extract_raw_embedding(data)
        embedding = _parse_float_sequence(raw_embedding)
    except (KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("Ollama returned an invalid embedding response body")
        raise EmbeddingResponseError("Ollama returned an invalid embedding") from exc

    if not embedding:
        LOGGER.warning("Ollama returned an empty embedding")
        raise EmbeddingResponseError("Ollama returned an invalid embedding")

    return embedding


def _extract_raw_embedding(data: object) -> Sequence[object]:
    """Extract embedding data from current or legacy Ollama responses."""

    if not isinstance(data, dict):
        raise TypeError

    embeddings = data.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first_embedding = embeddings[0]
        if not isinstance(first_embedding, list):
            raise TypeError
        return first_embedding

    embedding = data["embedding"]
    if not isinstance(embedding, list):
        raise TypeError
    return embedding


def _parse_float_sequence(values: Sequence[object]) -> tuple[float, ...]:
    """Parse JSON values into an embedding vector."""

    embedding: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError
        embedding.append(float(value))
    return tuple(embedding)
