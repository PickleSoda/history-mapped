"""Map parsed OHM polity records to WikiGlobe JSONL entities."""

from __future__ import annotations

from typing import Any

from pipeline.ohm_borders.date_parser import parse_end_year, parse_start_year


def _pick_name(tags: dict[str, Any], wd_meta: dict[str, Any] | None) -> str:
    if wd_meta and wd_meta.get("name_en"):
        return wd_meta["name_en"]

    return tags.get("name:en") or tags.get("name") or "Unknown"


def map_polity_to_jsonl(polity: dict[str, Any], wikidata_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build one JSONL record from a parsed OHM polity object."""
    tags = polity.get("tags", {})
    qid = tags.get("wikidata")
    wd_meta = wikidata_index.get(qid) if qid else None

    name = _pick_name(tags, wd_meta)
    aliases = (wd_meta or {}).get("aliases_en", [])

    temporal_start = (wd_meta or {}).get("temporal_start") or tags.get("start_date")
    temporal_end = (wd_meta or {}).get("temporal_end") or tags.get("end_date")

    geometry_periods: list[dict[str, Any]] = []

    for stage in polity.get("stages", []):
        stage_tags = stage.get("tags", {})
        raw_start = stage_tags.get("start_date") or tags.get("start_date")
        raw_end = stage_tags.get("end_date") or tags.get("end_date")
        start_year = parse_start_year(raw_start)
        end_year = parse_end_year(raw_end)

        label = name
        if start_year is not None and end_year is not None:
            label = f"{name} ({start_year}-{end_year})"

        geometry_periods.append({
            "ohm_relation_id": str(stage.get("relation_id")),
            "external_type": "relation",
            "start_year": start_year,
            "end_year": end_year,
            "start_date": raw_start,
            "end_date": raw_end,
            "geojson": stage.get("geometry"),
            "label": label,
            "external_tags": stage_tags,
        })

    return {
        "name": name,
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": qid,
        "alternative_names": aliases,
        "summary": (wd_meta or {}).get("description"),
        "temporal_start": temporal_start,
        "temporal_end": temporal_end,
        "verification_status": "ohm_draft",
        "confidence": "medium",
        "location_method": "ohm_nominatim",
        "location_confidence": "high",
        "_ohm_relation_id": str(polity.get("relation_id")),
        "_geometry_periods": geometry_periods,
    }
