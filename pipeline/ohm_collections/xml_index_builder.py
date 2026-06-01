from __future__ import annotations

import json
import os
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pipeline.ohm_collections.xml_index_store import (
    acquire_build_lock,
    index_matches_source,
    initialize_index_schema,
    insert_object_aliases,
    insert_objects,
    insert_relation_members,
    insert_way_node_refs,
    read_index_metadata,
    release_build_lock,
    write_completed_metadata,
)


_BATCH_SIZE = 1000
_TOP_LEVEL_ELEMENTS = {"node", "way", "relation"}


class MalformedElementError(RuntimeError):
    def __init__(self, reason_code: str, reason: str, *, element_id: int | None = None) -> None:
        super().__init__(reason)
        self.reason_code = reason_code
        self.reason = reason
        self.element_id = element_id


def build_index(
    source_path: str | Path,
    *,
    index_path: str | Path,
    force: bool = False,
    stale_timeout_seconds: int = 900,
) -> dict[str, Any]:
    resolved_source_path = Path(source_path)
    resolved_index_path = Path(index_path)
    diagnostics_path = resolved_index_path.with_suffix(resolved_index_path.suffix + ".skipped.jsonl")
    source_stat = resolved_source_path.stat()
    source_size_bytes = source_stat.st_size
    source_mtime_epoch = int(source_stat.st_mtime)

    existing_metadata = _read_existing_metadata(resolved_index_path)
    if resolved_index_path.exists() and existing_metadata is not None:
        if index_matches_source(
            resolved_index_path,
            source_path=resolved_source_path,
            source_size_bytes=source_size_bytes,
            source_mtime_epoch=source_mtime_epoch,
        ):
            return {
                "status": "skipped",
                "index_path": resolved_index_path,
                "skipped_elements": 0,
            }
        if existing_metadata.get("build_completed_at") and not force:
            raise RuntimeError("Index source changed; rerun with --force to rebuild.")

    lock_path = acquire_build_lock(
        resolved_index_path,
        source_path=resolved_source_path,
        stale_timeout_seconds=stale_timeout_seconds,
    )
    temp_index_path = resolved_index_path.with_name(f"{resolved_index_path.name}.tmp.{os.getpid()}")
    temp_diagnostics_path = diagnostics_path.with_name(f"{diagnostics_path.name}.tmp.{os.getpid()}")

    try:
        temp_index_path.unlink(missing_ok=True)
        temp_diagnostics_path.unlink(missing_ok=True)

        initialize_index_schema(temp_index_path)
        build_result = _stream_index_records(resolved_source_path, temp_index_path)
        write_completed_metadata(
            temp_index_path,
            source_path=resolved_source_path,
            source_size_bytes=source_size_bytes,
            source_mtime_epoch=source_mtime_epoch,
        )

        os.replace(temp_index_path, resolved_index_path)

        if build_result["diagnostics"]:
            _write_diagnostics(temp_diagnostics_path, build_result["diagnostics"])
            temp_diagnostics_path.replace(diagnostics_path)
        else:
            diagnostics_path.unlink(missing_ok=True)
    except Exception as exc:
        cleanup_warning = _cleanup_temp_artifacts(temp_index_path, temp_diagnostics_path)
        if force and resolved_index_path.exists():
            raise RuntimeError(f"Failed to replace built index: {exc}{cleanup_warning}") from exc
        raise RuntimeError(f"Failed to build index: {exc}{cleanup_warning}") from exc
    finally:
        release_build_lock(lock_path)

    result: dict[str, Any] = {
        "status": "completed",
        "index_path": resolved_index_path,
        "object_count": build_result["object_count"],
        "skipped_elements": build_result["skipped_elements"],
    }
    if build_result["diagnostics"]:
        result["diagnostics_path"] = diagnostics_path.as_posix()
    return result


def _stream_index_records(source_path: Path, index_path: Path) -> dict[str, Any]:
    object_rows: list[tuple[str, int, str | None, str | None, str | None, str, float | None, float | None]] = []
    alias_rows: list[tuple[str, int, str, str, str]] = []
    way_node_rows: list[tuple[int, int, int]] = []
    relation_member_rows: list[tuple[int, int, str, int, str]] = []
    diagnostics: list[dict[str, Any]] = []
    object_count = 0

    for _event, element in ET.iterparse(source_path, events=("end",)):
        if element.tag not in _TOP_LEVEL_ELEMENTS:
            continue

        try:
            row_batch = _rows_for_element(element)
            object_rows.append(row_batch[0])
            alias_rows.extend(row_batch[1])
            way_node_rows.extend(row_batch[2])
            relation_member_rows.extend(row_batch[3])
            object_count += 1
            if len(object_rows) >= _BATCH_SIZE:
                _flush_batches(index_path, object_rows, alias_rows, way_node_rows, relation_member_rows)
        except MalformedElementError as exc:
            diagnostics.append(
                {
                    "element_tag": element.tag,
                    "element_id": exc.element_id,
                    "reason_code": exc.reason_code,
                    "reason": exc.reason,
                }
            )
        finally:
            element.clear()

    _flush_batches(index_path, object_rows, alias_rows, way_node_rows, relation_member_rows)
    return {
        "object_count": object_count,
        "skipped_elements": len(diagnostics),
        "diagnostics": diagnostics,
    }


def _rows_for_element(
    element: ET.Element,
) -> tuple[
    tuple[str, int, str | None, str | None, str | None, str, float | None, float | None],
    list[tuple[str, int, str, str, str]],
    list[tuple[int, int, int]],
    list[tuple[int, int, str, int, str]],
]:
    if element.tag == "node":
        return _node_rows(element)
    if element.tag == "way":
        return _way_rows(element)
    return _relation_rows(element)


def _node_rows(
    element: ET.Element,
) -> tuple[
    tuple[str, int, str | None, str | None, str | None, str, float | None, float | None],
    list[tuple[str, int, str, str, str]],
    list[tuple[int, int, int]],
    list[tuple[int, int, str, int, str]],
]:
    object_id = _required_int(element.get("id"), element_tag="node", reason_code="missing_id")
    tags = _extract_tags(element)
    object_row = _object_row(
        object_type="node",
        object_id=object_id,
        tags=tags,
        point_lat=_optional_float(element.get("lat")),
        point_lon=_optional_float(element.get("lon")),
    )
    return object_row, _alias_rows("node", object_id, tags), [], []


def _way_rows(
    element: ET.Element,
) -> tuple[
    tuple[str, int, str | None, str | None, str | None, str, float | None, float | None],
    list[tuple[str, int, str, str, str]],
    list[tuple[int, int, int]],
    list[tuple[int, int, str, int, str]],
]:
    object_id = _required_int(element.get("id"), element_tag="way", reason_code="missing_id")
    tags = _extract_tags(element)
    way_node_rows: list[tuple[int, int, int]] = []

    for sequence_index, node_ref_element in enumerate(element.findall("nd")):
        node_ref_value = node_ref_element.get("ref")
        if node_ref_value is None:
            raise MalformedElementError(
                "missing_node_ref",
                f"Way {object_id} has nd entry without ref",
                element_id=object_id,
            )
        way_node_rows.append((object_id, sequence_index, int(node_ref_value)))

    object_row = _object_row(
        object_type="way",
        object_id=object_id,
        tags=tags,
        point_lat=None,
        point_lon=None,
    )
    return object_row, _alias_rows("way", object_id, tags), way_node_rows, []


def _relation_rows(
    element: ET.Element,
) -> tuple[
    tuple[str, int, str | None, str | None, str | None, str, float | None, float | None],
    list[tuple[str, int, str, str, str]],
    list[tuple[int, int, int]],
    list[tuple[int, int, str, int, str]],
]:
    object_id = _required_int(element.get("id"), element_tag="relation", reason_code="missing_id")
    tags = _extract_tags(element)
    relation_member_rows: list[tuple[int, int, str, int, str]] = []

    for sequence_index, member_element in enumerate(element.findall("member")):
        member_ref_value = member_element.get("ref")
        if member_ref_value is None:
            raise MalformedElementError(
                "missing_member_ref",
                f"Relation {object_id} has member without ref",
                element_id=object_id,
            )
        member_type = _normalize_optional_string(member_element.get("type"))
        if member_type is None:
            raise MalformedElementError(
                "missing_member_type",
                f"Relation {object_id} has member without type",
                element_id=object_id,
            )
        relation_member_rows.append(
            (
                object_id,
                sequence_index,
                member_type,
                int(member_ref_value),
                _normalize_optional_string(member_element.get("role")) or "",
            )
        )

    object_row = _object_row(
        object_type="relation",
        object_id=object_id,
        tags=tags,
        point_lat=None,
        point_lon=None,
    )
    return object_row, _alias_rows("relation", object_id, tags), [], relation_member_rows


def _object_row(
    *,
    object_type: str,
    object_id: int,
    tags: dict[str, str],
    point_lat: float | None,
    point_lon: float | None,
) -> tuple[str, int, str | None, str | None, str | None, str, float | None, float | None]:
    name = _normalize_optional_string(tags.get("name"))
    wikidata_id = _normalize_optional_string(tags.get("wikidata"))
    return (
        object_type,
        object_id,
        name,
        _normalize_name(name),
        wikidata_id,
        json.dumps(tags, ensure_ascii=False, separators=(",", ":")),
        point_lat,
        point_lon,
    )


def _extract_tags(element: ET.Element) -> dict[str, str]:
    tags: dict[str, str] = {}
    for tag_element in element.findall("tag"):
        key = tag_element.get("k")
        value = tag_element.get("v")
        if not isinstance(key, str) or value is None:
            continue
        tags[key] = value
    return tags


def _alias_rows(object_type: str, object_id: int, tags: dict[str, str]) -> list[tuple[str, int, str, str, str]]:
    rows: list[tuple[str, int, str, str, str]] = []
    for alias_key, alias_value in tags.items():
        normalized_alias = _normalize_name(alias_value)
        if alias_key == "name" or normalized_alias is None or "name" not in alias_key:
            continue
        rows.append((object_type, object_id, alias_key, alias_value, normalized_alias))
    return rows


def _flush_batches(
    index_path: Path,
    object_rows: list[tuple[str, int, str | None, str | None, str | None, str, float | None, float | None]],
    alias_rows: list[tuple[str, int, str, str, str]],
    way_node_rows: list[tuple[int, int, int]],
    relation_member_rows: list[tuple[int, int, str, int, str]],
) -> None:
    if object_rows:
        insert_objects(index_path, object_rows)
        object_rows.clear()
    if alias_rows:
        insert_object_aliases(index_path, alias_rows)
        alias_rows.clear()
    if way_node_rows:
        insert_way_node_refs(index_path, way_node_rows)
        way_node_rows.clear()
    if relation_member_rows:
        insert_relation_members(index_path, relation_member_rows)
        relation_member_rows.clear()


def _write_diagnostics(path: Path, diagnostics: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for diagnostic in diagnostics:
            handle.write(json.dumps(diagnostic, ensure_ascii=False))
            handle.write("\n")


def _read_existing_metadata(index_path: Path) -> dict[str, Any] | None:
    if not index_path.exists():
        return None

    try:
        return read_index_metadata(index_path)
    except (RuntimeError, sqlite3.DatabaseError):
        return None


def _required_int(value: str | None, *, element_tag: str, reason_code: str) -> int:
    if value is None:
        raise MalformedElementError(reason_code, f"{element_tag} element is missing an id", element_id=None)
    return int(value)


def _optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_name(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    collapsed = unicodedata.normalize("NFC", normalized).casefold().replace("-", " ")
    return " ".join(collapsed.split())


def _cleanup_temp_artifacts(*paths: Path) -> str:
    warnings: list[str] = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            warnings.append(f"could not remove temporary artifact {path}: {cleanup_error}")
    if not warnings:
        return ""
    return " Cleanup warning: " + "; ".join(warnings)