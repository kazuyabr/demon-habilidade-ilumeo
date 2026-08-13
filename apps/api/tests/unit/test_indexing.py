"""Unit tests for markdown-aware chunking."""

from __future__ import annotations

from risklens.application.services.indexing_service import chunk_text


def test_sections_detected() -> None:
    text = "# Resumo\n\nTexto do resumo.\n\n## Financeiro\n\nDados financeiros aqui."
    chunks = chunk_text(text)
    sections = [meta["section"] for _, meta in chunks]
    assert "Resumo" in sections
    assert "Financeiro" in sections


def test_no_sections_uses_intro() -> None:
    text = "Parágrafo único sem títulos." * 50
    chunks = chunk_text(text)
    assert chunks
    assert chunks[0][1]["section"] == "intro"


def test_chunk_size_bounded() -> None:
    text = "a" * 5000
    chunks = chunk_text(text, target_chars=1200)
    assert all(len(content) <= 1200 for content, _ in chunks)
    assert len(chunks) >= 4


def test_empty_text_falls_back() -> None:
    chunks = chunk_text("   ")
    assert chunks  # fallback chunk
