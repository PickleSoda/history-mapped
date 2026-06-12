"""Tests for the eval harness's pure metric/heuristic functions."""
from __future__ import annotations

from pipeline.agent.eval.metrics import (
    summarize_manifest,
    flag_entities,
    flag_relationships,
    overlap_consistency,
)


def test_summarize_manifest_flags_reducer_blowup():
    healthy = {"run_id": "r", "audit_log": [{}] * 16, "errors": [], "committed_count": 11}
    assert summarize_manifest(healthy, 4096)["reducer_sane"] is True

    blown = {"run_id": "r", "audit_log": [{}] * 65534, "errors": [], "committed_count": 548}
    summary = summarize_manifest(blown, 11_000_000)
    assert summary["reducer_sane"] is False
    assert summary["audit_log_len"] == 65534


def test_flag_relationships_detects_event_range_violation_and_dupes():
    rels = [
        # defeated_at should target an EVENT, not a person -> violation
        {"source_name": "Alexander", "relationship_type": "defeated_at",
         "target_name": "Darius III", "target_entity_type": "person"},
        # duplicate of a valid event-targeted relation
        {"source_name": "Alexander", "relationship_type": "victorious_at",
         "target_name": "Battle of Issus", "target_entity_type": "event_battle"},
        {"source_name": "Alexander", "relationship_type": "victorious_at",
         "target_name": "Battle of Issus", "target_entity_type": "event_battle"},
    ]
    flags = flag_relationships(rels)
    assert flags["total"] == 3
    assert any(v["target"] == "Darius III" for v in flags["event_range_violations"])
    # victorious_at -> battle is NOT a violation
    assert all(v["target"] != "Battle of Issus" for v in flags["event_range_violations"])
    assert any(d["target"] == "Battle of Issus" and d["count"] == 2 for d in flags["duplicates"])


def test_overlap_consistency_detects_duplicate_identity():
    consistent = [
        {"name": "Alexander the Great", "wikidata_id": "Q8409"},
        {"name": "Darius III", "wikidata_id": "Q179339"},
    ]
    assert overlap_consistency(consistent)["consistent"] is True

    duplicated = [
        {"name": "Alexander the Great", "wikidata_id": "Q8409"},
        {"name": "alexander the great", "wikidata_id": "Q8409"},
    ]
    result = overlap_consistency(duplicated)
    assert result["consistent"] is False
    assert result["duplicate_names"][0]["count"] == 2
    assert result["duplicate_wikidata_ids"][0]["count"] == 2


def test_flag_entities_soft_short_name_and_geometry_counts():
    entities = [
        {"name": "Ty", "entity_type": "city", "wikidata_id": None,
         "has_geometry": False, "temporal_start": None, "verification_status": "pipeline_draft"},
        {"name": "Alexandria", "entity_type": "city", "wikidata_id": "Q87",
         "has_geometry": True, "temporal_start": "-0331", "verification_status": "pipeline_draft"},
    ]
    flags = flag_entities(entities)
    assert flags["total"] == 2
    assert "Ty" in flags["short_name_review"]
    assert flags["with_geometry"] == 1
    assert flags["with_wikidata"] == 1
    assert flags["missing_temporal_count"] == 1
