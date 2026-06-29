"""Import one local text or Markdown document into the knowledge database."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

from kelvin_assistant.adapters.local_documents import LocalTextDocumentLoader
from kelvin_assistant.adapters.postgres_knowledge import PostgresKnowledgeRepository
from kelvin_assistant.application.knowledge import (
    KnowledgeIngestionResult,
    KnowledgeIngestionService,
    ParagraphChunker,
)
from kelvin_assistant.domain.knowledge import KnowledgeDocumentError
from kelvin_assistant.ports.documents import DocumentLoaderError
from kelvin_assistant.ports.knowledge import KnowledgeRepositoryError

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""

    parser = argparse.ArgumentParser(
        description="Import one .txt or .md document into Kelvin knowledge storage.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a local .txt, .md, or .markdown file.",
    )
    parser.add_argument(
        "--collection",
        required=True,
        help="Knowledge collection name, for example 'manual' or 'notes'.",
    )
    parser.add_argument(
        "--max-characters",
        type=int,
        default=2_000,
        help="Maximum characters per chunk. Default: 2000.",
    )
    return parser


def build_service(max_characters: int) -> KnowledgeIngestionService:
    """Create the default ingestion service for local document imports."""

    return KnowledgeIngestionService(
        loader=LocalTextDocumentLoader(),
        chunker=ParagraphChunker(max_characters=max_characters),
        repository=PostgresKnowledgeRepository(),
    )


async def import_document(
    path: Path,
    *,
    collection_name: str,
    max_characters: int,
) -> KnowledgeIngestionResult:
    """Import one local document and return the stored document result."""

    service = build_service(max_characters)
    return await service.ingest_file(path, collection_name=collection_name)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the import script and return a process exit code."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = asyncio.run(
            import_document(
                args.path,
                collection_name=args.collection,
                max_characters=args.max_characters,
            )
        )
    except (
        ValueError,
        DocumentLoaderError,
        KnowledgeDocumentError,
        KnowledgeRepositoryError,
    ) as exc:
        LOGGER.error("Document import failed: %s", exc)
        return 1

    LOGGER.info(
        "Imported %s into collection '%s' as document %s with %s chunks",
        result.source_uri,
        result.collection_name,
        result.stored_document.document_id,
        result.stored_document.chunk_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
