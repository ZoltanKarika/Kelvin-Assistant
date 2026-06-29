"""Unit tests for the document import script."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from kelvin_assistant.application.knowledge import (
    KnowledgeIngestionResult,
    KnowledgeIngestionService,
)
from kelvin_assistant.cli import import_document
from kelvin_assistant.ports.knowledge import (
    StoredKnowledgeDocument,
    StoredKnowledgeEmbeddings,
)

DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_parser_requires_path_and_collection() -> None:
    """The import script accepts a source path and collection name."""

    args = import_document.build_parser().parse_args(
        [
            "--collection",
            "manual",
            "--max-characters",
            "500",
            "notes.md",
        ]
    )

    assert args.collection == "manual"
    assert args.max_characters == 500
    assert args.path == Path("notes.md")


def test_main_imports_document_with_default_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script wires CLI arguments into the ingestion service."""

    fake_service = FakeKnowledgeIngestionService()

    def fake_build_service(max_characters: int) -> KnowledgeIngestionService:
        assert max_characters == 500
        return cast(KnowledgeIngestionService, fake_service)

    monkeypatch.setattr(import_document, "build_service", fake_build_service)

    exit_code = import_document.main(
        [
            "--collection",
            "manual",
            "--max-characters",
            "500",
            "notes.md",
        ]
    )

    assert exit_code == 0
    assert fake_service.calls == [
        {
            "path": Path("notes.md"),
            "collection_name": "manual",
        }
    ]


def test_main_returns_failure_on_ingestion_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script exits with a non-zero code when ingestion fails."""

    fake_service = FakeKnowledgeIngestionService(error=ValueError("bad import"))

    def fake_build_service(max_characters: int) -> KnowledgeIngestionService:
        assert max_characters == 2_000
        return cast(KnowledgeIngestionService, fake_service)

    monkeypatch.setattr(import_document, "build_service", fake_build_service)

    exit_code = import_document.main(["--collection", "manual", "notes.md"])

    assert exit_code == 1


class FakeKnowledgeIngestionService:
    """Fake ingestion service for script tests."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def ingest_file(
        self,
        path: Path,
        *,
        collection_name: str,
    ) -> KnowledgeIngestionResult:
        self.calls.append(
            {
                "path": path,
                "collection_name": collection_name,
            }
        )
        if self._error is not None:
            raise self._error
        return KnowledgeIngestionResult(
            source_uri="file:///notes.md",
            collection_name=collection_name,
            stored_document=StoredKnowledgeDocument(
                collection_id=UUID("11111111-1111-1111-1111-111111111111"),
                document_id=DOCUMENT_ID,
                chunk_count=2,
                content_hash="a" * 64,
            ),
            stored_embeddings=StoredKnowledgeEmbeddings(
                source_uri="file:///notes.md",
                embedding_model="nomic-embed-text",
                embedding_count=2,
                embedding_dimension=768,
            ),
        )
