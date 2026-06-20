"""Tests for commit_writer's date-consistency guard."""
from __future__ import annotations

from pipeline.agent.graph.nodes.commit_writer import (
    _consistent_dates,
    _entity_to_jsonl_record,
    _relation_to_jsonl_record,
)
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


def test_drops_end_when_a_ce_year_was_mis_signed_negative():
    # The Justinian/Opium-War regression: a CE date emitted negative leaves
    # start_year > end_year. Drop the end so the entity still imports.
    assert _consistent_dates("-527", "-565") == ("-527", None)


def test_keeps_valid_bce_range():
    assert _consistent_dates("2112 BCE", "2095 BCE") == ("-2112", "-2095")


def test_keeps_valid_ce_range():
    # CE markers are stripped to a clean year by normalize_historical_date.
    assert _consistent_dates("527 CE", "565 CE") == ("527", "565")


def test_passes_through_nones_and_singletons():
    assert _consistent_dates(None, None) == (None, None)
    assert _consistent_dates("1453", None) == ("1453", None)


def test_event_with_one_bound_collapses_to_a_point():
    # A one-date battle should get start == end, not a null (open-ended) end.
    enriched = EnrichedCandidate(
        candidate=CandidateEntity(label="Battle of Issus", entity_type="event_battle", start_date="333 BCE"),
    )
    record = _entity_to_jsonl_record(enriched, "topic_test")
    assert record["temporal_start"] == "-333"
    assert record["temporal_end"] == "-333"


def test_non_event_keeps_open_end():
    # A city may still exist — keep the null end (open-ended), don't collapse.
    enriched = EnrichedCandidate(
        candidate=CandidateEntity(label="Alexandria", entity_type="city", start_date="331 BCE"),
    )
    record = _entity_to_jsonl_record(enriched, "topic_test")
    assert record["temporal_start"] == "-331"
    assert record["temporal_end"] is None


def _rel(**kw):
    base = dict(source_label="A", target_label="B", relationship_type="participated_in")
    base.update(kw)
    return CandidateRelation(**base)


def test_point_relation_mirrors_single_date_to_both_bounds():
    # A one-date point relation must record start AND end (was: only start).
    rec = _relation_to_jsonl_record(_rel(relationship_type="founded", start_date="762 CE"), "topic_test")
    assert rec["start_date"] == "762"
    assert rec["end_date"] == "762"


def test_span_relation_keeps_open_end():
    # at_war_with is a span; a lone start stays open-ended (end unknown).
    rec = _relation_to_jsonl_record(_rel(relationship_type="at_war_with", start_date="264 BCE"), "topic_test")
    assert rec["start_date"] == "-264"
    assert rec["end_date"] is None


def test_relation_gets_fallback_description_when_missing():
    rec = _relation_to_jsonl_record(
        _rel(source_label="Carthage", target_label="Rome", relationship_type="at_war_with",
             start_date="264 BCE", end_date="146 BCE"),
        "topic_test",
    )
    assert rec["description"] == "Carthage at war with Rome (264 BCE–146 BCE)."


def test_relation_keeps_generated_description():
    rec = _relation_to_jsonl_record(_rel(description="A vivid generated sentence."), "topic_test")
    assert rec["description"] == "A vivid generated sentence."


def test_relation_source_citations_include_provenance():
    rec = _relation_to_jsonl_record(
        _rel(source_event="Founding of Baghdad", source_wikidata_id="Q1"), "topic_christianity"
    )
    cites = rec["source_citations"]
    assert cites["transcript_run"] == "topic_christianity"
    assert cites["source_event"] == "Founding of Baghdad"
    assert cites["source_wikidata_id"] == "Q1"


def test_entity_source_citations_include_wikidata_and_run():
    enriched = EnrichedCandidate(
        candidate=CandidateEntity(label="Baghdad", entity_type="city"),
        wikidata_match={"qid": "Q1530"},
    )
    rec = _entity_to_jsonl_record(enriched, "topic_islamic_golden_age")
    cites = rec["source_citations"]
    assert cites["wikidata_id"] == "Q1530"
    assert cites["wikidata_url"] == "https://www.wikidata.org/wiki/Q1530"
    assert cites["transcript_run"] == "topic_islamic_golden_age"
