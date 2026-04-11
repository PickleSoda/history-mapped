"""Fetch and parse OHM admin_level=2 borders via Overpass."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.openhistoricalmap.org/api/interpreter"

GLOBAL_QUERY = """
[out:json][timeout:1800];
relation["boundary"="administrative"]["admin_level"="2"];
out geom;
"""


def load_query_text(query_file: str | Path | None = None) -> str:
    """Load an Overpass query from disk or fall back to the global query."""
    if query_file is None:
        return GLOBAL_QUERY

    return Path(query_file).read_text(encoding="utf-8")


def fetch_raw(query: str = GLOBAL_QUERY) -> dict[str, Any]:
    """Execute an Overpass query and return parsed JSON."""
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=1800,
        headers={"User-Agent": "WikiGlobe-Pipeline/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _build_relation_index(elements: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(element["id"]): element
        for element in elements
        if element.get("type") == "relation" and "id" in element
    }


def parse_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split OHM relations into polity records with stage geometry entries."""
    relation_by_id = _build_relation_index(elements)

    chronology_ids: set[int] = set()
    chronology_member_ids: set[int] = set()

    for relation in relation_by_id.values():
        tags = relation.get("tags", {})
        if tags.get("type") == "chronology":
            relation_id = int(relation["id"])
            chronology_ids.add(relation_id)
            for member in relation.get("members", []):
                if member.get("type") == "relation" and "ref" in member:
                    chronology_member_ids.add(int(member["ref"]))

    polities: list[dict[str, Any]] = []

    for chronology_id in chronology_ids:
        chronology = relation_by_id[chronology_id]
        stages: list[dict[str, Any]] = []

        for member in chronology.get("members", []):
            if member.get("type") != "relation" or "ref" not in member:
                continue
            stage = relation_by_id.get(int(member["ref"]))
            if stage is None:
                continue

            stages.append(
                {
                    "relation_id": int(stage["id"]),
                    "tags": stage.get("tags", {}),
                    "geometry": assemble_geometry(stage.get("members", [])),
                }
            )

        polities.append(
            {
                "relation_id": chronology_id,
                "tags": chronology.get("tags", {}),
                "stages": stages,
            }
        )

    for relation in relation_by_id.values():
        relation_id = int(relation["id"])
        if relation_id in chronology_ids or relation_id in chronology_member_ids:
            continue

        tags = relation.get("tags", {})
        if tags.get("boundary") != "administrative" or tags.get("admin_level") != "2":
            continue

        geometry = assemble_geometry(relation.get("members", []))
        polities.append(
            {
                "relation_id": relation_id,
                "tags": tags,
                "stages": [
                    {
                        "relation_id": relation_id,
                        "tags": tags,
                        "geometry": geometry,
                    }
                ],
            }
        )

    return polities


def _detail_score(coords: list[list[float]]) -> int:
    return len(coords)


def _ring_area(coords: list[list[float]]) -> float:
    area = 0.0

    for index in range(len(coords) - 1):
        x1, y1 = coords[index]
        x2, y2 = coords[index + 1]
        area += (x1 * y2) - (x2 * y1)

    return abs(area) / 2.0


def _ring_bbox(coords: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]

    return min(xs), min(ys), max(xs), max(ys)


def _bbox_overlap_ratio(
    first_bbox: tuple[float, float, float, float],
    second_bbox: tuple[float, float, float, float],
) -> float:
    first_min_x, first_min_y, first_max_x, first_max_y = first_bbox
    second_min_x, second_min_y, second_max_x, second_max_y = second_bbox

    overlap_width = min(first_max_x, second_max_x) - max(first_min_x, second_min_x)
    overlap_height = min(first_max_y, second_max_y) - max(first_min_y, second_min_y)
    if overlap_width <= 0 or overlap_height <= 0:
        return 0.0

    overlap_area = overlap_width * overlap_height
    first_area = max((first_max_x - first_min_x) * (first_max_y - first_min_y), 0.0)
    second_area = max((second_max_x - second_min_x) * (second_max_y - second_min_y), 0.0)
    min_area = min(first_area, second_area)

    if min_area <= 0:
        return 0.0

    return overlap_area / min_area


def _ring_centroid(coords: list[list[float]]) -> tuple[float, float]:
    unique_points = coords[:-1] if len(coords) > 1 and coords[0] == coords[-1] else coords
    if not unique_points:
        return 0.0, 0.0

    x_total = sum(point[0] for point in unique_points)
    y_total = sum(point[1] for point in unique_points)
    count = len(unique_points)

    return x_total / count, y_total / count


def _point_in_ring(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False

    for index in range(len(ring) - 1):
        x1, y1 = ring[index]
        x2, y2 = ring[index + 1]

        if ((y1 > y) != (y2 > y)) and (x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12)) + x1):
            inside = not inside

    return inside


def _is_near_duplicate_outline(first_coords: list[list[float]], second_coords: list[list[float]]) -> bool:
    first_area = _ring_area(first_coords)
    second_area = _ring_area(second_coords)
    min_area = min(first_area, second_area)
    max_area = max(first_area, second_area)

    if min_area <= 0 or max_area <= 0:
        return False

    area_ratio = min_area / max_area
    bbox_ratio = _bbox_overlap_ratio(_ring_bbox(first_coords), _ring_bbox(second_coords))
    if area_ratio < 0.9 or bbox_ratio < 0.98:
        return False

    return _point_in_ring(_ring_centroid(first_coords), second_coords) and _point_in_ring(_ring_centroid(second_coords), first_coords)



def _prefer_ring(
    current_coords: list[list[float]],
    candidate_coords: list[list[float]],
) -> list[list[float]]:
    current_score = _detail_score(current_coords)
    candidate_score = _detail_score(candidate_coords)

    if candidate_score > current_score:
        return candidate_coords

    if candidate_score < current_score:
        return current_coords

    if _ring_area(candidate_coords) > _ring_area(current_coords):
        return candidate_coords

    return current_coords


def _filter_duplicate_rings(rings: list[list[list[float]]]) -> list[list[list[float]]]:
    filtered: list[list[list[float]]] = []

    for ring in rings:
        duplicate_index = None

        for index, existing_ring in enumerate(filtered):
            if not _is_near_duplicate_outline(existing_ring, ring):
                continue

            duplicate_index = index
            filtered[index] = _prefer_ring(existing_ring, ring)
            break

        if duplicate_index is None:
            filtered.append(ring)

    return filtered


def assemble_geometry(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Assemble geometry from member way coordinates.

    Uses shapely when available; otherwise falls back to a simple MultiPolygon
    assembly suitable for ingestion tests.
    """
    rings: list[list[list[float]]] = []

    for member in members:
        if member.get("type") != "way":
            continue
        if member.get("role", "outer") != "outer":
            continue

        points = member.get("geometry", [])
        coords = [[float(point["lon"]), float(point["lat"])] for point in points if "lon" in point and "lat" in point]
        if len(coords) < 3:
            continue

        if coords[0] != coords[-1]:
            coords.append(coords[0])

        rings.append(coords)

    if not rings:
        return None

    rings = _filter_duplicate_rings(rings)

    try:
        from shapely.geometry import MultiPolygon, Polygon, mapping

        polygons = [Polygon(ring) for ring in rings if len(ring) >= 4]
        polygons = [polygon for polygon in polygons if polygon.is_valid and not polygon.is_empty]
        if not polygons:
            return None

        if len(polygons) == 1:
            return mapping(polygons[0])

        return mapping(MultiPolygon(polygons))
    except Exception as exc:  # pragma: no cover - fallback for missing shapely/runtime issues
        logger.debug("Shapely fallback in assemble_geometry: %s", exc)
        return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
