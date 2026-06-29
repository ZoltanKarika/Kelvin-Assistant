"""Local filesystem document loader."""

from pathlib import Path

from kelvin_assistant.domain.knowledge import KnowledgeDocument, SupportedMimeType
from kelvin_assistant.ports.documents import (
    DocumentLoaderError,
    UnsupportedDocumentTypeError,
)

SUPPORTED_SUFFIXES: dict[str, SupportedMimeType] = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}


class LocalTextDocumentLoader:
    """Load UTF-8 Markdown and plain text files from disk."""

    def load(self, path: Path) -> KnowledgeDocument:
        """Load a supported local text document."""

        resolved_path = path.expanduser().resolve()
        mime_type = SUPPORTED_SUFFIXES.get(resolved_path.suffix.lower())
        if mime_type is None:
            raise UnsupportedDocumentTypeError(
                f"Unsupported document type: {resolved_path.suffix}"
            )

        try:
            content = resolved_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise DocumentLoaderError(f"Cannot load document: {resolved_path}") from exc

        return KnowledgeDocument(
            source_uri=str(resolved_path),
            content=content,
            mime_type=mime_type,
            title=resolved_path.stem,
            metadata={"filename": resolved_path.name},
        )
