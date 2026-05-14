"""Extract normalized relation candidates from parsed OHM polity shards."""

from __future__ import annotations

from typing import Any

_TOP_LEVEL_TAG_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("predecessor", "preceded_by"),
    ("preceded_by", "preceded_by"),
    ("successor", "succeeded_by"),
    ("succeeded_by", "succeeded_by"),
)

_STAGE_TAG_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("predecessor", "preceded_by"),
    ("preceded_by", "preceded_by"),
    ("successor", "succeeded_by"),
    ("succeeded_by", "succeeded_by"),
    ("start_event", "resulted_from"),
    ("end_event", "caused"),
)


def extract_relation_candidates(polity: dict[str, Any]) -> list[dict[str, Any]]:
    tags = polity.get("tags", {}) or {}
    source_wikidata_id = _normalize_optional_string(tags.get("wikidata"))
    if source_wikidata_id is None:
        return []

    base = {
        "source_ohm_relation_id": str(polity.get("relation_id")),
        "source_wikidata_id": source_wikidata_id,
        "source_name": _normalize_optional_string(tags.get("name")),
    }

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None, str | None, str | None, str | None]] = set()

    candidates.extend(_extract_from_tags(base, tags, _TOP_LEVEL_TAG_MAPPINGS, None, None, seen))

    for stage in polity.get("stages", []) or []:
        stage_tags = stage.get("tags", {}) or {}
        temporal_start = _first_non_empty(stage_tags.get("start_date"), stage_tags.get("start"))
        temporal_end = _first_non_empty(stage_tags.get("end_date"), stage_tags.get("end"))
        candidates.extend(_extract_from_tags(base, stage_tags, _STAGE_TAG_MAPPINGS, temporal_start, temporal_end, seen))

    return sorted(
        candidates,
        key=lambda candidate: (
            str(candidate["source_ohm_relation_id"]),
            str(candidate["relationship_type"]),
            str(candidate["source_tag_key"]),
            str(candidate.get("target_wikidata_id") or ""),
            str(candidate.get("target_label") or ""),
        ),
    )



def _extract_from_tags(
    base: dict[str, Any],
    tags: dict[str, Any],
    mappings: tuple[tuple[str, str], ...],
    temporal_start: str | None,
    temporal_end: str | None,
    seen: set[tuple[str, str, str | None, str | None, str | None, str | None]],
) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []

    for source_tag_key, relationship_type in mappings:
        target_label = _normalize_optional_string(tags.get(source_tag_key))
        target_wikidata_id = _normalize_optional_string(tags.get(f"{source_tag_key}:wikidata"))

        if target_label is None and target_wikidata_id is None:
            continue

        dedupe_key = (relationship_type, source_tag_key, target_wikidata_id, target_label, temporal_start, temporal_end)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        extracted.append(
            {
                **base,
                "relationship_type": relationship_type,
                "target_wikidata_id": target_wikidata_id,
                "target_label": target_label,
                "source_tag_key": source_tag_key,
                "temporal_start": temporal_start,
                "temporal_end": temporal_end,
            }
        )

    return extracted



def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    return trimmed or None



def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        normalized = _normalize_optional_string(value)
        if normalized is not None:
            return normalized

    return None
