"""Unit tests for the resilient JSON parser (LLM output)."""

from __future__ import annotations

import pytest

from risklens.infrastructure.ai.json_utils import parse_json_output


def test_direct_json() -> None:
    assert parse_json_output('{"a": 1}') == {"a": 1}


def test_fenced_json() -> None:
    raw = '```json\n{"a": 1}\n```'
    assert parse_json_output(raw) == {"a": 1}


def test_fence_without_lang() -> None:
    raw = '```\n{"a": 1}\n```'
    assert parse_json_output(raw) == {"a": 1}


def test_markdown_wrapped() -> None:
    raw = 'Aqui está:\n{"a": 1}\n\nFim.'
    assert parse_json_output(raw) == {"a": 1}


def test_truncated_but_balanced() -> None:
    raw = '{"a": {"b": [1, 2]}, "c": null}} extra'
    assert parse_json_output(raw) == {"a": {"b": [1, 2]}, "c": None}


def test_garbage_raises() -> None:
    with pytest.raises(ValueError):
        parse_json_output("isto não é json nenhum")


def test_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_json_output("   ")
