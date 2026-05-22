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
        headers={"User-Agent": "history-mapped-Pipeline/1.0"},
    )
    response.raise_for_status()
    return response.json()


def _build_relation_index(elements: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        int(element["id"]): element
        for element in elements
        if element.get("type") == "relation" and "id" in element
    }


def parse_relation_subset(
    elements: list[dict[str, Any]],
    parser: Any = None,
    relation_index: dict[int, dict[str, Any]] | None = None,
    chronology_member_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Parse a relation-only subset safely while preserving parser compatibility.

    This helper is intentionally thin: it sanitizes relation inputs for one shard
    and then delegates to the provided parser (defaulting to parse_elements).
    """
    relation_elements: list[dict[str, Any]] = []

    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") != "relation" or "id" not in element:
            continue

        try:
            relation_id = int(element["id"])
        except (TypeError, ValueError):
            continue

        relation_elements.append({**element, "id": relation_id})

    relation_elements.sort(key=lambda relation: relation["id"])

    parse_fn = parser or parse_elements

    if parse_fn is parse_elements and relation_index is not None:
        return _parse_relation_subset_with_index(
            relation_elements=relation_elements,
            relation_index=relation_index,
            chronology_member_ids=chronology_member_ids,
        )

    return parse_fn(relation_elements)


def _collect_chronology_members(relation_index: dict[int, dict[str, Any]]) -> set[int]:
    members: set[int] = set()

    for relation in relation_index.values():
        tags = relation.get("tags", {})
        if tags.get("type") != "chronology":
            continue

        for member in relation.get("members", []):
            if member.get("type") != "relation" or "ref" not in member:
                continue

            try:
                members.add(int(member["ref"]))
            except (TypeError, ValueError):
                continue

    return members


def _collect_chronology_wikidata_ids(relation_index: dict[int, dict[str, Any]]) -> set[str]:
    wikidata_ids: set[str] = set()

    for relation in relation_index.values():
        tags = relation.get("tags", {})
        if tags.get("type") != "chronology":
            continue

        wikidata_id = tags.get("wikidata")
        if isinstance(wikidata_id, str) and wikidata_id:
            wikidata_ids.add(wikidata_id)

    return wikidata_ids


def _parse_relation_subset_with_index(
    *,
    relation_elements: list[dict[str, Any]],
    relation_index: dict[int, dict[str, Any]],
    chronology_member_ids: set[int] | None,
) -> list[dict[str, Any]]:
    chronology_ids = {
        relation_id
        for relation_id, relation in relation_index.items()
        if relation.get("tags", {}).get("type") == "chronology"
    }
    global_chronology_member_ids = chronology_member_ids or _collect_chronology_members(relation_index)
    chronology_wikidata_ids = _collect_chronology_wikidata_ids(relation_index)

    polities: list[dict[str, Any]] = []

    for relation in relation_elements:
        relation_id = int(relation["id"])
        if relation_id not in chronology_ids:
            continue

        stages: list[dict[str, Any]] = []

        for member in relation.get("members", []):
            if member.get("type") != "relation" or "ref" not in member:
                continue

            try:
                member_relation_id = int(member["ref"])
            except (TypeError, ValueError):
                continue

            stage_relation = relation_index.get(member_relation_id)
            if stage_relation is None:
                continue

            stages.append(
                {
                    "relation_id": member_relation_id,
                    "tags": stage_relation.get("tags", {}),
                    "geometry": assemble_geometry(stage_relation.get("members", [])),
                }
            )

        polities.append(
            {
                "relation_id": relation_id,
                "tags": relation.get("tags", {}),
                "stages": stages,
            }
        )

    for relation in relation_elements:
        relation_id = int(relation["id"])
        if relation_id in chronology_ids or relation_id in global_chronology_member_ids:
            continue

        tags = relation.get("tags", {})
        if tags.get("boundary") != "administrative" or tags.get("admin_level") != "2":
            continue
        wikidata_id = tags.get("wikidata")
        if isinstance(wikidata_id, str) and wikidata_id in chronology_wikidata_ids:
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


def parse_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split OHM relations into polity records with stage geometry entries."""
    relation_by_id = _build_relation_index(elements)

    chronology_ids: set[int] = set()
    chronology_member_ids: set[int] = set()
    chronology_wikidata_ids: set[str] = set()

    for relation in relation_by_id.values():
        tags = relation.get("tags", {})
        if tags.get("type") == "chronology":
            relation_id = int(relation["id"])
            chronology_ids.add(relation_id)
            wikidata_id = tags.get("wikidata")
            if isinstance(wikidata_id, str) and wikidata_id:
                chronology_wikidata_ids.add(wikidata_id)
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
        wikidata_id = tags.get("wikidata")
        if isinstance(wikidata_id, str) and wikidata_id in chronology_wikidata_ids:
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
            # Check exact/near duplicates (area and bbox similarity)
            if _is_near_duplicate_outline(existing_ring, ring):
                duplicate_index = index
                filtered[index] = _prefer_ring(existing_ring, ring)
                break

        if duplicate_index is None:
            filtered.append(ring)

    return filtered


def _normalize_ring_coords(coords: Any) -> list[list[float]]:
    normalized: list[list[float]] = []

    if not isinstance(coords, list):
        return normalized

    for point in coords:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue

        try:
            normalized.append([float(point[0]), float(point[1])])
        except (TypeError, ValueError):
            continue

    if len(normalized) >= 3 and normalized[0] != normalized[-1]:
        normalized.append(normalized[0])

    return normalized


def _largest_outer_ring_from_geometry(geometry: dict[str, Any]) -> list[list[float]] | None:
    geometry_type = geometry.get("type")

    if geometry_type == "Polygon":
        polygons = [geometry.get("coordinates", [])]
    elif geometry_type == "MultiPolygon":
        polygons = geometry.get("coordinates", [])
    else:
        return None

    outer_rings: list[list[list[float]]] = []

    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            continue

        ring = _normalize_ring_coords(polygon[0])
        if len(ring) >= 4:
            outer_rings.append(ring)

    if not outer_rings:
        return None

    return max(outer_rings, key=_ring_area)


def derive_representative_point(geometry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(geometry, dict):
        return None

    geometry_type = geometry.get("type")
    if geometry_type == "Point":
        coords = geometry.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return None

        try:
            return {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]}
        except (TypeError, ValueError):
            return None

    if geometry_type not in {"Polygon", "MultiPolygon"}:
        return None

    try:
        from shapely.geometry import shape

        shaped = shape(geometry)
        if not shaped.is_empty:
            point = shaped.representative_point()
            if not point.is_empty:
                return {"type": "Point", "coordinates": [float(point.x), float(point.y)]}
    except Exception as exc:  # pragma: no cover - fallback for missing shapely/runtime issues
        logger.debug("Shapely fallback in derive_representative_point: %s", exc)

    outer_ring = _largest_outer_ring_from_geometry(geometry)
    if outer_ring is None:
        return None

    x, y = _ring_centroid(outer_ring)
    return {"type": "Point", "coordinates": [x, y]}


def assemble_geometry(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Assemble geometry from member way coordinates.

    Uses shapely when available; otherwise falls back to a simple MultiPolygon
    assembly suitable for ingestion tests.
    """
    outer_rings: list[list[list[float]]] = []
    inner_rings: list[list[list[float]]] = []
    outer_linework: list[list[list[float]]] = []
    inner_linework: list[list[list[float]]] = []

    for member in members:
        if member.get("type") != "way":
            continue

        role = member.get("role", "outer")

        points = member.get("geometry", [])
        coords = [[float(point["lon"]), float(point["lat"])] for point in points if "lon" in point and "lat" in point]
        if len(coords) < 2:
            continue

        if role == "inner":
            inner_linework.append(coords)
        else:
            outer_linework.append(coords)

        if len(coords) >= 3:
            ring_coords = coords if coords[0] == coords[-1] else [*coords, coords[0]]
            if role == "inner":
                inner_rings.append(ring_coords)
            else:
                outer_rings.append(ring_coords)

    if not outer_linework:
        return None

    try:
        from shapely.geometry import LineString, MultiPolygon, Polygon, mapping
        from shapely.ops import polygonize, unary_union

        outer_lines = [LineString(coords) for coords in outer_linework if len(coords) >= 2]
        merged_outer = unary_union(outer_lines)
        polygons = [polygon for polygon in polygonize(merged_outer) if polygon.is_valid and not polygon.is_empty]

        if not polygons:
            deduped_outer_rings = _filter_duplicate_rings(outer_rings)
            polygons = [Polygon(ring) for ring in deduped_outer_rings if len(ring) >= 4]
            polygons = [polygon for polygon in polygons if polygon.is_valid and not polygon.is_empty]

        if inner_linework and polygons:
            inner_lines = [LineString(coords) for coords in inner_linework if len(coords) >= 2]
            merged_inner = unary_union(inner_lines)
            inner_polygons = [polygon for polygon in polygonize(merged_inner) if polygon.is_valid and not polygon.is_empty]

            if not inner_polygons and inner_rings:
                deduped_inner_rings = _filter_duplicate_rings(inner_rings)
                inner_polygons = [Polygon(ring) for ring in deduped_inner_rings if len(ring) >= 4]
                inner_polygons = [polygon for polygon in inner_polygons if polygon.is_valid and not polygon.is_empty]

            if inner_polygons:
                inner_union = unary_union(inner_polygons)
                clipped_polygons: list[Polygon] = []
                for polygon in polygons:
                    diff = polygon.difference(inner_union)
                    if diff.is_empty:
                        continue
                    if diff.geom_type == "Polygon":
                        clipped_polygons.append(diff)
                    elif diff.geom_type == "MultiPolygon":
                        clipped_polygons.extend(geom for geom in diff.geoms if geom.is_valid and not geom.is_empty)
                polygons = clipped_polygons

        if not polygons:
            return None

        merged_polygon = unary_union(polygons)

        if merged_polygon.is_empty:
            return None

        if merged_polygon.geom_type == "Polygon":
            return mapping(merged_polygon)

        if merged_polygon.geom_type == "MultiPolygon":
            return mapping(merged_polygon)

        multi_polygon = MultiPolygon([geom for geom in getattr(merged_polygon, "geoms", []) if geom.geom_type == "Polygon"])
        return mapping(multi_polygon) if not multi_polygon.is_empty else None
    except Exception as exc:  # pragma: no cover - fallback for missing shapely/runtime issues
        logger.debug("Shapely fallback in assemble_geometry: %s", exc)
        deduped_outer_rings = _filter_duplicate_rings(outer_rings)
        return {"type": "MultiPolygon", "coordinates": [[ring] for ring in deduped_outer_rings]} if deduped_outer_rings else None
