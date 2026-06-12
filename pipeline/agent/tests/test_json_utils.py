"""Tests for the lenient LLM JSON parser."""
from __future__ import annotations

import pytest

from pipeline.agent.json_utils import parse_llm_json


def test_parses_plain_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_strips_json_fence():
    assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_strips_bare_fence():
    assert parse_llm_json('```\n{"a": 1}\n```') == {"a": 1}


def test_tolerates_raw_control_characters():
    # A literal newline inside a string value — strict json.loads rejects this,
    # which is exactly the failure that broke preprocess_transcript.
    raw = '{"cleaned_text": "line one\nline two"}'
    with pytest.raises(ValueError):
        __import__("json").loads(raw)  # confirms strict mode would fail
    assert parse_llm_json(raw)["cleaned_text"] == "line one\nline two"


def test_extracts_fenced_block_amid_prose():
    content = 'Here you go:\n```json\n{"x": [1, 2]}\n```\nHope that helps!'
    assert parse_llm_json(content) == {"x": [1, 2]}
