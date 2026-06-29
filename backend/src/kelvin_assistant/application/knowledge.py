"""Knowledge document chunking use cases."""

from dataclasses import dataclass
from pathlib import Path

from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from kelvin_assistant.ports.documents import DocumentChunker, DocumentLoader
from kelvin_assistant.ports.embeddings import EmbeddingProvider
from kelvin_assistant.ports.knowledge import (
    ChunkEmbedding,
    KnowledgeRepository,
    StoredKnowledgeDocument,
    StoredKnowledgeEmbeddings,
)


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionResult:
    """Result returned after importing one knowledge document."""

    source_uri: str
    collection_name: str
    stored_document: StoredKnowledgeDocument
    stored_embeddings: StoredKnowledgeEmbeddings | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeIngestionService:
    """Load, chunk, and store local knowledge documents."""

    loader: DocumentLoader
    chunker: DocumentChunker
    repository: KnowledgeRepository
    embedding_provider: EmbeddingProvider | None = None
    embedding_model: str | None = None

    async def ingest_file(
        self,
        path: Path,
        *,
        collection_name: str,
    ) -> KnowledgeIngestionResult:
        """Import one local document into a knowledge collection."""

        normalized_collection_name = collection_name.strip()
        if not normalized_collection_name:
            msg = "Collection name cannot be empty"
            raise ValueError(msg)

        document = self.loader.load(path)
        chunks = self.chunker.chunk(document)
        stored_document = await self.repository.save_document(
            normalized_collection_name,
            document,
            chunks,
        )
        stored_embeddings = await self._store_embeddings(
            normalized_collection_name,
            document,
            chunks,
        )

        return KnowledgeIngestionResult(
            source_uri=document.source_uri,
            collection_name=normalized_collection_name,
            stored_document=stored_document,
            stored_embeddings=stored_embeddings,
        )

    async def _store_embeddings(
        self,
        collection_name: str,
        document: KnowledgeDocument,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> StoredKnowledgeEmbeddings | None:
        """Create and store embeddings when an embedding provider is configured."""

        if self.embedding_provider is None:
            return None
        if self.embedding_model is None or not self.embedding_model.strip():
            msg = "Embedding model must be configured when embeddings are enabled"
            raise ValueError(msg)

        embeddings: list[ChunkEmbedding] = []
        for chunk in chunks:
            embeddings.append(
                ChunkEmbedding(
                    chunk_index=chunk.chunk_index,
                    embedding=await self.embedding_provider.embed_text(chunk.content),
                )
            )

        return await self.repository.save_embeddings(
            collection_name,
            document.source_uri,
            self.embedding_model.strip(),
            tuple(embeddings),
        )


@dataclass(frozen=True, slots=True)
class ParagraphChunker:
    """Create deterministic paragraph-based chunks."""

    max_characters: int = 2_000

    def __post_init__(self) -> None:
        """Validate chunking policy."""

        if self.max_characters <= 0:
            msg = "max_characters must be positive"
            raise ValueError(msg)

    def chunk(self, document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        """Split a document into stable chunks with lightweight metadata."""

        if document.mime_type == "text/markdown":
            sections = _markdown_sections(document)
        else:
            sections = [_Section(content=document.content, heading=None)]

        chunks: list[KnowledgeChunk] = []
        for section in sections:
            for content in _split_text(section.content, self.max_characters):
                metadata = dict(document.metadata)
                if section.heading is not None:
                    metadata["heading"] = section.heading
                chunks.append(
                    KnowledgeChunk(
                        source_uri=document.source_uri,
                        chunk_index=len(chunks),
                        content=content,
                        metadata=metadata,
                    )
                )

        return tuple(chunks)


@dataclass(frozen=True, slots=True)
class _Section:
    """Internal chunking section."""

    content: str
    heading: str | None


def _markdown_sections(document: KnowledgeDocument) -> list[_Section]:
    """Group Markdown text below its latest heading."""

    sections: list[_Section] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in document.content.splitlines():
        heading = _extract_markdown_heading(line)
        if heading is not None:
            if "\n".join(current_lines).strip():
                sections.append(
                    _Section(
                        content="\n".join(current_lines),
                        heading=current_heading,
                    )
                )
            current_heading = heading
            current_lines = [line]
        else:
            current_lines.append(line)

    if "\n".join(current_lines).strip():
        sections.append(
            _Section(
                content="\n".join(current_lines),
                heading=current_heading,
            )
        )

    return sections or [_Section(content=document.content, heading=None)]


def _extract_markdown_heading(line: str) -> str | None:
    """Return an ATX heading title if the line is a Markdown heading."""

    stripped_line = line.strip()
    if not stripped_line.startswith("#"):
        return None
    marker, _, title = stripped_line.partition(" ")
    if not marker or any(character != "#" for character in marker):
        return None
    if len(marker) > 6:
        return None
    normalized_title = title.strip()
    return normalized_title or None


def _split_text(text: str, max_characters: int) -> tuple[str, ...]:
    """Split text by paragraphs without exceeding the character limit."""

    paragraphs = [
        paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()
    ]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_characters:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(paragraph, max_characters))
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return tuple(chunks)


def _split_long_text(text: str, max_characters: int) -> tuple[str, ...]:
    """Split a single long paragraph into fixed-size text chunks."""

    return tuple(
        text[start : start + max_characters].strip()
        for start in range(0, len(text), max_characters)
        if text[start : start + max_characters].strip()
    )
