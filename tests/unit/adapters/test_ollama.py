"""Unit tests for the Ollama language model adapter."""

import asyncio
import json

import httpx2
import pytest

from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.config.settings import Settings
from kelvin_assistant.domain.chat import ChatMessage, ChatRole
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


def test_chat_sends_structured_messages_and_returns_content() -> None:
    """The chat operation preserves message roles at the Ollama boundary."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url == httpx2.URL("http://ollama.test:11434/api/chat")
        assert json.loads(request.content) == {
            "model": "gemma4:test",
            "messages": [
                {"role": "user", "content": "Szia!"},
                {"role": "assistant", "content": "Szia!"},
                {"role": "user", "content": "Emlékszel rám?"},
            ],
            "stream": False,
        }
        return httpx2.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "Igen.",
                }
            },
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
    messages = (
        ChatMessage(role=ChatRole.USER, content="Szia!"),
        ChatMessage(role=ChatRole.ASSISTANT, content="Szia!"),
        ChatMessage(role=ChatRole.USER, content="Emlékszel rám?"),
    )

    result = asyncio.run(provider.chat(messages))

    assert result == "Igen."


def test_stream_chat_sends_structured_messages_and_yields_content() -> None:
    """The streaming chat operation yields Ollama message chunks."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url == httpx2.URL("http://ollama.test:11434/api/chat")
        assert json.loads(request.content) == {
            "model": "gemma4:test",
            "messages": [{"role": "user", "content": "Szia!"}],
            "stream": True,
        }
        return httpx2.Response(
            200,
            content=(
                b'{"message":{"role":"assistant","content":"Szi"},"done":false}\n'
                b'{"message":{"role":"assistant","content":"a!"},"done":false}\n'
                b'{"done":true}\n'
            ),
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
    messages = (ChatMessage(role=ChatRole.USER, content="Szia!"),)

    async def collect_chunks() -> list[str]:
        return [chunk async for chunk in provider.stream_chat(messages)]

    result = asyncio.run(collect_chunks())

    assert result == ["Szi", "a!"]


def test_stream_chat_rejects_invalid_chunk() -> None:
    """Streaming chat rejects chunks without text content."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b'{"message":{"content":42},"done":false}\n',
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
    messages = (ChatMessage(role=ChatRole.USER, content="Szia!"),)

    async def collect_chunks() -> list[str]:
        return [chunk async for chunk in provider.stream_chat(messages)]

    with pytest.raises(
        LLMResponseError,
        match="Ollama returned an invalid streaming chat chunk",
    ):
        asyncio.run(collect_chunks())


@pytest.mark.parametrize(
    "payload",
    [
        {"done": True},
        {"message": {"content": 42}},
    ],
)
def test_chat_rejects_invalid_response(payload: dict[str, object]) -> None:
    """The chat operation rejects missing or non-text response content."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=payload, request=request)

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
    messages = (ChatMessage(role=ChatRole.USER, content="Szia!"),)

    with pytest.raises(
        LLMResponseError,
        match="Ollama returned an invalid chat response",
    ):
        asyncio.run(provider.chat(messages))


def test_readiness_accepts_installed_configured_model() -> None:
    """Readiness succeeds when Ollama lists the configured model."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        assert request.url == httpx2.URL("http://ollama.test:11434/api/tags")
        return httpx2.Response(
            200,
            json={
                "models": [
                    {
                        "name": "gemma4:test",
                        "model": "gemma4:test",
                    }
                ]
            },
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

    asyncio.run(provider.check_readiness())


def test_readiness_rejects_missing_configured_model() -> None:
    """Readiness fails when the configured model is not installed."""

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={"models": [{"name": "another-model:latest"}]},
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
        match="Configured Ollama model is not installed: gemma4:test",
    ):
        asyncio.run(provider.check_readiness())
