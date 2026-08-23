import json
from pathlib import Path

import pytest

from pipeline.agent.handoff import HandoffDocument, hydrate_state, load_handoff


def _sample_doc() -> dict:
    return {
        "run_id": "campaign_test",
        "source_transcript": "output/transcripts/campaign/sample.txt",
        "title": "Test Chronicle",
        "summaries_precomputed": True,
        "parsed_events": [
            {"label": "Battle of Didgori", "description": "David IV defeats Ilghazi.",
             "start_date": "1121", "end_date": None,
             "mentioned_entities": ["David IV"], "date_uncertain": False}
        ],
        "candidate_entities": [
            {"label": "David IV of Georgia", "entity_type": "person",
             "start_date": "1073", "end_date": "1125", "aliases": ["David IV"]},
            {"label": "Kingdom of Georgia", "entity_type": "political_entity"},
            {"label": "Battle of Didgori", "entity_type": "event_battle",
             "start_date": "1121", "end_date": "1121"},
        ],
        "candidate_relations": [
            {"source_label": "David IV of Georgia", "target_label": "Battle of Didgori",
             "relationship_type": "participated_in", "start_date": "1121", "end_date": "1121",
             "description": "David IV commanded the Georgian forces at Didgori."},
            {"source_label": "David IV of Georgia", "target_label": "Kingdom of Georgia",
             "relationship_type": "rules", "start_date": "1089", "end_date": "1125",
             "description": "Ruled the Kingdom of Georgia from 1089 to 1125."}
        ],
        "summaries": {
            "David IV of Georgia": {"summary": "He ruled Georgia. He won at Didgori. His reign began the Golden Age.",
                                     "significance": "Broke Seljuk dominance."},
            "Kingdom of Georgia": {"summary": "The kingdom rose in the Caucasus. It flourished under David IV. Its golden age peaked in the twelfth century.",
                                    "significance": "Medieval Caucasian power."},
            "Battle of Didgori": {"summary": "Didgori was fought in 1121 near Tbilisi. The Georgian coalition crushed the Seljuk host. The victory opened the way to Tbilisi's recapture.",
                                   "significance": "Decisive Georgian victory over the Seljuks."},
        },
        "self_audit": {"critic_iterations": 2, "orphan_check_done": True},
    }


def test_load_handoff_parses_and_coerces(tmp_path: Path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(_sample_doc()), encoding="utf-8")
    doc = load_handoff(path)
    assert doc.run_id == "campaign_test"
    assert len(doc.candidate_entities) == 3
    assert doc.summaries["David IV of Georgia"]["significance"].startswith("Broke")


def test_load_handoff_normalizes_synonym_types(tmp_path: Path):
    doc_dict = _sample_doc()
    doc_dict["candidate_entities"][1]["entity_type"] = "kingdom"
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(doc_dict), encoding="utf-8")
    doc = load_handoff(path)
    assert doc.candidate_entities[1].entity_type == "political_entity"


def test_hydrate_state_produces_full_tail_state(tmp_path: Path):
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(_sample_doc()), encoding="utf-8")
    doc = load_handoff(path)
    state = hydrate_state(doc, raw_input="raw transcript text")
    assert state["run_id"] == "campaign_test"
    assert state["title"] == "Test Chronicle"
    assert state["critic_done"] is True
    assert state["summaries_precomputed"] is True
    assert "David IV of Georgia" in state["summaries"]
    for key in ("parsed_events", "candidate_entities", "candidate_relations",
                "enriched_entities", "validation_results", "committed",
                "audit_log", "errors", "entity_id_map", "relation_id_map"):
        assert key in state


def test_hydrate_state_defaults_without_summaries(tmp_path: Path):
    doc_dict = _sample_doc()
    doc_dict["summaries_precomputed"] = False
    doc_dict["summaries"] = {}
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(doc_dict), encoding="utf-8")
    doc = load_handoff(path)
    state = hydrate_state(doc, raw_input="")
    assert state["summaries_precomputed"] is False
    assert state["summaries"] == {}
