"""Pure metric + quality-heuristic functions for the eval harness.

Everything here is side-effect free and operates on plain dicts/lists so it can
be unit-tested without a database or the pipeline. The harness feeds it manifest
JSON and rows probed from the database.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

# entity_type values that denote an EVENT (the valid domain/range for
# event-anchored relationship types). Mirrors the EVENT group of the
# entity_type PG enum.
EVENT_ENTITY_TYPES: frozenset[str] = frozenset({
    "event_war",
    "event_battle",
    "event_treaty",
    "event_rebellion",
    "event_natural_disaster",
    "event_tech_adoption",
    "event_legal_reform",
    "migration",
    "epidemic_disease",
})

# Relationship types whose target should be an EVENT, not a person/polity.
# A "defeated_at Darius III" (person) is a domain/range violation — it should
# target a battle/war.
EVENT_TARGET_RELATIONSHIPS: frozenset[str] = frozenset({
    "participated_in",
    "fought_at",
    "defeated_at",
    "victorious_at",
    "stationed_at",
})

# Sane upper bound for audit-log length: the graph has ~15 nodes, each emitting
# a small, bounded number of audit events. Anything near this means the
# reducer-duplication bug is back.
AUDIT_LOG_SANE_MAX = 100


def summarize_manifest(manifest: dict[str, Any], manifest_size_bytes: int) -> dict[str, Any]:
    """Reduce a run manifest to the headline health metrics."""
    audit_len = len(manifest.get("audit_log", []))
    errors = manifest.get("errors", []) or []
    return {
        "run_id": manifest.get("run_id"),
        "parsed_events": manifest.get("parsed_events_count", 0),
        "candidate_entities": manifest.get("candidate_entities_count", 0),
        "candidate_relations": manifest.get("candidate_relations_count", 0),
        "enriched_entities": manifest.get("enriched_entities_count", 0),
        "validation_results": manifest.get("validation_results_count", 0),
        "committed_count": manifest.get("committed_count", 0),
        "errors_count": manifest.get("errors_count", len(errors)),
        "audit_log_len": audit_len,
        "manifest_size_bytes": manifest_size_bytes,
        "reducer_sane": audit_len < AUDIT_LOG_SANE_MAX,
        "errors": [
            {
                "node": e.get("node"),
                "type": e.get("error_type"),
                "message": (e.get("message") or "")[:300],
            }
            for e in errors
        ],
    }


def flag_entities(entities: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic quality flags over the entity rows persisted in the DB.

    ``entities`` rows expose: name, entity_type, wikidata_id, has_geometry,
    temporal_start, verification_status.
    """
    short_names = sorted({
        e["name"] for e in entities
        if isinstance(e.get("name"), str) and len(e["name"].strip()) <= 2
    })
    missing_wikidata = [e["name"] for e in entities if not e.get("wikidata_id")]
    missing_temporal = [e["name"] for e in entities if not e.get("temporal_start")]
    no_geometry = [e["name"] for e in entities if not e.get("has_geometry")]

    return {
        "total": len(entities),
        "by_type": dict(Counter(e.get("entity_type") for e in entities)),
        "by_status": dict(Counter(e.get("verification_status") for e in entities)),
        "with_wikidata": sum(1 for e in entities if e.get("wikidata_id")),
        "with_geometry": sum(1 for e in entities if e.get("has_geometry")),
        # Soft review flags (not necessarily errors — e.g. "Ur" is a real city).
        "short_name_review": short_names,
        "missing_wikidata_count": len(missing_wikidata),
        "missing_temporal_count": len(missing_temporal),
        "no_geometry_count": len(no_geometry),
    }


def flag_relationships(relationships: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic quality flags over the relationship rows persisted in the DB.

    ``relationships`` rows expose: source_name, target_name, relationship_type,
    target_entity_type.
    """
    keys = [
        (r.get("source_name"), r.get("relationship_type"), r.get("target_name"))
        for r in relationships
    ]
    dup_counter = Counter(keys)
    duplicates = [
        {"source": k[0], "type": k[1], "target": k[2], "count": c}
        for k, c in dup_counter.items() if c > 1
    ]

    self_loops = [
        {"source": r.get("source_name"), "type": r.get("relationship_type")}
        for r in relationships
        if r.get("source_name") and r.get("source_name") == r.get("target_name")
    ]

    range_violations = [
        {
            "source": r.get("source_name"),
            "type": r.get("relationship_type"),
            "target": r.get("target_name"),
            "target_type": r.get("target_entity_type"),
        }
        for r in relationships
        if r.get("relationship_type") in EVENT_TARGET_RELATIONSHIPS
        and r.get("target_entity_type") not in EVENT_ENTITY_TYPES
    ]

    return {
        "total": len(relationships),
        "by_type": dict(Counter(r.get("relationship_type") for r in relationships)),
        "duplicates": duplicates,
        "self_loops": self_loops,
        "event_range_violations": range_violations,
    }


def overlap_consistency(entities: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect entities duplicated across overlapping transcripts.

    The expectation: an entity mentioned in two transcripts (e.g. "Alexander
    the Great") should be ONE row, deduped on import — not two. Reports name and
    wikidata_id collisions where the same identity produced multiple rows.
    """
    name_counter = Counter(
        e["name"].strip().lower()
        for e in entities
        if isinstance(e.get("name"), str)
    )
    qid_counter = Counter(
        e["wikidata_id"] for e in entities if e.get("wikidata_id")
    )

    dup_names = [
        {"name": name, "count": c} for name, c in name_counter.items() if c > 1
    ]
    dup_qids = [
        {"wikidata_id": qid, "count": c} for qid, c in qid_counter.items() if c > 1
    ]
    return {
        "duplicate_names": sorted(dup_names, key=lambda d: -d["count"]),
        "duplicate_wikidata_ids": sorted(dup_qids, key=lambda d: -d["count"]),
        "consistent": not dup_names and not dup_qids,
    }
