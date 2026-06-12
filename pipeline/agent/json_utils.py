"""Lenient JSON parsing for LLM responses.

LLMs wrap JSON in ``` / ```json fences and frequently emit raw control
characters (literal newlines/tabs) inside string values, which the stdlib
``json.loads`` rejects in strict mode ("Invalid control character at ..."). This
helper strips fences and parses with ``strict=False`` so a single stray newline
doesn't sink a whole transcript.
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_llm_json(content: str) -> Any:
    """Parse JSON from an LLM response, tolerating code fences + control chars.

    Raises json.JSONDecodeError if the content still isn't valid JSON.
    """
    text = (content or "").strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text, strict=False)
