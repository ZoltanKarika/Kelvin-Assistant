"""Unit tests for knowledge ingestion use cases."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest

from kelvin_assistant.application.knowledge import KnowledgeIngestionService
from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from kelvin_assistant.ports.knowledge import (
    ChunkEmbedding,
    KnowledgeSearchResult,
    StoredKnowledgeDocument,
    StoredKnowledgeEmbeddings,
)

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
    assert result.stored_embeddings is None


def test_ingest_file_embeds_and_stores_chunks_when_enabled() -> None:
    """The ingestion service can persist embeddings for imported chunks."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="Kelvin API production portja 8000.",
        mime_type="text/plain",
    )
    chunks = (
        KnowledgeChunk(
            source_uri=document.source_uri,
            chunk_index=0,
            content="Kelvin API production portja 8000.",
        ),
        KnowledgeChunk(
            source_uri=document.source_uri,
            chunk_index=1,
            content="PostgreSQL es pgvector lokalisan fut.",
        ),
    )
    embedding_provider = FakeEmbeddingProvider(
        {
            chunks[0].content: (0.1, 0.2, 0.3),
            chunks[1].content: (0.4, 0.5, 0.6),
        }
    )
    repository = FakeKnowledgeRepository()
    service = KnowledgeIngestionService(
        loader=FakeDocumentLoader(document),
        chunker=FakeDocumentChunker(chunks),
        repository=repository,
        embedding_provider=embedding_provider,
        embedding_model="nomic-embed-text",
    )

    result = asyncio.run(
        service.ingest_file(
            Path("notes.txt"),
            collection_name="manual",
        )
    )

    assert embedding_provider.embedded_texts == [
        "Kelvin API production portja 8000.",
        "PostgreSQL es pgvector lokalisan fut.",
    ]
    assert repository.saved_embeddings == [
        SavedEmbeddings(
            collection_name="manual",
            source_uri="file:///notes.txt",
            embedding_model="nomic-embed-text",
            embeddings=(
                ChunkEmbedding(chunk_index=0, embedding=(0.1, 0.2, 0.3)),
                ChunkEmbedding(chunk_index=1, embedding=(0.4, 0.5, 0.6)),
            ),
        )
    ]
    assert result.stored_embeddings is not None
    assert result.stored_embeddings.embedding_count == 2
    assert result.stored_embeddings.embedding_dimension == 3


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


def test_ingest_file_requires_embedding_model_when_embeddings_are_enabled() -> None:
    """Embedding imports must store the model name with vectors."""

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
    service = KnowledgeIngestionService(
        loader=FakeDocumentLoader(document),
        chunker=FakeDocumentChunker((chunk,)),
        repository=FakeKnowledgeRepository(),
        embedding_provider=FakeEmbeddingProvider({chunk.content: (0.1, 0.2, 0.3)}),
    )

    with pytest.raises(ValueError, match="Embedding model"):
        asyncio.run(service.ingest_file(Path("notes.txt"), collection_name="manual"))


@dataclass(frozen=True, slots=True)
class SavedDocument:
    """Recorded repository save call."""

    collection_name: str
    document: KnowledgeDocument
    chunks: tuple[KnowledgeChunk, ...]


@dataclass(frozen=True, slots=True)
class SavedEmbeddings:
    """Recorded repository embedding save call."""

    collection_name: str
    source_uri: str
    embedding_model: str
    embeddings: tuple[ChunkEmbedding, ...]


class FakeEmbeddingProvider:
    """Deterministic embedding provider for ingestion tests."""

    def __init__(self, embeddings_by_text: dict[str, tuple[float, ...]]) -> None:
        self._embeddings_by_text = embeddings_by_text
        self.embedded_texts: list[str] = []

    async def embed_text(self, text: str) -> tuple[float, ...]:
        self.embedded_texts.append(text)
        return self._embeddings_by_text[text]


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
        self.saved_embeddings: list[SavedEmbeddings] = []

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

    async def save_embeddings(
        self,
        collection_name: str,
        source_uri: str,
        embedding_model: str,
        embeddings: tuple[ChunkEmbedding, ...],
    ) -> StoredKnowledgeEmbeddings:
        self.saved_embeddings.append(
            SavedEmbeddings(
                collection_name=collection_name,
                source_uri=source_uri,
                embedding_model=embedding_model,
                embeddings=embeddings,
            )
        )
        return StoredKnowledgeEmbeddings(
            source_uri=source_uri,
            embedding_model=embedding_model,
            embedding_count=len(embeddings),
            embedding_dimension=len(embeddings[0].embedding) if embeddings else 0,
        )

    async def search_similar_chunks(
        self,
        collection_name: str,
        embedding_model: str,
        query_embedding: tuple[float, ...],
        *,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        return ()
