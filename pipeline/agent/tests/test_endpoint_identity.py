"""Relation/chronicle endpoints carry identity (entity_id / QID), not just names.

Regression for campaign link loss: an entity imported with a QID can collapse
into an existing row under a different name ("Tell Halaf" → "Guzana"), and a
db_lookup existing match is never re-imported — in both cases a name-only
relation end or chronicle ref misses.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.nodes.commit_writer import (
    _endpoint_identity_index,
    _relation_to_jsonl_record,
    commit_writer,
)
from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate, ParsedEvent
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.relations import CandidateRelation, CommittedChange

EXISTING_ID = "11111111-1111-1111-1111-111111111111"


def _existing(label, etype="political_entity", entity_id=EXISTING_ID, qid="Q146246"):
    return EnrichedCandidate(
        candidate=CandidateEntity(label=label, entity_type=etype),
        wikidata_match={"existing_entity": {
            "entity_id": entity_id, "name": label, "entity_type": etype, "wikidata_id": qid,
        }},
        existing_entity=True,
    )


def _created(label, etype="city", qid=None):
    return EnrichedCandidate(
        candidate=CandidateEntity(label=label, entity_type=etype),
        wikidata_match={"qid": qid} if qid else None,
        final_confidence=0.99,
        summary="s",
    )


def _state(**kw):
    state = {
        "run_id": "identity_test",
        "raw_input": "",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }
    state.update(kw)
    return state


def test_identity_index_covers_existing_and_created_but_not_held():
    existing = _existing("Kingdom of the Franks")
    created = _created("Tell Halaf", qid="Q2142541")
    held = _created("Dendra", qid="Q999")  # resolved a QID but held by the approval gate
    index = _endpoint_identity_index([existing, created, held], [created])
    assert index["kingdom of the franks"] == {"entity_id": EXISTING_ID, "wikidata_id": "Q146246"}
    assert index["tell halaf"] == {"wikidata_id": "Q2142541"}
    assert "dendra" not in index


def test_relation_record_carries_endpoint_ids():
    rel = CandidateRelation(source_label="Tell Halaf", target_label="Kingdom of the Franks",
                            relationship_type="part_of")
    endpoints = {
        "tell halaf": {"wikidata_id": "Q2142541"},
        "kingdom of the franks": {"entity_id": EXISTING_ID, "wikidata_id": "Q146246"},
    }
    rec = _relation_to_jsonl_record(rel, "run", endpoints)
    assert rec["source_name"] == "Tell Halaf"
    assert rec["source_wikidata_id"] == "Q2142541"
    assert "source_entity_id" not in rec
    assert rec["target_entity_id"] == EXISTING_ID
    assert rec["target_wikidata_id"] == "Q146246"


def test_relation_record_without_endpoints_keeps_legacy_shape():
    rel = CandidateRelation(source_label="A", target_label="B", relationship_type="part_of")
    rec = _relation_to_jsonl_record(rel, "run")
    assert not any(k.endswith("_entity_id") or k.endswith("_wikidata_id") for k in rec)


@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
@patch("pipeline.agent.graph.nodes.commit_writer.AgentConfig")
def test_commit_writer_writes_ids_and_review_items(mock_cfg, mock_run, tmp_path):
    mock_cfg.return_value = SimpleNamespace(output_dir=str(tmp_path), container_output_dir="/c")
    mock_run.return_value = {"returncode": 0, "stdout": "OK", "stderr": ""}
    existing = _existing("Kingdom of the Franks")
    created = _created("Tell Halaf", qid="Q2142541")
    rel = CandidateRelation(source_label="Tell Halaf", target_label="Kingdom of the Franks",
                            relationship_type="part_of", final_confidence=0.95)
    state = _state(
        enriched_entities=[existing, created],
        proposed_diff=ProposedDiff(
            run_id="identity_test",
            create_entities=[created],
            create_relations=[rel],
            review_items=[{"type": "entity", "label": "Dendra", "reason": "confidence 0.90 < threshold 0.94"}],
        ),
    )
    commit_writer(state)
    run_dir = tmp_path / "identity_test"
    rec = json.loads((run_dir / "relations.jsonl").read_text().splitlines()[0])
    assert rec["source_wikidata_id"] == "Q2142541"
    assert rec["target_entity_id"] == EXISTING_ID
    held = [json.loads(line) for line in (run_dir / "review_items.jsonl").read_text().splitlines()]
    assert held == [{"type": "entity", "label": "Dendra", "reason": "confidence 0.90 < threshold 0.94"}]


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_relationship_by_labels")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_relationship_by_entity_ids")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_wikidata_id")
def test_resolve_ids_preseeds_existing_and_links_relations_by_id(mock_qid, mock_rel_ids, mock_rel_labels):
    # "Tell Halaf" was imported with Q2142541 and merged into the row "Tell Halaf (Guzana)".
    mock_qid.return_value = [{"entity_id": "22222222-2222-2222-2222-222222222222", "name": "Tell Halaf (Guzana)"}]
    mock_rel_ids.return_value = [{"relationship_id": "33333333-3333-3333-3333-333333333333"}]
    mock_rel_labels.return_value = []
    now = datetime.now(timezone.utc).isoformat()
    state = _state(
        enriched_entities=[_existing("Kingdom of the Franks")],
        committed=[
            CommittedChange(change_type="entity", committed_at=now, batch_id="b", record={
                "name": "Tell Halaf", "entity_type": "city", "wikidata_id": "Q2142541"}),
            CommittedChange(change_type="relation", committed_at=now, batch_id="b", record={
                "source_label": "Tell Halaf", "target_label": "Kingdom of the Franks",
                "relationship_type": "part_of"}),
        ],
    )
    result = resolve_entity_ids(state)
    assert result["entity_id_map"]["Kingdom of the Franks"] == EXISTING_ID
    assert result["entity_id_map"]["Tell Halaf"] == "22222222-2222-2222-2222-222222222222"
    assert result["relation_id_map"]["Tell Halaf|part_of|Kingdom of the Franks"] == "33333333-3333-3333-3333-333333333333"
    mock_rel_ids.assert_called_once_with(
        "22222222-2222-2222-2222-222222222222", EXISTING_ID, "part_of")
    mock_rel_labels.assert_not_called()


def test_chronicle_refs_carry_name_and_qid():
    now = datetime.now(timezone.utc).isoformat()
    state = _state(
        title="T",
        parsed_events=[ParsedEvent(label="E", description="The Franks met at Tell Halaf; Dendra too.",
                                   mentioned_entities=["Kingdom of the Franks", "Tell Halaf", "Dendra"])],
        enriched_entities=[_existing("Kingdom of the Franks"), _created("Tell Halaf", qid="Q2142541"),
                           _created("Dendra", qid="Q999")],
        committed=[CommittedChange(change_type="entity", committed_at=now, batch_id="b", record={
            "name": "Tell Halaf", "entity_type": "city", "wikidata_id": "Q2142541"})],
        entity_id_map={"Kingdom of the Franks": EXISTING_ID},
    )
    chronicle = chronicle_builder(state)["chronicle"]
    refs = {r.name: r for r in chronicle.entries[0].secondary_entities}
    assert refs["Kingdom of the Franks"].entity_id == EXISTING_ID
    assert refs["Tell Halaf"].entity_id == "Tell Halaf"  # unresolved → label fallback…
    assert refs["Tell Halaf"].wikidata_id == "Q2142541"  # …but the import QID rides along
    assert refs["Dendra"].wikidata_id is None  # held for review: no unvetted QID


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_wikidata_id")
def test_resolve_ids_rejects_qid_row_with_incompatible_name(mock_qid, mock_name):
    # The pipeline gave "World War I" World War II's QID: do not map WWI's
    # chronicle refs onto the WWII row; fall back to the exact-name row.
    mock_qid.return_value = [{"entity_id": "ww2", "name": "World War II"}]
    mock_name.return_value = [{"entity_id": "ww1", "name": "World War I", "entity_type": "event_war"}]
    now = datetime.now(timezone.utc).isoformat()
    state = _state(committed=[CommittedChange(change_type="entity", committed_at=now, batch_id="b", record={
        "name": "World War I", "entity_type": "event_war", "wikidata_id": "Q362"})])
    assert resolve_entity_ids(state)["entity_id_map"] == {"World War I": "ww1"}


def test_names_compatible_mirrors_php_guard():
    from pipeline.agent.tools.disambiguation import names_compatible

    assert names_compatible("Eighteenth Dynasty of Egypt", "Eighteenth Dynasty")
    assert names_compatible("Philip II of France", "Philip II")
    assert names_compatible("Cordoba", "Córdoba")
    assert not names_compatible("World War I", "World War II")
    assert not names_compatible("Malik-Shah", "Malik-Shah II")
    assert not names_compatible("Qi", "Qing dynasty")
    assert not names_compatible("Julian", "Queen Juliana")
    assert not names_compatible("Late Helladic I", "Late Helladic IIIB")
