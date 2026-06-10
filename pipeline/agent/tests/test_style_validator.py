"""Tests for style_validator.py"""

from __future__ import annotations

from pipeline.agent.style_validator import (
    validate_entity_summary,
    validate_relation_description,
    validate_all,
    StyleViolation,
)


# ─── Entity Summary Tests ────────────────────────────────────────────────────

def test_summary_passes_good_example():
    result = validate_entity_summary(
        "Ruled the Kingdom of Georgia from 1089 to 1125 and led the decisive victory at the Battle of Didgori in 1121.",
        entity_name="David IV of Georgia",
    )
    assert result.passed
    assert result.content_type == "entity_summary"
    assert not any(v.severity == "error" for v in result.violations)


def test_summary_fails_self_name():
    result = validate_entity_summary(
        "David IV of Georgia ruled the Kingdom of Georgia from 1089 to 1125.",
        entity_name="David IV of Georgia",
    )
    assert not result.passed
    assert any(v.rule == "no_self_name" for v in result.violations)


def test_summary_fails_generic_reference():
    result = validate_entity_summary(
        "This person ruled Georgia from 1089 to 1125.",
        entity_name="David IV",
    )
    assert not result.passed
    assert any(v.rule == "no_generic_self_reference" for v in result.violations)


def test_summary_fails_vague_phrase():
    result = validate_entity_summary(
        "Played a role in Georgian history during the 12th century.",
        entity_name="David IV",
    )
    assert not result.passed
    assert any(v.rule == "no_vague_phrases" for v in result.violations)


def test_summary_warns_missing_temporal():
    result = validate_entity_summary(
        "Led the Georgian kingdom and expanded its territory.",
        entity_name="David IV",
    )
    # Should pass (no errors) but have a temporal warning
    assert result.passed
    assert any(v.rule == "temporal_scope" for v in result.violations)


def test_summary_fails_too_long():
    result = validate_entity_summary(
        "A. " * 150,  # Way too many sentences
        entity_name="Test Entity",
    )
    assert not result.passed
    assert any(v.rule == "max_sentences" for v in result.violations)


def test_summary_fails_empty():
    result = validate_entity_summary("", entity_name="Test")
    assert not result.passed
    assert any(v.rule == "non_empty" for v in result.violations)


def test_summary_fails_bce_exposure():
    result = validate_entity_summary(
        "Existed in -2000 as a major power.",
        entity_name="Ancient Egypt",
    )
    assert not result.passed
    assert any(v.rule == "bce_format" for v in result.violations)


def test_summary_passes_with_bce():
    result = validate_entity_summary(
        "Flourished around 2000 BCE along the Nile Valley.",
        entity_name="Ancient Egypt",
    )
    assert result.passed


# ─── Relation Description Tests ──────────────────────────────────────────────

def test_relation_passes_good_example():
    result = validate_relation_description(
        "Commanded the Georgian forces at the Battle of Didgori on August 12, 1121."
    )
    assert result.passed


def test_relation_fails_vague():
    result = validate_relation_description(
        "Was involved in the battle."
    )
    assert not result.passed
    assert any(v.rule == "no_vague_phrases" for v in result.violations)


def test_relation_warns_no_temporal():
    result = validate_relation_description(
        "Commanded the Georgian forces at the Battle of Didgori."
    )
    assert result.passed
    assert any(v.rule == "temporal_qualifier" for v in result.violations)


def test_relation_fails_empty():
    result = validate_relation_description("")
    assert not result.passed


def test_relation_fails_bce_exposure():
    result = validate_relation_description(
        "Founded the city in -3000."
    )
    assert not result.passed
    assert any(v.rule == "bce_format" for v in result.violations)


# ─── Batch Validation Tests ──────────────────────────────────────────────────

def test_validate_all_aggregates_results():
    summaries = {
        "David IV": "Ruled Georgia from 1089 to 1125.",
        "Bad Entity": "This entity was involved in things.",
    }
    relations = {
        "David IV|participated_in|Didgori": "Commanded forces at Didgori in 1121.",
        "Vague|related_to|Something": "Was related to something.",
    }
    result = validate_all(summaries, relations)
    assert not result["passed"]
    assert result["error_count"] > 0
    assert "Bad Entity" in result["entity_results"]
    assert not result["entity_results"]["Bad Entity"]["passed"]
    assert "Vague|related_to|Something" in result["relation_results"]
    assert not result["relation_results"]["Vague|related_to|Something"]["passed"]
