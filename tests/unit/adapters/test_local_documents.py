"""Unit tests for local document loading."""

from pathlib import Path

import pytest

from kelvin_assistant.adapters.local_documents import LocalTextDocumentLoader
from kelvin_assistant.domain.knowledge import KnowledgeDocumentError
from kelvin_assistant.ports.documents import UnsupportedDocumentTypeError


def test_loads_utf8_markdown_document(tmp_path: Path) -> None:
    """Markdown files are loaded as text/markdown documents."""

    path = tmp_path / "notes.md"
    path.write_text("# Kelvin\n\nSzia!", encoding="utf-8")
    loader = LocalTextDocumentLoader()

    document = loader.load(path)

    assert document.source_uri == str(path.resolve())
    assert document.content == "# Kelvin\n\nSzia!"
    assert document.mime_type == "text/markdown"
    assert document.title == "notes"
    assert document.metadata == {"filename": "notes.md"}


def test_loads_utf8_sig_text_document(tmp_path: Path) -> None:
    """UTF-8 BOM text files are accepted."""

    path = tmp_path / "notes.txt"
    path.write_text("Szia Kelvin!", encoding="utf-8-sig")
    loader = LocalTextDocumentLoader()

    document = loader.load(path)

    assert document.content == "Szia Kelvin!"
    assert document.mime_type == "text/plain"


def test_rejects_unsupported_document_type(tmp_path: Path) -> None:
    """Only text and Markdown documents are supported in v0.4 first pass."""

    path = tmp_path / "notes.pdf"
    path.write_text("not really a pdf", encoding="utf-8")
    loader = LocalTextDocumentLoader()

    with pytest.raises(UnsupportedDocumentTypeError):
        loader.load(path)


def test_rejects_empty_document(tmp_path: Path) -> None:
    """Empty text files are not valid knowledge documents."""

    path = tmp_path / "empty.txt"
    path.write_text("   ", encoding="utf-8")
    loader = LocalTextDocumentLoader()

    with pytest.raises(KnowledgeDocumentError):
        loader.load(path)
