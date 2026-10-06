"""Campaign approval-gate policy: reviewed campaign handoffs commit entities held
only for a missing/weak Wikidata match or missing geometry as needs_review instead
of holding them (which left the run's relations to them dangling). Other runs keep
the plain confidence gate."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.agent.graph.nodes.approval_gate import approval_gate, is_campaign_handoff
from pipeline.agent.graph.nodes.build_diff import build_diff
from pipeline.agent.graph.nodes.commit_writer import _entity_to_jsonl_record, commit_writer
from pipeline.agent.graph.nodes.validate import validate
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation

CAMPAIGN_RUN = "campaign_e04__aegean__classical-greece"
POINT = {"type": "Point", "coordinates": [23.7, 37.9]}


def _entity(label, etype, qid=None, bonus=0.0, geometry=None):
    return EnrichedCandidate(
        candidate=CandidateEntity(label=label, entity_type=etype),
        wikidata_match={"qid": qid} if qid else None,
        system_confidence=bonus,
        geometry=geometry,
        summary="s",
    )


def _state(entities, relations=(), run_id=CAMPAIGN_RUN, precomputed=True):
    return {
        "run_id": run_id,
        "raw_input": "",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": list(relations),
        "enriched_entities": list(entities),
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
        "summaries_precomputed": precomputed,
    }


def _gate(state):
    return approval_gate(build_diff(validate(state)))


def _by_label(diff):
    return {e.candidate.label: e for e in diff.create_entities}


def test_campaign_detection_needs_both_signals():
    assert is_campaign_handoff({"run_id": CAMPAIGN_RUN, "summaries_precomputed": True})
    assert not is_campaign_handoff({"run_id": CAMPAIGN_RUN, "summaries_precomputed": False})
    assert not is_campaign_handoff({"run_id": "handoff_pilot", "summaries_precomputed": True})
    assert not is_campaign_handoff({"run_id": CAMPAIGN_RUN})  # full-LLM run, key never set


def test_campaign_commits_wikidata_and_geometry_shortfalls_as_needs_review():
    state = _gate(_state([
        _entity("Pericles", "person"),                                  # 0.95 < 0.97
        _entity("Delian League", "political_entity", qid="Q1", geometry=POINT),  # weak match: 0.95 < 0.97
        _entity("Eion", "city", qid="Q2"),                              # matched, no geometry: 0.90 < 0.94
        _entity("Amphipolis", "city"),                                  # neither: 0.90 < 0.94
        _entity("Battle of Marathon", "event_battle", qid="Q3", bonus=0.4, geometry=POINT),
    ]))
    diff = state["proposed_diff"]
    committed = _by_label(diff)
    assert set(committed) == {"Pericles", "Delian League", "Eion", "Amphipolis", "Battle of Marathon"}
    assert diff.review_items == []
    assert committed["Pericles"].verification_status == "needs_review"
    assert committed["Pericles"].validation_flags == ["no_wikidata_match"]
    assert committed["Delian League"].validation_flags == ["low_wikidata_match"]
    assert committed["Eion"].validation_flags == ["missing_geometry"]
    assert committed["Amphipolis"].validation_flags == ["no_wikidata_match", "missing_geometry"]
    # A confident entity is committed as before: no unverified status.
    assert committed["Battle of Marathon"].verification_status is None
    assert committed["Battle of Marathon"].validation_flags == []
    assert "(4 as needs_review)" in state["audit_log"][-1].output_summary


def test_non_campaign_run_keeps_holding_low_confidence_entities():
    for run_id, precomputed in (("topic_classical_greece", False), ("handoff_pilot", True),
                                (CAMPAIGN_RUN, False)):
        state = _gate(_state([_entity("Pericles", "person"), _entity("Amphipolis", "city")],
                             run_id=run_id, precomputed=precomputed))
        diff = state["proposed_diff"]
        assert diff.create_entities == []
        assert [i["label"] for i in diff.review_items] == ["Pericles", "Amphipolis"]


def test_campaign_still_holds_a_shortfall_it_cannot_explain():
    # Fully corroborated (QID + bonus + geometry) yet under threshold: not a
    # Wikidata/geometry shortfall, so the gate keeps holding it.
    enriched = _entity("Athens", "city", qid="Q1524", bonus=0.4, geometry=POINT)
    state = _state([enriched])
    validate(state)
    build_diff(state)
    enriched.final_confidence = 0.5
    approval_gate(state)
    diff = state["proposed_diff"]
    assert diff.create_entities == []
    assert diff.review_items[0]["label"] == "Athens"
    assert enriched.verification_status is None


def test_jsonl_record_carries_status_only_when_unverified():
    plain = _entity_to_jsonl_record(_entity("Athens", "city", qid="Q1524"), CAMPAIGN_RUN)
    assert "verification_status" not in plain and "validation_flags" not in plain
    unverified = _entity("Amphipolis", "city")
    unverified.verification_status = "needs_review"
    unverified.validation_flags = ["no_wikidata_match", "missing_geometry"]
    rec = _entity_to_jsonl_record(unverified, CAMPAIGN_RUN)
    assert rec["verification_status"] == "needs_review"
    assert rec["validation_flags"] == ["no_wikidata_match", "missing_geometry"]


@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
@patch("pipeline.agent.graph.nodes.commit_writer.AgentConfig")
def test_campaign_entity_and_its_relations_reach_the_import(mock_cfg, mock_run, tmp_path):
    mock_cfg.return_value = SimpleNamespace(output_dir=str(tmp_path), container_output_dir="/c")
    mock_run.return_value = {"returncode": 0, "stdout": "OK", "stderr": ""}
    rel = CandidateRelation(source_label="Pericles", target_label="Battle of Marathon",
                            relationship_type="participated_in")
    state = _gate(_state(
        [_entity("Pericles", "person"),
         _entity("Battle of Marathon", "event_battle", qid="Q3", bonus=0.4, geometry=POINT)],
        relations=[rel],
    ))
    commit_writer(state)
    run_dir = tmp_path / CAMPAIGN_RUN
    records = {r["name"]: r for r in map(json.loads, (run_dir / "entities_to_create.jsonl").read_text().splitlines())}
    assert records["Pericles"]["verification_status"] == "needs_review"
    assert records["Pericles"]["validation_flags"] == ["no_wikidata_match"]
    assert "verification_status" not in records["Battle of Marathon"]
    relations = (run_dir / "relations.jsonl").read_text().splitlines()
    assert [json.loads(r)["source_name"] for r in relations] == ["Pericles"]
    assert not (run_dir / "review_items.jsonl").exists()
    assert {c.record.get("name") for c in state["committed"] if c.change_type == "entity"} == {
        "Pericles", "Battle of Marathon"}


# --- Relations held only for their predicate threshold (rules/governed_by 0.97) ---

def _rel(src, rtype, tgt, **kw):
    return CandidateRelation(source_label=src, target_label=tgt, relationship_type=rtype, **kw)


def _relations_by_type(diff):
    return {r.relationship_type: r for r in diff.create_relations}


def test_campaign_commits_below_threshold_relations_at_medium():
    state = _gate(_state(
        [_entity("Augustus", "person"), _entity("Roman Empire", "political_entity"),
         _entity("Battle of Actium", "event_battle", qid="Q3", bonus=0.4, geometry=POINT)],
        relations=[_rel("Augustus", "rules", "Roman Empire"),
                   _rel("Roman Empire", "governed_by", "Augustus"),
                   _rel("Augustus", "participated_in", "Battle of Actium")],
    ))
    diff = state["proposed_diff"]
    rels = _relations_by_type(diff)
    assert set(rels) == {"rules", "governed_by", "participated_in"}
    assert [i for i in diff.review_items if i["type"] == "relation"] == []
    assert rels["rules"].final_confidence == 0.95  # uncorroborated ends: under 0.97
    assert rels["rules"].commit_confidence == "medium"
    assert rels["governed_by"].commit_confidence == "medium"
    # Cleared its own threshold: committed as before, no explicit confidence.
    assert rels["participated_in"].commit_confidence is None
    assert "(2 at medium)" in state["audit_log"][-1].output_summary


def test_non_campaign_run_keeps_holding_uncorroborated_high_risk_relations():
    for run_id, precomputed in (("topic_rome", False), ("handoff_pilot", True), (CAMPAIGN_RUN, False)):
        state = _gate(_state(
            [_entity("Augustus", "person", qid="Q1405"), _entity("Roman Empire", "political_entity")],
            relations=[_rel("Augustus", "rules", "Roman Empire"), _rel("Augustus", "at_war_with", "Roman Empire")],
            run_id=run_id, precomputed=precomputed,
        ))
        diff = state["proposed_diff"]
        assert [r.relationship_type for r in diff.create_relations] == ["at_war_with"]
        assert [i["relation_id"] for i in diff.review_items if i["type"] == "relation"] == [
            "Augustus|rules|Roman Empire"]
        assert diff.create_relations[0].commit_confidence is None


def test_relation_with_both_ends_on_wikidata_clears_the_high_risk_threshold():
    # One end resolved now (qid), the other an existing DB row with a QID.
    existing = EnrichedCandidate(
        candidate=CandidateEntity(label="Roman Empire", entity_type="political_entity"),
        wikidata_match={"existing_entity": {"entity_id": "e-1", "wikidata_id": "Q2277"}},
        existing_entity=True,
    )
    state = _gate(_state(
        [_entity("Augustus", "person", qid="Q1405", bonus=0.3), existing],
        relations=[_rel("Augustus", "rules", "Roman Empire")],
        run_id="topic_rome", precomputed=False,
    ))
    diff = state["proposed_diff"]
    assert [r.final_confidence for r in diff.create_relations] == [0.97]
    assert diff.review_items == []
    assert diff.create_relations[0].commit_confidence is None


def test_gate_discards_a_handoff_supplied_commit_confidence():
    rel = _rel("Augustus", "participated_in", "Battle of Actium", commit_confidence="high")
    assert "commit_confidence" not in rel.model_dump()  # never written to candidates.json
    state = _gate(_state(
        [_entity("Augustus", "person"), _entity("Battle of Actium", "event_battle", qid="Q3", bonus=0.4, geometry=POINT)],
        relations=[rel], run_id="topic_rome", precomputed=False,
    ))
    assert state["proposed_diff"].create_relations[0].commit_confidence is None


@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
@patch("pipeline.agent.graph.nodes.commit_writer.AgentConfig")
def test_campaign_reviewed_relation_reaches_the_import_at_medium(mock_cfg, mock_run, tmp_path):
    mock_cfg.return_value = SimpleNamespace(output_dir=str(tmp_path), container_output_dir="/c")
    mock_run.return_value = {"returncode": 0, "stdout": "OK", "stderr": ""}
    state = _gate(_state(
        [_entity("Augustus", "person"),
         _entity("Battle of Actium", "event_battle", qid="Q3", bonus=0.4, geometry=POINT),
         _entity("Roman Empire", "political_entity")],
        relations=[_rel("Augustus", "rules", "Roman Empire"), _rel("Augustus", "participated_in", "Battle of Actium")],
    ))
    commit_writer(state)
    run_dir = tmp_path / CAMPAIGN_RUN
    records = {r["relationship_type"]: r for r in map(json.loads, (run_dir / "relations.jsonl").read_text().splitlines())}
    assert records["rules"]["confidence"] == "medium"
    assert records["rules"]["source_citations"]["approval"] == "campaign_review"
    assert "confidence" not in records["participated_in"]
    assert "approval" not in records["participated_in"]["source_citations"]
    assert not (run_dir / "review_items.jsonl").exists()
