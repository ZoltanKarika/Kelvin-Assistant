"""Domain models for local knowledge documents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

SupportedMimeType = Literal["text/markdown", "text/plain"]


class KnowledgeDocumentError(ValueError):
    """Raised when a knowledge document violates domain rules."""


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A loaded text document before chunking."""

    source_uri: str
    content: str
    mime_type: SupportedMimeType
    title: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize and validate the loaded document."""

        source_uri = self.source_uri.strip()
        content = self.content.strip()
        title = self.title.strip() if self.title is not None else None

        if not source_uri:
            raise KnowledgeDocumentError("Document source URI cannot be empty")
        if not content:
            raise KnowledgeDocumentError("Document content cannot be empty")
        if title == "":
            title = None

        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A deterministic searchable piece of a knowledge document."""

    source_uri: str
    chunk_index: int
    content: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize and validate a chunk."""

        source_uri = self.source_uri.strip()
        content = self.content.strip()

        if not source_uri:
            raise KnowledgeDocumentError("Chunk source URI cannot be empty")
        if self.chunk_index < 0:
            raise KnowledgeDocumentError("Chunk index cannot be negative")
        if not content:
            raise KnowledgeDocumentError("Chunk content cannot be empty")

        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
