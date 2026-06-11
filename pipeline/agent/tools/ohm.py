from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.agent.logging import get_logger
from pipeline.ohm_collections.xml_lookup import (
    find_objects_by_name,
    find_objects_by_wikidata_id,
)
from pipeline.ohm_collections.point_resolver import resolve_best_point

logger = get_logger(__name__)


def search_ohm_by_name(name: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by name."""
    logger.info("OHM name lookup: '%s'", name)
    results = find_objects_by_name(index_path, name)
    logger.info("OHM name lookup: %d results for '%s'", len(results), name)
    return results


def search_ohm_by_wikidata_id(wikidata_id: str, index_path: str | Path) -> list[dict[str, Any]]:
    """Search OHM SQLite index by Wikidata QID."""
    logger.info("OHM QID lookup: '%s'", wikidata_id)
    results = find_objects_by_wikidata_id(index_path, wikidata_id)
    logger.info("OHM QID lookup: %d results for '%s'", len(results), wikidata_id)
    return results


def resolve_ohm_geometry(index_path: str | Path, object_type: str, object_id: int) -> dict[str, Any] | None:
    """Resolve the best point geometry for an OHM object."""
    logger.info("OHM geom resolve: type=%s id=%s", object_type, object_id)
    geo = resolve_best_point(index_path, object_type=object_type, object_id=object_id)
    logger.info("OHM geom resolve: %s", "found" if geo else "not found")
    return geo
