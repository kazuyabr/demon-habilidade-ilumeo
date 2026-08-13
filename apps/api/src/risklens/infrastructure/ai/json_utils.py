"""Robust JSON extraction from LLM output.

Local models (gemma-3-4b) frequently wrap JSON in ```json fences, add
markdown, or truncate. This parser tries, in order: raw parse, strip code
fences, slice the outermost {...} block. Raises a clear error if all fail —
the caller decides whether to retry with a repair prompt.
"""

from __future__ import annotations

import json
import re


def parse_json_output(raw: str) -> dict | list:
    text = raw.strip()
    if not text:
        raise ValueError("empty LLM output")

    # 1) direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) strip markdown code fences (```json ... ```)
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3) slice the outermost balanced {...} (or [...]) block
    sliced = _slice_balanced(text)
    if sliced is not None:
        try:
            return json.loads(sliced)
        except json.JSONDecodeError:
            pass

    raise ValueError("could not parse JSON from LLM output")


def _slice_balanced(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        start = text.find("[")
        if start == -1:
            return None
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
