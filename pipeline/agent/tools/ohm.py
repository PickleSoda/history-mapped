from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.ohm_collections.xml_lookup import (
    find_objects_by_name,
    find_objects_by_wikidata_id,
)
from pipeline.ohm_collections.point_resolver import resolve_best_point


def search_ohm_by_name(name: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by name.

    Returns a list of matching OHM objects with their metadata.
    """
    return find_objects_by_name(index_path, name)


def search_ohm_by_wikidata_id(wikidata_id: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by Wikidata QID.

    Returns a list of matching OHM objects.
    """
    return find_objects_by_wikidata_id(index_path, wikidata_id)


def resolve_ohm_geometry(index_path: str | Path, object_type: str, object_id: int) -> dict[str, Any] | None:
    """Resolve the best point geometry for an OHM object.

    Returns a GeoJSON-like dict with the geometry, or None if not found.
    """
    return resolve_best_point(index_path, object_type=object_type, object_id=object_id)
