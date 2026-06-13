"""Tests for commit_writer's date-consistency guard."""
from __future__ import annotations

from pipeline.agent.graph.nodes.commit_writer import _consistent_dates, _entity_to_jsonl_record
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate


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
    record = _entity_to_jsonl_record(enriched)
    assert record["temporal_start"] == "-333"
    assert record["temporal_end"] == "-333"


def test_non_event_keeps_open_end():
    # A city may still exist — keep the null end (open-ended), don't collapse.
    enriched = EnrichedCandidate(
        candidate=CandidateEntity(label="Alexandria", entity_type="city", start_date="331 BCE"),
    )
    record = _entity_to_jsonl_record(enriched)
    assert record["temporal_start"] == "-331"
    assert record["temporal_end"] is None
