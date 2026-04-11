"""Map parsed OHM polity records to WikiGlobe JSONL entities."""

from __future__ import annotations

from typing import Any

from pipeline.ohm_borders.date_parser import parse_end_year, parse_start_year


def _has_valid_stage_range(stage: dict[str, Any]) -> bool:
    stage_tags = stage.get("tags", {})
    start_year = parse_start_year(stage_tags.get("start_date"))
    end_year = parse_end_year(stage_tags.get("end_date"))

    if start_year is not None and end_year is not None and start_year > end_year:
        return False

    return True


def _pick_name(tags: dict[str, Any], wd_meta: dict[str, Any] | None) -> str:
    if wd_meta and wd_meta.get("name_en"):
        return wd_meta["name_en"]

    return tags.get("name:en") or tags.get("name") or "Unknown"


def _resolve_temporal_bounds(
    tags: dict[str, Any],
    stages: list[dict[str, Any]],
    wd_meta: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    valid_stages = [stage for stage in stages if _has_valid_stage_range(stage)]

    tag_start = tags.get("start_date")
    tag_end = tags.get("end_date")

    stage_starts = [stage.get("tags", {}).get("start_date") for stage in valid_stages if stage.get("tags", {}).get("start_date")]
    stage_ends = [stage.get("tags", {}).get("end_date") for stage in valid_stages if stage.get("tags", {}).get("end_date")]

    if tag_start is not None:
        temporal_start = tag_start
    elif stage_starts:
        temporal_start = min(stage_starts, key=lambda value: parse_start_year(value) if parse_start_year(value) is not None else float("inf"))
    else:
        temporal_start = (wd_meta or {}).get("temporal_start")

    if tag_end is not None:
        temporal_end = tag_end
    elif stage_ends:
        temporal_end = max(stage_ends, key=lambda value: parse_end_year(value) if parse_end_year(value) is not None else float("-inf"))
    else:
        temporal_end = (wd_meta or {}).get("temporal_end")

    start_year = parse_start_year(temporal_start)
    end_year = parse_end_year(temporal_end)

    if start_year is not None and end_year is not None and start_year > end_year:
        temporal_start = tag_start or (stage_starts[0] if stage_starts else temporal_start)
        temporal_end = tag_end or (stage_ends[-1] if stage_ends else temporal_end)

    return temporal_start, temporal_end


def map_polity_to_jsonl(polity: dict[str, Any], wikidata_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build one JSONL record from a parsed OHM polity object."""
    tags = polity.get("tags", {})
    stages = polity.get("stages", [])
    qid = tags.get("wikidata")
    wd_meta = wikidata_index.get(qid) if qid else None

    name = _pick_name(tags, wd_meta)
    aliases = (wd_meta or {}).get("aliases_en", [])

    temporal_start, temporal_end = _resolve_temporal_bounds(tags, stages, wd_meta)

    geometry_periods: list[dict[str, Any]] = []

    for stage in stages:
        if not _has_valid_stage_range(stage):
            continue

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
