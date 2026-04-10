"""Fetch and parse OHM admin_level=2 borders via Overpass."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.openhistoricalmap.org/api/interpreter"

GLOBAL_QUERY = """
[out:json][timeout:1800];
relation["boundary"="administrative"]["admin_level"="2"];
out geom;
"""


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

    try:
        from shapely.geometry import MultiPolygon, Polygon, mapping

        polygons = [Polygon(ring) for ring in rings if len(ring) >= 4]
        polygons = [polygon for polygon in polygons if polygon.is_valid and not polygon.is_empty]
        if not polygons:
            return None

        return mapping(MultiPolygon(polygons))
    except Exception as exc:  # pragma: no cover - fallback for missing shapely/runtime issues
        logger.debug("Shapely fallback in assemble_geometry: %s", exc)
        return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
