"""Unit tests for knowledge search application services."""

import asyncio

import pytest

from kelvin_assistant.application.knowledge_search import KnowledgeSearchService
from kelvin_assistant.ports.knowledge import KnowledgeSearchResult


def test_knowledge_search_formats_context() -> None:
    """Search results are formatted into compact RAG context blocks."""

    async def scenario() -> None:
        embedding_provider = FakeEmbeddingProvider()
        repository = FakeKnowledgeRepository(
            (
                KnowledgeSearchResult(
                    source_uri="file:///notes.md",
                    title="Kelvin Notes",
                    chunk_index=2,
                    content="Ollama a Windows hoston fut.",
                    metadata={"heading": "Runtime"},
                    distance=0.12,
                ),
            )
        )
        service = KnowledgeSearchService(
            embedding_provider=embedding_provider,
            repository=repository,
            collection_name="manual",
            embedding_model="nomic-embed-text",
            result_limit=3,
        )

        context = await service.get_context("Hol fut az Ollama?")

        assert embedding_provider.texts == ["Hol fut az Ollama?"]
        assert repository.calls == [
            {
                "collection_name": "manual",
                "embedding_model": "nomic-embed-text",
                "query_embedding": (0.1, 0.2, 0.3),
                "limit": 3,
            }
        ]
        assert context == (
            "[1] source=Kelvin Notes; chunk=2; heading=Runtime\n"
            "Ollama a Windows hoston fut."
        )

    asyncio.run(scenario())


def test_knowledge_search_returns_none_without_results() -> None:
    """No matching chunks means no RAG context is added."""

    async def scenario() -> None:
        service = KnowledgeSearchService(
            embedding_provider=FakeEmbeddingProvider(),
            repository=FakeKnowledgeRepository(()),
            collection_name="manual",
            embedding_model="nomic-embed-text",
        )

        assert await service.get_context("query") is None

    asyncio.run(scenario())


def test_knowledge_search_rejects_invalid_configuration() -> None:
    """Search configuration must be explicit."""

    with pytest.raises(ValueError, match="collection_name"):
        KnowledgeSearchService(
            embedding_provider=FakeEmbeddingProvider(),
            repository=FakeKnowledgeRepository(()),
            collection_name=" ",
            embedding_model="nomic-embed-text",
        )


class FakeEmbeddingProvider:
    """Deterministic embedding provider for search tests."""

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed_text(self, text: str) -> tuple[float, ...]:
        self.texts.append(text)
        return (0.1, 0.2, 0.3)


class FakeKnowledgeRepository:
    """Deterministic repository for search tests."""

    def __init__(self, results: tuple[KnowledgeSearchResult, ...]) -> None:
        self._results = results
        self.calls: list[dict[str, object]] = []

    async def search_similar_chunks(
        self,
        collection_name: str,
        embedding_model: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        self.calls.append(
            {
                "collection_name": collection_name,
                "embedding_model": embedding_model,
                "query_embedding": query_embedding,
                "limit": limit,
            }
        )
        return self._results
