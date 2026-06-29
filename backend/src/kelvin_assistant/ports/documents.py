"""Ports for loading and chunking knowledge documents."""

from pathlib import Path
from typing import Protocol

from kelvin_assistant.domain.knowledge import KnowledgeChunk, KnowledgeDocument


class DocumentLoaderError(RuntimeError):
    """Raised when a document cannot be loaded."""


class UnsupportedDocumentTypeError(DocumentLoaderError):
    """Raised when a document type is not supported yet."""


class DocumentLoader(Protocol):
    """Interface for loading local knowledge documents."""

    def load(self, path: Path) -> KnowledgeDocument:
        """Load a document from a local path."""
        ...


class DocumentChunker(Protocol):
    """Interface for deterministic document chunking."""

    def chunk(self, document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        """Split a document into searchable chunks."""
        ...
