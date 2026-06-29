"""Unit tests for the knowledge search command."""

from __future__ import annotations

import asyncio

import pytest

from kelvin_assistant.cli import search_knowledge
from kelvin_assistant.ports.knowledge import KnowledgeSearchResult


def test_parser_requires_query_and_collection() -> None:
    """The search command accepts query text, collection, and limit."""

    args = search_knowledge.build_parser().parse_args(
        [
            "--collection",
            "manual",
            "--limit",
            "3",
            "Hol fut az Ollama?",
        ]
    )

    assert args.collection == "manual"
    assert args.limit == 3
    assert args.query == "Hol fut az Ollama?"


def test_main_reports_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command returns success when semantic search succeeds."""

    async def fake_search_knowledge(
        query: str,
        *,
        collection_name: str,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        assert query == "Hol fut az Ollama?"
        assert collection_name == "manual"
        assert limit == 2
        return (
            KnowledgeSearchResult(
                source_uri="file:///notes.md",
                title="notes",
                chunk_index=2,
                content="Ollama a Windows hoston fut.",
                metadata={"heading": "Runtime"},
                distance=0.12,
            ),
        )

    monkeypatch.setattr(search_knowledge, "search_knowledge", fake_search_knowledge)

    exit_code = search_knowledge.main(
        [
            "--collection",
            "manual",
            "--limit",
            "2",
            "Hol fut az Ollama?",
        ]
    )

    assert exit_code == 0


def test_main_returns_failure_on_search_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command exits with a non-zero code when search fails."""

    async def fake_search_knowledge(
        query: str,
        *,
        collection_name: str,
        limit: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        raise ValueError("bad search")

    monkeypatch.setattr(search_knowledge, "search_knowledge", fake_search_knowledge)

    exit_code = search_knowledge.main(["--collection", "manual", "query"])

    assert exit_code == 1


def test_search_knowledge_rejects_empty_query() -> None:
    """Empty queries are rejected before calling external services."""

    with pytest.raises(ValueError, match="Query"):
        asyncio.run(
            search_knowledge.search_knowledge(
                " ",
                collection_name="manual",
                limit=1,
            )
        )
