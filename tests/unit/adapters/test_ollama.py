"""Unit tests for the Ollama language model adapter."""

import asyncio
import json

import httpx2
import pytest

from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.ports.llm import LLMResponseError, LLMUnavailableError


def test_generate_sends_expected_request_and_returns_response() -> None:
    """The adapter sends a non-streaming request using the configured model."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url == httpx2.URL("http://ollama.test:11434/api/generate")
        assert json.loads(request.content) == {
            "model": "gemma4:test",
            "prompt": "Működsz?",
            "stream": False,
        }
        return httpx2.Response(200, json={"response": "Igen."})

    settings = Settings(
        environment="test",
        ollama_base_url="http://ollama.test:11434",
        ollama_model="gemma4:test",
        ollama_timeout=1.0,
    )
    provider = OllamaProvider(
        settings=settings,
        transport=httpx2.MockTransport(handle_request),
    )

    result = asyncio.run(provider.generate("Működsz?"))

    assert result == "Igen."


def test_generate_translates_unsuccessful_response() -> None:
    """The adapter translates an Ollama HTTP failure to its port contract."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            503,
            json={"error": "model unavailable"},
            request=request,
        )

    settings = Settings(
        environment="test",
        ollama_base_url="http://ollama.test:11434",
        ollama_model="gemma4:test",
        ollama_timeout=1.0,
    )
    provider = OllamaProvider(
        settings=settings,
        transport=httpx2.MockTransport(handle_request),
    )

    with pytest.raises(
        LLMResponseError,
        match="Ollama returned HTTP status 503",
    ):
        asyncio.run(provider.generate("Működsz?"))


def test_generate_translates_connection_failure() -> None:
    """The adapter reports an unreachable Ollama runtime consistently."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    settings = Settings(
        environment="test",
        ollama_base_url="http://ollama.test:11434",
        ollama_model="gemma4:test",
        ollama_timeout=1.0,
    )
    provider = OllamaProvider(
        settings=settings,
        transport=httpx2.MockTransport(handle_request),
    )

    with pytest.raises(
        LLMUnavailableError,
        match="Ollama runtime is unavailable",
    ):
        asyncio.run(provider.generate("Működsz?"))


@pytest.mark.parametrize(
    "payload",
    [
        {"done": True},
        {"response": 42},
    ],
)
def test_generate_rejects_invalid_response(payload: dict[str, object]) -> None:
    """The adapter rejects a successful response without valid generated text."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json=payload,
            request=request,
        )

    settings = Settings(
        environment="test",
        ollama_base_url="http://ollama.test:11434",
        ollama_model="gemma4:test",
        ollama_timeout=1.0,
    )
    provider = OllamaProvider(
        settings=settings,
        transport=httpx2.MockTransport(handle_request),
    )

    with pytest.raises(
        LLMResponseError,
        match="Ollama returned an invalid response",
    ):
        asyncio.run(provider.generate("Működsz?"))
