from __future__ import annotations

import json
import os
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 1
PAYLOAD_FORMAT_VERSION = 1


def initialize_index_schema(index_path: str | Path) -> None:
    resolved_path = Path(index_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(resolved_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS index_metadata (
                schema_version INTEGER NOT NULL,
                payload_format_version INTEGER NOT NULL,
                source_fingerprint_sha256 TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_size_bytes INTEGER NOT NULL,
                source_mtime_epoch INTEGER NOT NULL,
                build_completed_at TEXT NOT NULL,
                fuzzy_matcher_name TEXT NOT NULL,
                fuzzy_matcher_version TEXT NOT NULL,
                fuzzy_threshold REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS relations (
                relation_id INTEGER PRIMARY KEY,
                name TEXT,
                normalized_name TEXT,
                wikidata_id TEXT,
                is_chronology INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chronology_edges (
                chronology_relation_id INTEGER NOT NULL,
                member_relation_id INTEGER NOT NULL,
                UNIQUE (chronology_relation_id, member_relation_id),
                FOREIGN KEY (chronology_relation_id) REFERENCES relations (relation_id),
                FOREIGN KEY (member_relation_id) REFERENCES relations (relation_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS qid_edges (
                source_relation_id INTEGER NOT NULL,
                edge_kind TEXT NOT NULL,
                target_wikidata_id TEXT NOT NULL,
                FOREIGN KEY (source_relation_id) REFERENCES relations (relation_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS qid_to_relations (
                wikidata_id TEXT NOT NULL,
                relation_id INTEGER NOT NULL,
                FOREIGN KEY (relation_id) REFERENCES relations (relation_id)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_wikidata_id ON relations (wikidata_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_relations_normalized_name ON relations (normalized_name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_chronology_edges_member ON chronology_edges (member_relation_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_qid_edges_source ON qid_edges (source_relation_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_qid_to_relations_wikidata ON qid_to_relations (wikidata_id)")
        connection.commit()


def write_completed_metadata(
    index_path: str | Path,
    *,
    source_path: Path,
    source_fingerprint_sha256: str,
    source_size_bytes: int,
    source_mtime_epoch: int,
    fuzzy_matcher_name: str,
    fuzzy_matcher_version: str,
    fuzzy_threshold: float,
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.execute("DELETE FROM index_metadata")
        connection.execute(
            """
            INSERT INTO index_metadata (
                schema_version,
                payload_format_version,
                source_fingerprint_sha256,
                source_path,
                source_size_bytes,
                source_mtime_epoch,
                build_completed_at,
                fuzzy_matcher_name,
                fuzzy_matcher_version,
                fuzzy_threshold
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                SCHEMA_VERSION,
                PAYLOAD_FORMAT_VERSION,
                source_fingerprint_sha256,
                source_path.as_posix(),
                source_size_bytes,
                source_mtime_epoch,
                datetime.now(timezone.utc).isoformat(),
                fuzzy_matcher_name,
                fuzzy_matcher_version,
                fuzzy_threshold,
            ),
        )
        connection.commit()


def read_index_metadata(index_path: str | Path) -> dict[str, object]:
    with sqlite3.connect(Path(index_path)) as connection:
        row = connection.execute(
            """
            SELECT schema_version, payload_format_version, source_fingerprint_sha256,
                   source_path, source_size_bytes, source_mtime_epoch, build_completed_at,
                   fuzzy_matcher_name, fuzzy_matcher_version, fuzzy_threshold
            FROM index_metadata
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise RuntimeError("Index metadata not found")

    return {
        "schema_version": row[0],
        "payload_format_version": row[1],
        "source_fingerprint_sha256": row[2],
        "source_path": row[3],
        "source_size_bytes": row[4],
        "source_mtime_epoch": row[5],
        "build_completed_at": row[6],
        "fuzzy_matcher_name": row[7],
        "fuzzy_matcher_version": row[8],
        "fuzzy_threshold": row[9],
    }


def insert_relations(
    index_path: str | Path,
    rows: Iterable[tuple[int, str | None, str | None, str | None, bool | int, str]],
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            """
            INSERT INTO relations (relation_id, name, normalized_name, wikidata_id, is_chronology, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    relation_id,
                    name,
                    normalized_name,
                    wikidata_id,
                    1 if is_chronology else 0,
                    payload_json,
                )
                for relation_id, name, normalized_name, wikidata_id, is_chronology, payload_json in rows
            ],
        )
        connection.commit()


def insert_chronology_edges(index_path: str | Path, rows: Iterable[tuple[int, int]]) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO chronology_edges (chronology_relation_id, member_relation_id) VALUES (?, ?)",
            list(rows),
        )
        connection.commit()


def insert_qid_edges(index_path: str | Path, rows: Iterable[tuple[int, str, str]]) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            "INSERT INTO qid_edges (source_relation_id, edge_kind, target_wikidata_id) VALUES (?, ?, ?)",
            list(rows),
        )
        connection.commit()


def insert_qid_to_relations(index_path: str | Path, rows: Iterable[tuple[str, int]]) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            "INSERT INTO qid_to_relations (wikidata_id, relation_id) VALUES (?, ?)",
            list(rows),
        )
        connection.commit()


def relation_ids_for_wikidata_id(index_path: str | Path, wikidata_id: str) -> list[int]:
    with sqlite3.connect(Path(index_path)) as connection:
        rows = connection.execute(
            "SELECT relation_id FROM qid_to_relations WHERE wikidata_id = ? ORDER BY relation_id",
            (wikidata_id,),
        ).fetchall()

    return [int(row[0]) for row in rows]


def load_relations_by_ids(index_path: str | Path, relation_ids: Iterable[int]) -> dict[int, dict]:
    resolved_relation_ids = sorted({int(relation_id) for relation_id in relation_ids})
    if not resolved_relation_ids:
        return {}

    placeholders = ", ".join("?" for _ in resolved_relation_ids)
    with sqlite3.connect(Path(index_path)) as connection:
        rows = connection.execute(
            f"SELECT relation_id, payload_json FROM relations WHERE relation_id IN ({placeholders})",
            tuple(resolved_relation_ids),
        ).fetchall()

    return {int(relation_id): json.loads(payload_json) for relation_id, payload_json in rows}


def index_matches_source(
    index_path: str | Path,
    *,
    source_fingerprint_sha256: str,
    expected_schema_version: int = SCHEMA_VERSION,
) -> bool:
    metadata = read_index_metadata(index_path)
    return bool(
        metadata["schema_version"] == expected_schema_version
        and metadata["source_fingerprint_sha256"] == source_fingerprint_sha256
    )


def open_index_readonly(index_path: str | Path) -> sqlite3.Connection:
    resolved_path = Path(index_path).resolve()
    return sqlite3.connect(f"file:{resolved_path.as_posix()}?mode=ro", uri=True)


def acquire_build_lock(
    index_path: str | Path,
    *,
    source_path: Path,
    stale_timeout_seconds: int,
) -> Path:
    lock_path = Path(index_path).with_suffix(Path(index_path).suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
    }

    if lock_path.exists():
        existing = json.loads(lock_path.read_text(encoding="utf-8"))
        started_at = datetime.fromisoformat(existing["started_at"])
        age_seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())
        existing_pid = int(existing.get("pid", -1))

        if age_seconds > stale_timeout_seconds and not _process_is_alive(existing_pid):
            lock_path.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"Index build already running for: {index_path}")

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Index build already running for: {index_path}") from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except Exception:
        lock_path.unlink(missing_ok=True)
        raise

    return lock_path


def release_build_lock(lock_path: str | Path) -> None:
    Path(lock_path).unlink(missing_ok=True)


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False

    return True