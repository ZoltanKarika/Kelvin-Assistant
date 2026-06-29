"""Knowledge search application services."""

from __future__ import annotations

from dataclasses import dataclass

from kelvin_assistant.ports.embeddings import EmbeddingProvider
from kelvin_assistant.ports.knowledge import KnowledgeSearchRepository


@dataclass(frozen=True, slots=True)
class KnowledgeSearchService:
    """Retrieve formatted RAG context from the knowledge store."""

    embedding_provider: EmbeddingProvider
    repository: KnowledgeSearchRepository
    collection_name: str
    embedding_model: str
    result_limit: int = 3

    def __post_init__(self) -> None:
        """Validate search configuration."""

        if not self.collection_name.strip():
            msg = "collection_name cannot be empty"
            raise ValueError(msg)
        if not self.embedding_model.strip():
            msg = "embedding_model cannot be empty"
            raise ValueError(msg)
        if self.result_limit <= 0:
            msg = "result_limit must be positive"
            raise ValueError(msg)

    async def get_context(self, query: str) -> str | None:
        """Return formatted knowledge context for a user query."""

        normalized_query = query.strip()
        if not normalized_query:
            return None

        query_embedding = await self.embedding_provider.embed_text(normalized_query)
        results = await self.repository.search_similar_chunks(
            self.collection_name.strip(),
            self.embedding_model.strip(),
            query_embedding,
            limit=self.result_limit,
        )
        if not results:
            return None

        context_blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            heading = result.metadata.get("heading")
            source = result.title or result.source_uri
            label = f"[{index}] source={source}; chunk={result.chunk_index}"
            if heading:
                label = f"{label}; heading={heading}"
            context_blocks.append(f"{label}\n{result.content}")

        return "\n\n".join(context_blocks)
