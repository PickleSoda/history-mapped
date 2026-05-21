from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
import unicodedata

from pipeline.ohm_borders.index_store import (
    acquire_build_lock,
    initialize_index_schema,
    read_index_metadata,
    release_build_lock,
    write_completed_metadata,
)

try:
    import ijson
except ImportError:  # pragma: no cover - fallback for environments without optional dependency installed yet.
    ijson = None

try:
    import rapidfuzz
except ImportError:  # pragma: no cover - fallback for environments without optional dependency installed yet.
    rapidfuzz = None


_QID_EDGE_TAGS: dict[str, str] = {
    "predecessor:wikidata": "predecessor_wikidata",
    "preceded_by:wikidata": "preceded_by_wikidata",
    "successor:wikidata": "successor_wikidata",
    "succeeded_by:wikidata": "succeeded_by_wikidata",
    "start_event:wikidata": "start_event_wikidata",
    "end_event:wikidata": "end_event_wikidata",
}


def build_index(
    source_path: str | Path,
    *,
    index_path: str | Path,
    force: bool = False,
    stale_timeout_seconds: int = 900,
) -> dict[str, Any]:
    resolved_source_path = Path(source_path)
    resolved_index_path = Path(index_path)
    fingerprint = source_fingerprint_for_file(resolved_source_path)

    if resolved_index_path.exists():
        existing_metadata = read_index_metadata(resolved_index_path)
        if existing_metadata["source_fingerprint_sha256"] == fingerprint:
            return {
                "status": "skipped",
                "index_path": resolved_index_path,
                "source_fingerprint_sha256": fingerprint,
            }
        if not force:
            raise RuntimeError("Index source changed; rerun with --force to rebuild.")

    lock_path = acquire_build_lock(
        resolved_index_path,
        source_path=resolved_source_path,
        stale_timeout_seconds=stale_timeout_seconds,
    )
    temp_index_path = resolved_index_path.with_name(f"{resolved_index_path.name}.tmp.{os.getpid()}")

    try:
        if temp_index_path.exists():
            temp_index_path.unlink()

        initialize_index_schema(temp_index_path)
        relation_count = _write_relation_records(temp_index_path, _iter_relation_records(resolved_source_path))
        write_completed_metadata(
            temp_index_path,
            source_path=resolved_source_path,
            source_fingerprint_sha256=fingerprint,
            source_size_bytes=resolved_source_path.stat().st_size,
            source_mtime_epoch=int(resolved_source_path.stat().st_mtime),
            fuzzy_matcher_name="rapidfuzz",
            fuzzy_matcher_version=getattr(rapidfuzz, "__version__", "unavailable"),
            fuzzy_threshold=0.85,
        )

        os.replace(temp_index_path, resolved_index_path)
    except Exception as exc:
        cleanup_warning = _cleanup_temp_index(temp_index_path)
        if force and resolved_index_path.exists():
            raise RuntimeError(
                "Failed to replace built index because the existing file appears to be in use. "
                "Leave the current completed index in place and retry once active readers release it. "
                f"Original error: {exc}{cleanup_warning}"
            ) from exc
        raise RuntimeError(f"Failed to build index: {exc}{cleanup_warning}") from exc
    finally:
        release_build_lock(lock_path)

    return {
        "status": "completed",
        "index_path": resolved_index_path,
        "source_fingerprint_sha256": fingerprint,
        "relation_count": relation_count,
    }


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint_for_file(path: str | Path) -> str:
    return _sha256_for_file(Path(path))


def _iter_relation_records(source_path: Path) -> Iterable[dict[str, Any]]:
    if ijson is None:
        payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
        for relation in payload.get("elements", []):
            if isinstance(relation, dict) and relation.get("type") == "relation" and "id" in relation:
                yield relation
        return

    with source_path.open("rb") as handle:
        if handle.read(3) != b"\xef\xbb\xbf":
            handle.seek(0)

        for relation in ijson.items(handle, "elements.item"):
            if isinstance(relation, dict) and relation.get("type") == "relation" and "id" in relation:
                yield relation


def _write_relation_records(index_path: Path, relation_records: Iterable[dict[str, Any]]) -> int:
    relation_count = 0
    pending_chronology_edges: list[tuple[int, int]] = []
    pending_qid_edges: list[tuple[int, str, str]] = []

    with sqlite3.connect(index_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        for relation in relation_records:
            relation_count += 1
            relation_id = int(relation["id"])
            tags = relation.get("tags", {}) or {}
            wikidata_id = _normalize_optional_string(tags.get("wikidata"))
            connection.execute(
                """
                INSERT INTO relations (relation_id, name, normalized_name, wikidata_id, is_chronology, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    _normalize_optional_string(tags.get("name")),
                    _normalize_name(tags.get("name")),
                    wikidata_id,
                    1 if tags.get("type") == "chronology" else 0,
                    json.dumps(relation, ensure_ascii=False, separators=(",", ":"), default=_json_scalar),
                ),
            )
            if wikidata_id is not None:
                connection.execute(
                    "INSERT INTO qid_to_relations (wikidata_id, relation_id) VALUES (?, ?)",
                    (wikidata_id, relation_id),
                )
            if tags.get("type") == "chronology":
                for member in relation.get("members", []) or []:
                    if member.get("type") == "relation" and "ref" in member:
                        pending_chronology_edges.append((relation_id, int(member["ref"])))

            for tag_name, edge_kind in _QID_EDGE_TAGS.items():
                target_qid = _normalize_optional_string(tags.get(tag_name))
                if target_qid is None:
                    continue
                pending_qid_edges.append((relation_id, edge_kind, target_qid))

        if pending_chronology_edges:
            connection.executemany(
                "INSERT OR IGNORE INTO chronology_edges (chronology_relation_id, member_relation_id) VALUES (?, ?)",
                pending_chronology_edges,
            )
        if pending_qid_edges:
            connection.executemany(
                "INSERT INTO qid_edges (source_relation_id, edge_kind, target_wikidata_id) VALUES (?, ?, ?)",
                pending_qid_edges,
            )

        connection.commit()
    return relation_count


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_name(value: Any) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    return " ".join(unicodedata.normalize("NFC", normalized).casefold().split())


def _json_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _cleanup_temp_index(path: Path) -> str:
    try:
        path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        return f" Cleanup warning: could not remove temporary index {path}: {cleanup_error}"
    return ""