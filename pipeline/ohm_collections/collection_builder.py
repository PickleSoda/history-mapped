from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.ohm_collections.artifacts import ensure_collection_artifact_dirs
from pipeline.config import TYPE_TO_GROUP


_COLLECTION_TYPE_MAP = {
    "battle": "event_battle",
    "city": "city",
    "culture": "archaeological_culture",
    "currency": "currency_monetary_system",
    "dynasty": "dynasty",
    "event": "event_war",
    "geographic_region": "political_entity",
    "historical_period": "political_entity",
    "place": "infrastructure_monument",
    "political_entity": "political_entity",
    "region": "political_entity",
    "religion": "religious_movement",
    "script": "language",
    "state": "political_entity",
    "war": "event_war",
    "writing_system": "language",
}

_RAW_TAG_RELATIONSHIP_MAP: tuple[tuple[str, str, str], ...] = (
    ("predecessor", "preceded_by", "P155"),
    ("preceded_by", "preceded_by", "P155"),
    ("successor", "succeeded_by", "P156"),
    ("succeeded_by", "succeeded_by", "P156"),
    ("start_event", "resulted_from", "P828"),
    ("end_event", "caused", "P1542"),
)


def build_collection_artifacts(
    included_candidates: list[dict[str, Any]],
    *,
    output_root: str | Path,
    excluded_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_excluded_candidates = excluded_candidates or []
    paths = ensure_collection_artifact_dirs(output_root)

    border_records: list[dict[str, Any]] = []
    entity_records: list[dict[str, Any]] = []
    included_report_records: list[dict[str, Any]] = []
    excluded_report_records: list[dict[str, Any]] = []
    geometry_sources = {
        "ohm_point": 0,
        "ohm_representative_point": 0,
        "pipeline_geojson": 0,
        "none": 0,
    }

    for candidate in included_candidates:
        geometry_source, geojson = _select_geometry(candidate)
        geometry_sources[geometry_source] += 1

        included_report_records.append(_included_report_record(candidate, geometry_source))

        border_record = candidate.get("border_record")
        if isinstance(border_record, dict):
            border_records.append(border_record)
            continue

        entity_records.append(_build_entity_record(candidate, geometry_source, geojson))

    for candidate in resolved_excluded_candidates:
        decision = candidate.get("decision") or {}
        excluded_report_records.append(
            {
                "name": candidate.get("name"),
                "entity_types": list(candidate.get("entity_types") or []),
                "reasons": list(decision.get("reasons") or []),
                "ambiguity": list(decision.get("ambiguity") or []),
            }
        )

    _write_jsonl(paths["borders_file"], border_records)
    _write_jsonl(paths["entities_file"], entity_records)
    _write_jsonl(paths["included_report"], included_report_records)
    _write_jsonl(paths["excluded_report"], excluded_report_records)

    manifest = {
        "counts": {
            "included": len(included_candidates),
            "excluded": len(resolved_excluded_candidates),
            "border_records": len(border_records),
            "entity_records": len(entity_records),
        },
        "geometry_sources": geometry_sources,
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _entity_type_for_candidate(candidate: dict[str, Any]) -> str | None:
    entity_types = candidate.get("entity_types") or []
    if isinstance(entity_types, list) and entity_types:
        return str(entity_types[0])
    entity_type = candidate.get("entity_type")
    return str(entity_type) if entity_type is not None else None


def _included_report_record(candidate: dict[str, Any], geometry_source: str) -> dict[str, Any]:
    return {
        "name": candidate.get("name"),
        "wikidata_id": candidate.get("wikidata_id"),
        "entity_types": list(candidate.get("entity_types") or []),
        "reasons": list((candidate.get("decision") or {}).get("reasons") or []),
        "ambiguity": list((candidate.get("decision") or {}).get("ambiguity") or []),
        "geometry_source": geometry_source,
        "raw_tags": dict(candidate.get("raw_tags") or {}),
        "_ohm_object_type": candidate.get("_ohm_object_type"),
        "_ohm_object_id": candidate.get("_ohm_object_id"),
    }


def _build_entity_record(
    candidate: dict[str, Any],
    geometry_source: str,
    geojson: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_tags = candidate.get("raw_tags") or {}
    temporal_start = _normalize_temporal(raw_tags.get("start_date") or raw_tags.get("start"))
    temporal_end = _normalize_temporal(raw_tags.get("end_date") or raw_tags.get("end"))
    location_name = _normalize_optional_string(raw_tags.get("name:en")) or _normalize_optional_string(candidate.get("name"))

    requested_type = _entity_type_for_candidate(candidate)
    canonical_type, entity_group = _canonical_entity_type_and_group(requested_type)
    attributes: dict[str, Any] = {
        "ohm_object_type": candidate.get("_ohm_object_type"),
        "ohm_object_id": candidate.get("_ohm_object_id"),
    }
    if requested_type is not None and requested_type != canonical_type:
        attributes["collection_entity_type"] = requested_type

    record: dict[str, Any] = {
        "name": candidate.get("name"),
        "entity_type": canonical_type,
        "entity_group": entity_group,
        "wikidata_id": candidate.get("wikidata_id"),
        "alternative_names": list(candidate.get("alternative_names") or []),
        "summary": candidate.get("summary"),
        "temporal_start": temporal_start,
        "temporal_end": temporal_end,
        "location_name": location_name,
        "geojson": geojson,
        "impact_score": _compute_impact_score(candidate, geometry_source),
        "verification_status": "pipeline_draft",
        "confidence": "medium",
        "attributes": attributes,
        "_geometry_source": geometry_source,
    }

    relationship_hints = _relationship_hints_from_raw_tags(raw_tags)
    if relationship_hints:
        record["_relationship_hints"] = relationship_hints

    wikidata_id = candidate.get("wikidata_id")
    if isinstance(wikidata_id, str) and wikidata_id:
        record["source_citations"] = [{"source": "wikidata", "wikidata_id": wikidata_id}]

    return record


def _canonical_entity_type_and_group(requested_type: str | None) -> tuple[str, str]:
    if requested_type is None:
        return "political_entity", "POLITY"

    canonical_type = _COLLECTION_TYPE_MAP.get(requested_type, requested_type)
    entity_group = TYPE_TO_GROUP.get(canonical_type)
    if entity_group is None:
        canonical_type = "political_entity"
        entity_group = "POLITY"
    return canonical_type, entity_group


def _select_geometry(candidate: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    point_resolution = candidate.get("point_resolution") or {}
    if point_resolution.get("status") == "resolved" and isinstance(point_resolution.get("point"), dict):
        geometry_source = str(point_resolution.get("geometry_source") or "ohm_point")
        return geometry_source, point_resolution["point"]

    fallback_geojson = candidate.get("fallback_geojson")
    if isinstance(fallback_geojson, dict):
        return "pipeline_geojson", fallback_geojson

    return "none", None


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    return trimmed or None


def _normalize_temporal(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None

    return normalized


def _compute_impact_score(candidate: dict[str, Any], geometry_source: str) -> int:
    base_by_type = {
        "political_entity": 80,
        "event_war": 76,
        "event_battle": 74,
        "dynasty": 72,
        "city": 64,
        "infrastructure_monument": 58,
    }

    canonical_type, _ = _canonical_entity_type_and_group(_entity_type_for_candidate(candidate))
    score = base_by_type.get(canonical_type, 52)

    if _normalize_optional_string(candidate.get("wikidata_id")) is not None:
        score += 8

    if _normalize_optional_string(candidate.get("summary")) is not None:
        score += 4

    raw_tags = candidate.get("raw_tags") or {}
    if _normalize_temporal(raw_tags.get("start_date") or raw_tags.get("start")) is not None:
        score += 4
    if _normalize_temporal(raw_tags.get("end_date") or raw_tags.get("end")) is not None:
        score += 2

    if geometry_source in {"ohm_point", "ohm_representative_point", "pipeline_geojson"}:
        score += 4

    if candidate.get("_ohm_object_type") == "relation":
        score += 3

    return max(1, min(100, score))


def _relationship_hints_from_raw_tags(raw_tags: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw_tags, dict):
        return []

    temporal_start = _normalize_temporal(raw_tags.get("start_date") or raw_tags.get("start"))
    temporal_end = _normalize_temporal(raw_tags.get("end_date") or raw_tags.get("end"))

    hints: list[dict[str, Any]] = []
    for source_key, relationship_type, property_id in _RAW_TAG_RELATIONSHIP_MAP:
        target_wikidata_id = _normalize_optional_string(raw_tags.get(f"{source_key}:wikidata"))
        target_label = _normalize_optional_string(raw_tags.get(source_key))

        if target_wikidata_id is None:
            continue

        hints.append(
            {
                "relationship_type": relationship_type,
                "target_wikidata_id": target_wikidata_id,
                "target_label": target_label,
                "temporal_start": temporal_start,
                "temporal_end": temporal_end,
                "confidence": "medium",
                "source": f"wikidata:{property_id}",
            }
        )

    return hints