"""Run an opt-in connectivity check against the configured Ollama runtime."""

import asyncio
import logging

from kelvin_assistant.adapters.ollama import OllamaProvider
from kelvin_assistant.ports.llm import LLMProviderError

LOGGER = logging.getLogger(__name__)


async def request_probe() -> str:
    """Request a short response from the configured Ollama model."""

    provider = OllamaProvider()
    return await provider.generate("Válaszolj egyetlen szóval: működsz?")


def main() -> int:
    """Run the live check and return a process exit code."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    try:
        response = asyncio.run(request_probe())
    except LLMProviderError as exc:
        LOGGER.error("Ollama connectivity check failed: %s", exc)
        return 1

    LOGGER.info("Ollama response: %s", response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
