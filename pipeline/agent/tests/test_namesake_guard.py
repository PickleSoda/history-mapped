"""Temporal namesake guard: same name, different era.

Bare regnal labels ('Philip II', 'Charles V') match existing rows by exact name,
alias or QID, but the name guards cannot tell namesakes apart — the Macedonian
'Philip II' (382-336 BCE) ended up ruling Spain in 1556 and Charles V of France
(1338-1380) the Holy Roman Empire in 1519. Dates can. Mirrors
api/tests/Unit/EntityReferenceResolverTest (temporalFit / pickNamesake).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from pipeline.agent.graph.nodes.approval_gate import approval_gate
from pipeline.agent.graph.nodes.build_diff import build_diff
from pipeline.agent.graph.nodes.commit_writer import _entity_to_jsonl_record, _record_identity_span
from pipeline.agent.graph.nodes.db_lookup import db_lookup
from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
from pipeline.agent.graph.nodes.validate import validate
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate, ParsedEvent
from pipeline.agent.schemas.relations import CandidateRelation, CommittedChange
from pipeline.agent.tools.disambiguation import (
    NAMESAKE_AMBIGUOUS,
    pick_namesake,
    span_of_dates,
    temporal_fit,
    temporal_gap,
)

MACEDON = {"entity_id": "philip-macedon", "name": "Philip II", "entity_type": "person",
           "wikidata_id": "Q130650", "start_year": -382, "end_year": -336}
SPAIN = {"entity_id": "philip-spain", "name": "Philip II", "entity_type": "person",
         "wikidata_id": "Q83229", "start_year": 1527, "end_year": 1598}
CHARLES_FRANCE = {"entity_id": "charles-france", "name": "Charles V", "entity_type": "person",
                  "wikidata_id": "Q167782", "start_year": 1338, "end_year": 1380}
CHARLES_HRE = {"entity_id": "charles-hre", "name": "Charles V", "entity_type": "person",
               "wikidata_id": "Q34396", "start_year": 1500, "end_year": 1558}
UNDATED = {"entity_id": "philip-undated", "name": "Philip II", "entity_type": "person",
           "wikidata_id": None, "start_year": None, "end_year": None}


# ── temporal_fit / temporal_gap ─────────────────────────────────────────────

@pytest.mark.parametrize("etype,a,b,expected", [
    # Namesakes: centuries apart.
    ("person", (-382, -336), (1527, 1598), "conflict"),
    ("person", (1338, 1380), (1500, 1558), "conflict"),     # Charles V of France vs HRE
    ("person", (1519, 1519), (1338, 1380), "conflict"),     # HRE election vs the French king
    # The same person, slightly different dates: reign vs lifespan, one point.
    ("person", (1556, 1598), (1527, 1598), "match"),
    ("person", (1519, 1519), (1500, 1558), "match"),
    ("person", (1602, 1602), (1527, 1598), "near"),         # 4y after death: still him
    ("person", (1650, 1650), (1527, 1598), "near"),         # within 60y
    ("person", (1690, 1690), (1527, 1598), "conflict"),
    # A lone round-century year is a century-precision date (±100):
    # Catualda (c. 19 CE) stored as '100'; Tefnakht (c. 728 BCE) as '-800'.
    ("person", (19, 19), (100, 100), "match"),
    ("person", (-728, -728), (-800, -800), "match"),
    ("person", (1700, 1700), (1527, 1598), "near"),         # '1700' = 1600-1800
    ("person", (1900, 1900), (1527, 1598), "conflict"),
    # Before 1000 BCE chronologies disagree by decades, so the tolerance widens:
    # Parshatatar of Mitanni dated -1524 vs a -1460..-1440 row (64y) is him…
    ("person", (-1524, -1524), (-1460, -1440), "near"),
    # …whereas 64y in the 16th century CE is not.
    ("person", (1462, 1462), (1527, 1598), "conflict"),
    # Sign-insensitive: 'Augustus rules Gallia 27' (= 27 BCE).
    ("person", (27, 27), (-63, 14), "match"),
    # Polities / places are never date-checked (generic rows serve many eras).
    ("political_entity", (639, 969), (-3150, -30), "unknown"),
    ("city", (1500, 1600), (-500, -400), "unknown"),
    # Either side undated.
    ("person", None, (1527, 1598), "unknown"),
    ("person", (1527, 1598), None, "unknown"),
])
def test_temporal_fit(etype, a, b, expected):
    assert temporal_fit(etype, a, b) == expected


def test_temporal_gap_and_spans():
    assert temporal_gap((1556, 1598), (1527, 1598)) == 0
    # 1863y apart; the BCE/CE mirror (336-382 CE) is still 1145y away.
    assert temporal_gap((-382, -336), (1527, 1598)) == 1145
    assert temporal_gap((1556, 1556), (1338, 1380)) == 176
    assert temporal_gap(None, (1, 2)) is None
    assert span_of_dates("-382", "-336") == (-382, -336)
    assert span_of_dates("1556-01-15", None) == (1556, 1556)
    assert span_of_dates("334 BCE", 1598) == (-334, 1598)
    assert span_of_dates(None, None) is None


# ── pick_namesake ───────────────────────────────────────────────────────────

def test_pick_namesake_chooses_the_date_compatible_row():
    assert pick_namesake([MACEDON, SPAIN], (1556, 1598)) == (SPAIN, "match")
    assert pick_namesake([MACEDON, SPAIN], (-359, -336)) == (MACEDON, "match")
    assert pick_namesake([CHARLES_FRANCE, CHARLES_HRE], (1519, 1519)) == (CHARLES_HRE, "match")
    assert pick_namesake([CHARLES_FRANCE, CHARLES_HRE], (1364, 1380)) == (CHARLES_FRANCE, "match")


def test_pick_namesake_rejects_a_lone_incompatible_row():
    assert pick_namesake([MACEDON], (1556, 1598)) == (None, NAMESAKE_AMBIGUOUS)
    assert pick_namesake([CHARLES_FRANCE], (1519, 1519)) == (None, NAMESAKE_AMBIGUOUS)


def test_pick_namesake_undated_reference_between_dated_namesakes_is_ambiguous():
    assert pick_namesake([MACEDON, SPAIN], None) == (None, NAMESAKE_AMBIGUOUS)


def test_pick_namesake_keeps_pre_guard_behaviour_without_a_signal():
    # One row, or undated / mutually compatible rows: the first wins as before.
    assert pick_namesake([MACEDON], None) == (MACEDON, "unknown")
    assert pick_namesake([UNDATED, MACEDON], None) == (UNDATED, "unknown")
    duplicate = {**SPAIN, "entity_id": "philip-spain-dup", "start_year": 1556, "end_year": 1598}
    assert pick_namesake([SPAIN, duplicate], (1580, 1580)) == (SPAIN, "match")
    assert pick_namesake([], (1, 2)) == (None, "none")


def test_pick_namesake_prefers_dated_match_over_undated_row():
    assert pick_namesake([UNDATED, MACEDON, SPAIN], (1556, 1598)) == (SPAIN, "match")
    # Only an incompatible dated row and an undated one: the undated one.
    assert pick_namesake([MACEDON, UNDATED], (1556, 1598)) == (UNDATED, "unknown")


def test_pick_namesake_unique_mode_for_aliases():
    a = {**SPAIN, "entity_id": "a"}
    b = {**SPAIN, "entity_id": "b"}
    assert pick_namesake([a, b], (1556, 1598), unique=True) == (None, "ambiguous")
    assert pick_namesake([MACEDON, a], (1556, 1598), unique=True) == (a, "match")


def test_pick_namesake_skips_untyped_checks_for_polities():
    egypt_old = {"entity_id": "e1", "entity_type": "political_entity", "start_year": -3150, "end_year": -30}
    egypt_new = {"entity_id": "e2", "entity_type": "political_entity", "start_year": 1922, "end_year": None}
    assert pick_namesake([egypt_old, egypt_new], (639, 969)) == (egypt_old, "unknown")


# ── db_lookup ───────────────────────────────────────────────────────────────

def _state(candidates, relations=(), events=()):
    return {
        "run_id": "namesake_test",
        "raw_input": "",
        "parsed_events": list(events),
        "candidate_entities": list(candidates),
        "candidate_relations": list(relations),
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_wikidata_id")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_picks_the_spanish_philip_by_candidate_dates(mock_name, mock_qid):
    mock_name.return_value = [MACEDON, SPAIN]
    mock_qid.return_value = []
    state = db_lookup(_state([CandidateEntity(label="Philip II", entity_type="person",
                                              start_date="1527", end_date="1598")]))
    enriched = state["enriched_entities"][0]
    assert enriched.existing_entity is True
    assert enriched.wikidata_match["existing_entity"]["entity_id"] == "philip-spain"
    assert enriched.namesake_flag is None


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_wikidata_id")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_never_matches_macedon_for_a_16th_century_philip(mock_name, mock_qid):
    # Only the Macedonian row exists: the candidate becomes a new entity, flagged.
    mock_name.return_value = [MACEDON]
    mock_qid.return_value = [MACEDON]  # even the (wrong) Macedonian QID is refused
    state = db_lookup(_state([CandidateEntity(label="Philip II", entity_type="person",
                                              start_date="1527", end_date="1598",
                                              wikidata_id="Q130650")]))
    enriched = state["enriched_entities"][0]
    assert enriched.existing_entity is False
    assert enriched.wikidata_match is None
    assert enriched.namesake_flag == NAMESAKE_AMBIGUOUS
    assert enriched.identity_span == [1527, 1598]


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_dates_an_undated_candidate_by_its_relations(mock_name):
    # Charles V carries no dates, but 'Charles V rules Holy Roman Empire 1519'.
    mock_name.return_value = [CHARLES_FRANCE, CHARLES_HRE]
    relations = [
        CandidateRelation(source_label="Charles V", target_label="Holy Roman Empire",
                          relationship_type="rules", start_date="1519", end_date="1556"),
        # Posthumous-capable types are no temporal signal.
        CandidateRelation(source_label="Charles V", target_label="Erasmus",
                          relationship_type="influenced_by", start_date="1300"),
    ]
    state = db_lookup(_state([CandidateEntity(label="Charles V", entity_type="person")], relations))
    enriched = state["enriched_entities"][0]
    assert enriched.wikidata_match["existing_entity"]["entity_id"] == "charles-hre"
    assert enriched.identity_span == [1519, 1556]


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_falls_back_to_the_source_event_dates(mock_name):
    mock_name.return_value = [CHARLES_FRANCE, CHARLES_HRE]
    events = [ParsedEvent(label="Treaty of Bretigny", start_date="1360", end_date="1360")]
    candidate = CandidateEntity(label="Charles V", entity_type="person", source_event="Treaty of Bretigny")
    state = db_lookup(_state([candidate], events=events))
    assert state["enriched_entities"][0].wikidata_match["existing_entity"]["entity_id"] == "charles-france"


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_undated_candidate_between_dated_namesakes_is_flagged(mock_name):
    mock_name.return_value = [MACEDON, SPAIN]
    state = db_lookup(_state([CandidateEntity(label="Philip II", entity_type="person")]))
    enriched = state["enriched_entities"][0]
    assert enriched.existing_entity is False
    assert enriched.namesake_flag == NAMESAKE_AMBIGUOUS
    assert "1 namesake-ambiguous" in state["audit_log"][-1].output_summary


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_wikidata_id")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_qid_settles_an_ambiguous_name(mock_name, mock_qid):
    mock_name.return_value = [MACEDON, SPAIN]
    mock_qid.return_value = [SPAIN]
    state = db_lookup(_state([CandidateEntity(label="Philip II", entity_type="person", wikidata_id="Q83229")]))
    enriched = state["enriched_entities"][0]
    assert enriched.wikidata_match["existing_entity"]["entity_id"] == "philip-spain"
    assert enriched.namesake_flag is None


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_same_person_with_slightly_different_dates_still_matches(mock_name):
    mock_name.return_value = [MACEDON, SPAIN]
    # Reign dates (1556-1598) vs the row's lifespan; and a date 30y off.
    for start, end in (("1556", "1598"), ("1620", None)):
        state = db_lookup(_state([CandidateEntity(label="Philip II", entity_type="person",
                                                  start_date=start, end_date=end)]))
        assert state["enriched_entities"][0].wikidata_match["existing_entity"]["entity_id"] == "philip-spain"


# ── approval_gate / commit_writer / resolve_entity_ids ─────────────────────

def _flagged(label="Philip II", confidence_bonus=0.6):
    return EnrichedCandidate(
        candidate=CandidateEntity(label=label, entity_type="person", start_date="1527", end_date="1598"),
        wikidata_match={"qid": "Q83229"},
        system_confidence=confidence_bonus,
        summary="s",
        namesake_flag=NAMESAKE_AMBIGUOUS,
        identity_span=[1527, 1598],
    )


@pytest.mark.parametrize("run_id,precomputed", [
    ("campaign_e10__iberia__habsburg-spain", True),  # campaign handoff
    ("plain_run", False),                            # any run: identity in doubt
])
def test_approval_gate_commits_a_namesake_as_needs_review(run_id, precomputed):
    state = _state([])
    state.update(run_id=run_id, summaries_precomputed=precomputed, enriched_entities=[_flagged()])
    diff = approval_gate(build_diff(validate(state)))["proposed_diff"]
    [entity] = diff.create_entities
    assert entity.verification_status == "needs_review"
    assert NAMESAKE_AMBIGUOUS in entity.validation_flags
    record = _entity_to_jsonl_record(entity, run_id)
    assert record["verification_status"] == "needs_review"
    assert NAMESAKE_AMBIGUOUS in record["validation_flags"]


def test_commit_record_carries_identity_span_only_when_undated():
    dated = _flagged()
    assert "_identity_span" not in _entity_to_jsonl_record(dated, "r")
    assert _record_identity_span(_entity_to_jsonl_record(dated, "r")) == [1527, 1598]
    undated = EnrichedCandidate(candidate=CandidateEntity(label="Philip II", entity_type="person"),
                                summary="s", identity_span=[1556, 1598])
    record = _entity_to_jsonl_record(undated, "r")
    assert record["_identity_span"] == [1556, 1598]
    assert _record_identity_span(record) == [1556, 1598]


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_wikidata_id")
def test_resolve_ids_maps_the_new_row_not_the_older_namesake(mock_qid, mock_name):
    new_spain = {**SPAIN, "entity_id": "new-philip"}
    mock_qid.return_value = [MACEDON]  # a namesake's QID: refused by date
    mock_name.return_value = [MACEDON, new_spain]
    now = datetime.now(timezone.utc).isoformat()
    state = _state([])
    state["committed"] = [CommittedChange(change_type="entity", committed_at=now, batch_id="b", record={
        "name": "Philip II", "entity_type": "person", "wikidata_id": "Q130650",
        "identity_span": [1527, 1598]})]
    assert resolve_entity_ids(state)["entity_id_map"] == {"Philip II": "new-philip"}


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_name")
def test_resolve_ids_leaves_an_ambiguous_namesake_unmapped(mock_name):
    mock_name.return_value = [MACEDON, SPAIN]
    now = datetime.now(timezone.utc).isoformat()
    state = _state([])
    state["committed"] = [CommittedChange(change_type="entity", committed_at=now, batch_id="b", record={
        "name": "Philip II", "entity_type": "person", "wikidata_id": None})]
    assert resolve_entity_ids(state)["entity_id_map"] == {}
