"""Map Overpass `out tags;` elements to OHM-link records (the importer's JSONL contract)."""

from __future__ import annotations

import re
from typing import Any

OSM_TYPES = ("node", "way", "relation")

TAG_KEYS = (
    "boundary",
    "admin_level",
    "type",
    "place",
    "name",
    "name:en",
    "official_name",
    "wikidata",
    "wikipedia",
    "start_date",
    "end_date",
)

_QID_PATTERN = re.compile(r"Q[0-9]+")


def _wikidata_id(value: Any) -> str | None:
    if isinstance(value, str) and _QID_PATTERN.fullmatch(value):
        return value
    return None


def _admin_level(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def element_to_record(element: dict[str, Any]) -> dict[str, Any] | None:
    """Return the OHM-link record for one Overpass element, or None if it has no tags."""
    tags = element.get("tags")
    if not tags:
        return None

    osm_type = element.get("type")
    if osm_type not in OSM_TYPES or "id" not in element:
        return None

    return {
        "osm_type": osm_type,
        "osm_id": int(element["id"]),
        "wikidata_id": _wikidata_id(tags.get("wikidata")),
        "name": tags.get("name"),
        "name_en": tags.get("name:en"),
        "admin_level": _admin_level(tags.get("admin_level")),
        "place": tags.get("place"),
        "start_date": tags.get("start_date"),
        "end_date": tags.get("end_date"),
        "tags": {key: tags[key] for key in TAG_KEYS if key in tags},
    }
