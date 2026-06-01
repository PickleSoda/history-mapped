from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pipeline.ohm_borders.fetcher import derive_representative_point


def resolve_best_point(index_path: str | Path, *, object_type: str, object_id: int) -> dict[str, Any]:
    resolved_index_path = Path(index_path)

    with sqlite3.connect(resolved_index_path) as connection:
        object_row = connection.execute(
            """
            SELECT object_type, object_id, point_lat, point_lon
            FROM objects
            WHERE object_type = ? AND object_id = ?
            LIMIT 1
            """,
            (object_type, int(object_id)),
        ).fetchone()

        if object_row is None:
            return _no_point("missing_object")

        if object_type == "node":
            point = _point_from_object_row(object_row)
            if point is not None:
                return {
                    "status": "resolved",
                    "geometry_source": "ohm_point",
                    "point": point,
                }
            return _no_point("missing_geometry")

        if object_type == "way":
            geometry = _geometry_for_way(connection, int(object_id))
        elif object_type == "relation":
            geometry = _geometry_for_relation(connection, int(object_id))
        else:
            geometry = None

    point = derive_representative_point(geometry)
    if point is None:
        return _no_point("missing_geometry")

    return {
        "status": "resolved",
        "geometry_source": "ohm_representative_point",
        "point": point,
    }


def _geometry_for_way(connection: sqlite3.Connection, way_id: int) -> dict[str, Any] | None:
    ring = _ring_for_way(connection, way_id)
    if ring is None:
        return None
    return {"type": "Polygon", "coordinates": [ring]}


def _geometry_for_relation(connection: sqlite3.Connection, relation_id: int) -> dict[str, Any] | None:
    member_rows = connection.execute(
        """
        SELECT member_type, member_ref, member_role
        FROM relation_members
        WHERE relation_id = ?
        ORDER BY sequence_index, member_type, member_ref, member_role
        """,
        (relation_id,),
    ).fetchall()

    polygons: list[list[list[list[float]]]] = []
    for member_type, member_ref, member_role in member_rows:
        if member_type != "way":
            continue
        ring = _ring_for_way(connection, int(member_ref))
        if ring is None:
            continue
        if member_role == "inner":
            continue
        polygons.append([ring])

    if not polygons:
        return None
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def _ring_for_way(connection: sqlite3.Connection, way_id: int) -> list[list[float]] | None:
    node_rows = connection.execute(
        """
        SELECT objects.point_lon, objects.point_lat
        FROM way_node_refs
        JOIN objects
          ON objects.object_type = 'node'
         AND objects.object_id = way_node_refs.node_id
        WHERE way_node_refs.way_id = ?
        ORDER BY way_node_refs.sequence_index
        """,
        (way_id,),
    ).fetchall()

    coordinates = [
        [float(point_lon), float(point_lat)]
        for point_lon, point_lat in node_rows
        if point_lon is not None and point_lat is not None
    ]
    if len(coordinates) < 3:
        return None

    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])

    if len(coordinates) < 4:
        return None
    return coordinates


def _point_from_object_row(row: tuple[Any, ...]) -> dict[str, Any] | None:
    point_lat = row[2]
    point_lon = row[3]
    if point_lat is None or point_lon is None:
        return None
    return {"type": "Point", "coordinates": [float(point_lon), float(point_lat)]}


def _no_point(reason: str) -> dict[str, Any]:
    return {
        "status": "no_point",
        "geometry_source": "none",
        "point": None,
        "reason": reason,
    }