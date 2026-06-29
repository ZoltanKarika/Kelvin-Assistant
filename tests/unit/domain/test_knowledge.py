"""Unit tests for knowledge domain models."""

import pytest

from kelvin_assistant.domain.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentError,
)


def test_knowledge_document_normalizes_text_fields() -> None:
    """Documents trim source, content, and blank titles."""

    document = KnowledgeDocument(
        source_uri=" file:///notes.md ",
        content="  Hello Kelvin  ",
        mime_type="text/markdown",
        title="   ",
    )

    assert document.source_uri == "file:///notes.md"
    assert document.content == "Hello Kelvin"
    assert document.title is None


@pytest.mark.parametrize(
    ("source_uri", "content"),
    [
        ("", "content"),
        ("file:///notes.md", "   "),
    ],
)
def test_knowledge_document_rejects_invalid_values(
    source_uri: str,
    content: str,
) -> None:
    """Documents require source and content."""

    with pytest.raises(KnowledgeDocumentError):
        KnowledgeDocument(
            source_uri=source_uri,
            content=content,
            mime_type="text/plain",
        )


def test_knowledge_chunk_rejects_negative_index() -> None:
    """Chunks cannot have negative indexes."""

    with pytest.raises(KnowledgeDocumentError):
        KnowledgeChunk(
            source_uri="file:///notes.txt",
            chunk_index=-1,
            content="Szia",
        )
