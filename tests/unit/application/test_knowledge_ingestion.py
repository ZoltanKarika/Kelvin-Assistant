"""Unit tests for knowledge ingestion use cases."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

from kelvin_assistant.application.knowledge import KnowledgeIngestionService
from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from kelvin_assistant.ports.knowledge import StoredKnowledgeDocument

COLLECTION_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_ingest_file_loads_chunks_and_stores_document() -> None:
    """The ingestion service coordinates loader, chunker, and repository."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="Kelvin API production portja 8000.",
        mime_type="text/plain",
    )
    chunk = KnowledgeChunk(
        source_uri=document.source_uri,
        chunk_index=0,
        content=document.content,
    )
    repository = FakeKnowledgeRepository()
    service = KnowledgeIngestionService(
        loader=FakeDocumentLoader(document),
        chunker=FakeDocumentChunker((chunk,)),
        repository=repository,
    )

    result = asyncio.run(
        service.ingest_file(
            Path("notes.txt"),
            collection_name=" manual ",
        )
    )

    assert result.source_uri == "file:///notes.txt"
    assert result.collection_name == "manual"
    assert result.stored_document.document_id == DOCUMENT_ID
    assert repository.saved == [
        SavedDocument(
            collection_name="manual",
            document=document,
            chunks=(chunk,),
        )
    ]


def test_ingest_file_rejects_empty_collection_name() -> None:
    """Collection names are required before ingestion starts."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="Kelvin API production portja 8000.",
        mime_type="text/plain",
    )
    service = KnowledgeIngestionService(
        loader=FakeDocumentLoader(document),
        chunker=FakeDocumentChunker(()),
        repository=FakeKnowledgeRepository(),
    )

    with pytest.raises(ValueError, match="Collection name"):
        asyncio.run(service.ingest_file(Path("notes.txt"), collection_name=" "))


@dataclass(frozen=True, slots=True)
class SavedDocument:
    """Recorded repository save call."""

    collection_name: str
    document: KnowledgeDocument
    chunks: tuple[KnowledgeChunk, ...]


class FakeDocumentLoader:
    """Deterministic loader for ingestion tests."""

    def __init__(self, document: KnowledgeDocument) -> None:
        self._document = document

    def load(self, path: Path) -> KnowledgeDocument:
        assert path == Path("notes.txt")
        return self._document


class FakeDocumentChunker:
    """Deterministic chunker for ingestion tests."""

    def __init__(self, chunks: tuple[KnowledgeChunk, ...]) -> None:
        self._chunks = chunks

    def chunk(self, document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        assert document.source_uri == "file:///notes.txt"
        return self._chunks


class FakeKnowledgeRepository:
    """Recording repository for ingestion tests."""

    def __init__(self) -> None:
        self.saved: list[SavedDocument] = []

    async def save_document(
        self,
        collection_name: str,
        document: KnowledgeDocument,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> StoredKnowledgeDocument:
        self.saved.append(
            SavedDocument(
                collection_name=collection_name,
                document=document,
                chunks=chunks,
            )
        )
        return StoredKnowledgeDocument(
            collection_id=COLLECTION_ID,
            document_id=DOCUMENT_ID,
            chunk_count=len(chunks),
            content_hash="a" * 64,
        )
