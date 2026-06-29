"""Unit tests for knowledge application services."""

import pytest

from kelvin_assistant.application.knowledge import ParagraphChunker
from kelvin_assistant.domain.knowledge import KnowledgeDocument


def test_paragraph_chunker_keeps_short_text_together() -> None:
    """Short plain text documents become one chunk."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="First paragraph.\n\nSecond paragraph.",
        mime_type="text/plain",
        metadata={"filename": "notes.txt"},
    )
    chunker = ParagraphChunker(max_characters=100)

    chunks = chunker.chunk(document)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == "First paragraph.\n\nSecond paragraph."
    assert chunks[0].metadata == {"filename": "notes.txt"}


def test_paragraph_chunker_splits_by_paragraph_limit() -> None:
    """Paragraphs are split deterministically when the limit is reached."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="aaaa\n\nbbbb\n\ncccc",
        mime_type="text/plain",
    )
    chunker = ParagraphChunker(max_characters=10)

    chunks = chunker.chunk(document)

    assert [chunk.content for chunk in chunks] == ["aaaa\n\nbbbb", "cccc"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


def test_paragraph_chunker_splits_long_paragraph() -> None:
    """A single oversized paragraph is split into fixed-size chunks."""

    document = KnowledgeDocument(
        source_uri="file:///notes.txt",
        content="abcdefghij",
        mime_type="text/plain",
    )
    chunker = ParagraphChunker(max_characters=4)

    chunks = chunker.chunk(document)

    assert [chunk.content for chunk in chunks] == ["abcd", "efgh", "ij"]


def test_markdown_headings_are_preserved_as_metadata() -> None:
    """Markdown headings are attached to chunks for later source references."""

    document = KnowledgeDocument(
        source_uri="file:///notes.md",
        content="# API\n\nKelvin portja 8000.\n\n## Database\n\nPostgreSQL fut.",
        mime_type="text/markdown",
        metadata={"filename": "notes.md"},
    )
    chunker = ParagraphChunker(max_characters=100)

    chunks = chunker.chunk(document)

    assert [chunk.metadata.get("heading") for chunk in chunks] == [
        "API",
        "Database",
    ]
    assert chunks[0].content == "# API\n\nKelvin portja 8000."
    assert chunks[1].content == "## Database\n\nPostgreSQL fut."


def test_paragraph_chunker_rejects_invalid_limit() -> None:
    """Chunk size must be positive."""

    with pytest.raises(ValueError, match="max_characters"):
        ParagraphChunker(max_characters=0)
