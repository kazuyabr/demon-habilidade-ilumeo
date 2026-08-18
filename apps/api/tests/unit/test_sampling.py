"""Unit tests for provider-gated sampling kwargs and runtime knob registration."""

from __future__ import annotations

from risklens.infrastructure.ai import runtime
from risklens.infrastructure.ai.llm_provider import _sampling_kwargs

CFG = {
    "top_p": 0.9,
    "sampling_top_k": 40,
    "min_p": 0.05,
    "frequency_penalty": 0.5,
    "presence_penalty": 0.3,
    "seed": 123,
}


def test_runtime_fields_include_advanced_knobs() -> None:
    for key in (
        "top_p",
        "sampling_top_k",
        "min_p",
        "frequency_penalty",
        "presence_penalty",
        "seed",
        "agent_max_chars_per_chunk",
        "agent_max_evidence_chars",
    ):
        assert key in runtime.RUNTIME_FIELDS


def test_sampling_omits_unsupported_and_defaults() -> None:
    # LM Studio/Ollama-like: everything supported.
    kwargs = _sampling_kwargs(CFG, top_k=True, min_p=True, penalties=True, seed=True)
    assert kwargs == {
        "top_p": 0.9,
        "top_k": 40,
        "min_p": 0.05,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.3,
        "seed": 123,
    }


def test_sampling_strict_openai_excludes_top_k_and_min_p() -> None:
    kwargs = _sampling_kwargs(CFG, penalties=True, seed=True)
    assert "top_k" not in kwargs
    assert "min_p" not in kwargs
    assert kwargs["top_p"] == 0.9
    assert kwargs["seed"] == 123


def test_sampling_anthropic_has_no_penalties() -> None:
    kwargs = _sampling_kwargs(CFG, top_k=True)
    assert kwargs.get("top_k") == 40
    assert "frequency_penalty" not in kwargs
    assert "presence_penalty" not in kwargs
    assert "seed" not in kwargs


def test_sampling_seed_off_when_not_requested() -> None:
    kwargs = _sampling_kwargs(CFG, top_k=True, penalties=True)
    assert "seed" not in kwargs


def test_sampling_defaults_emit_nothing_extra() -> None:
    kwargs = _sampling_kwargs({"top_p": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0})
    assert kwargs == {"top_p": 1.0}
