"""Pin: LLMs emit year fields as JSON numbers; the schemas must coerce to str.

A bare integer start_date used to raise a ValidationError that sank
extract_candidates and collapsed an entire run's commits.
"""
from __future__ import annotations

from pipeline.agent.schemas.entities import CandidateEntity, ParsedEvent
from pipeline.agent.schemas.relations import CandidateRelation


def test_candidate_entity_coerces_int_date_to_str():
    e = CandidateEntity(label="Alexander the Great", entity_type="person", start_date=-331)
    assert e.start_date == "-331"


def test_parsed_event_coerces_int_dates():
    ev = ParsedEvent(label="Battle of Issus", start_date=-333, end_date=-333)
    assert ev.start_date == "-333"
    assert ev.end_date == "-333"


def test_candidate_relation_coerces_int_date():
    r = CandidateRelation(
        source_label="Alexander the Great",
        target_label="Battle of Issus",
        relationship_type="victorious_at",
        start_date=-333,
    )
    assert r.start_date == "-333"
