from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any


def find_objects_by_name(index_path: str | Path, name: str) -> list[dict[str, Any]]:
    normalized_name = _normalize_name(name)
    if normalized_name is None:
        return []

    with sqlite3.connect(Path(index_path)) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT
                objects.object_type,
                objects.object_id,
                objects.name,
                objects.normalized_name,
                objects.wikidata_id,
                objects.raw_tags_json,
                objects.point_lat,
                objects.point_lon
            FROM objects
            LEFT JOIN object_aliases
                ON object_aliases.object_type = objects.object_type
               AND object_aliases.object_id = objects.object_id
            WHERE objects.normalized_name = ? OR object_aliases.normalized_alias = ?
            ORDER BY objects.object_type, objects.object_id
            """,
            (normalized_name, normalized_name),
        ).fetchall()

    return [_hydrate_object_row(row) for row in rows]


def find_objects_by_wikidata_id(index_path: str | Path, wikidata_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(Path(index_path)) as connection:
        rows = connection.execute(
            """
            SELECT object_type, object_id, name, normalized_name, wikidata_id, raw_tags_json, point_lat, point_lon
            FROM objects
            WHERE wikidata_id = ?
            ORDER BY object_type, object_id
            """,
            (wikidata_id.strip(),),
        ).fetchall()

    return [_hydrate_object_row(row) for row in rows]


def find_objects_by_tag_value(index_path: str | Path, *, tag_key: str, tag_value: str) -> list[dict[str, Any]]:
    normalized_tag_value = _normalize_name(tag_value)
    if normalized_tag_value is None:
        return []

    with sqlite3.connect(Path(index_path)) as connection:
        rows = connection.execute(
            """
            SELECT object_type, object_id, name, normalized_name, wikidata_id, raw_tags_json, point_lat, point_lon
            FROM objects
            ORDER BY object_type, object_id
            """
        ).fetchall()

    matches: list[dict[str, Any]] = []
    for row in rows:
        hydrated = _hydrate_object_row(row)
        raw_value = hydrated["raw_tags"].get(tag_key)
        if _normalize_name(raw_value) == normalized_tag_value:
            matches.append(hydrated)
    return matches


def _hydrate_object_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "object_type": row[0],
        "object_id": row[1],
        "name": row[2],
        "normalized_name": row[3],
        "wikidata_id": row[4],
        "raw_tags": json.loads(row[5]),
        "point_lat": row[6],
        "point_lon": row[7],
    }


def _normalize_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    collapsed = unicodedata.normalize("NFC", stripped).casefold().replace("-", " ")
    return " ".join(collapsed.split())