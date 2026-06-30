"""Unit tests for memory domain models."""

from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from uuid import uuid4

import pytest

from kelvin_assistant.domain.memory import (
    MemoryEmbedding,
    MemoryError,
    MemoryItem,
    MemoryKind,
    MemoryScope,
)


def test_memory_item_normalizes_text_fields_and_metadata() -> None:
    """Memory items trim content and source and freeze metadata."""

    memory = MemoryItem(
        scope=MemoryScope.USER,
        kind=MemoryKind.PREFERENCE,
        content="  The user prefers step-by-step explanations.  ",
        source="  manual-test  ",
        metadata={"topic": "communication"},
    )

    assert memory.content == "The user prefers step-by-step explanations."
    assert memory.source == "manual-test"
    assert memory.confidence == 1.0
    assert memory.metadata == {"topic": "communication"}
    assert isinstance(memory.metadata, MappingProxyType)
    assert memory.is_active is True


@pytest.mark.parametrize(
    ("content", "source", "confidence"),
    [
        ("", "manual-test", 1.0),
        ("Useful memory", "", 1.0),
        ("Useful memory", "manual-test", -0.1),
        ("Useful memory", "manual-test", 1.1),
    ],
)
def test_memory_item_rejects_invalid_values(
    content: str,
    source: str,
    confidence: float,
) -> None:
    """Memory items reject empty text fields and invalid confidence."""

    with pytest.raises(MemoryError):
        MemoryItem(
            scope=MemoryScope.USER,
            kind=MemoryKind.FACT,
            content=content,
            source=source,
            confidence=confidence,
        )


def test_memory_item_reports_deleted_and_expired_state() -> None:
    """Memory items expose active/deleted/expired state."""

    now = datetime.now(UTC)

    deleted = MemoryItem(
        scope=MemoryScope.USER,
        kind=MemoryKind.FACT,
        content="Deleted memory",
        source="manual-test",
        deleted_at=now,
    )
    expired = MemoryItem(
        scope=MemoryScope.USER,
        kind=MemoryKind.FACT,
        content="Expired memory",
        source="manual-test",
        expires_at=now - timedelta(seconds=1),
    )

    assert deleted.is_deleted is True
    assert deleted.is_active is False
    assert expired.is_expired is True
    assert expired.is_active is False


def test_memory_embedding_normalizes_model_and_requires_vector() -> None:
    """Memory embeddings require a model name and non-empty vector."""

    memory_id = uuid4()
    embedding = MemoryEmbedding(
        memory_id=memory_id,
        embedding_model=" nomic-embed-text ",
        embedding=(0.1, 0.2, 0.3),
    )

    assert embedding.memory_id == memory_id
    assert embedding.embedding_model == "nomic-embed-text"
    assert embedding.embedding == (0.1, 0.2, 0.3)

    with pytest.raises(MemoryError, match="Embedding cannot be empty"):
        MemoryEmbedding(
            memory_id=memory_id,
            embedding_model="nomic-embed-text",
            embedding=(),
        )
