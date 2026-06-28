"""Unit tests for the Ollama language model adapter."""

import asyncio
import json

import httpx2
import pytest

from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.config.settings import Settings


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


def test_generate_raises_for_unsuccessful_response() -> None:
    """The adapter exposes an Ollama HTTP failure to its caller."""

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

    with pytest.raises(httpx2.HTTPStatusError):
        asyncio.run(provider.generate("Működsz?"))
