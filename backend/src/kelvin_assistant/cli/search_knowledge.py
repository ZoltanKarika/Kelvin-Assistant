"""Search the local knowledge database with an embedded query."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence

from kelvin_assistant.adapters.ollama import OllamaEmbeddingProvider
from kelvin_assistant.adapters.postgres_knowledge import PostgresKnowledgeRepository
from kelvin_assistant.config.settings import get_settings
from kelvin_assistant.ports.embeddings import EmbeddingProviderError
from kelvin_assistant.ports.knowledge import (
    KnowledgeRepositoryError,
    KnowledgeSearchResult,
)

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""

    parser = argparse.ArgumentParser(
        description="Search Kelvin knowledge storage with semantic similarity.",
    )
    parser.add_argument("query", help="Search question or query text.")
    parser.add_argument(
        "--collection",
        required=True,
        help="Knowledge collection name, for example 'manual' or 'notes'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of chunks to return. Default: 5.",
    )
    return parser


async def search_knowledge(
    query: str,
    *,
    collection_name: str,
    limit: int,
) -> tuple[KnowledgeSearchResult, ...]:
    """Embed a query and search for similar knowledge chunks."""

    normalized_query = query.strip()
    if not normalized_query:
        msg = "Query cannot be empty"
        raise ValueError(msg)

    settings = get_settings()
    embedding_provider = OllamaEmbeddingProvider(settings=settings)
    repository = PostgresKnowledgeRepository(settings=settings)
    query_embedding = await embedding_provider.embed_text(normalized_query)
    return await repository.search_similar_chunks(
        collection_name,
        settings.ollama_embedding_model,
        query_embedding,
        limit=limit,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the search command and return a process exit code."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        results = asyncio.run(
            search_knowledge(
                args.query,
                collection_name=args.collection,
                limit=args.limit,
            )
        )
    except (ValueError, EmbeddingProviderError, KnowledgeRepositoryError) as exc:
        LOGGER.error("Knowledge search failed: %s", exc)
        return 1

    if not results:
        LOGGER.info("No matching chunks found")
        return 0

    for index, result in enumerate(results, start=1):
        heading = result.metadata.get("heading")
        heading_suffix = f" | heading: {heading}" if heading else ""
        LOGGER.info(
            "[%s] distance=%.4f | source=%s | chunk=%s%s",
            index,
            result.distance,
            result.source_uri,
            result.chunk_index,
            heading_suffix,
        )
        LOGGER.info("%s", result.content)

    return 0
