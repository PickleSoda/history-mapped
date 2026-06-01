from __future__ import annotations

import json
import os
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 1


def initialize_index_schema(index_path: str | Path) -> None:
    resolved_path = Path(index_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(resolved_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS index_metadata (
                schema_version INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                source_size_bytes INTEGER NOT NULL,
                source_mtime_epoch INTEGER NOT NULL,
                build_completed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                object_type TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                name TEXT,
                normalized_name TEXT,
                wikidata_id TEXT,
                raw_tags_json TEXT NOT NULL,
                point_lat REAL,
                point_lon REAL,
                PRIMARY KEY (object_type, object_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS object_aliases (
                object_type TEXT NOT NULL,
                object_id INTEGER NOT NULL,
                alias_key TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                UNIQUE (object_type, object_id, alias_key, alias_value)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS way_node_refs (
                way_id INTEGER NOT NULL,
                sequence_index INTEGER NOT NULL,
                node_id INTEGER NOT NULL,
                UNIQUE (way_id, sequence_index, node_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS relation_members (
                relation_id INTEGER NOT NULL,
                sequence_index INTEGER NOT NULL,
                member_type TEXT NOT NULL,
                member_ref INTEGER NOT NULL,
                member_role TEXT NOT NULL,
                UNIQUE (relation_id, sequence_index, member_type, member_ref, member_role)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_normalized_name ON objects (normalized_name)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_objects_wikidata_id ON objects (wikidata_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_object_aliases_normalized_alias ON object_aliases (normalized_alias)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_way_node_refs_way_id ON way_node_refs (way_id, sequence_index)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_relation_members_relation_id ON relation_members (relation_id, sequence_index)"
        )
        connection.commit()


def write_completed_metadata(
    index_path: str | Path,
    *,
    source_path: Path,
    source_size_bytes: int,
    source_mtime_epoch: int,
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.execute("DELETE FROM index_metadata")
        connection.execute(
            """
            INSERT INTO index_metadata (
                schema_version,
                source_path,
                source_size_bytes,
                source_mtime_epoch,
                build_completed_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                SCHEMA_VERSION,
                source_path.as_posix(),
                source_size_bytes,
                source_mtime_epoch,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()


def read_index_metadata(index_path: str | Path) -> dict[str, object]:
    with sqlite3.connect(Path(index_path)) as connection:
        row = connection.execute(
            """
            SELECT schema_version, source_path, source_size_bytes, source_mtime_epoch, build_completed_at
            FROM index_metadata
            LIMIT 1
            """
        ).fetchone()

    if row is None:
        raise RuntimeError("Index metadata not found")

    return {
        "schema_version": row[0],
        "source_path": row[1],
        "source_size_bytes": row[2],
        "source_mtime_epoch": row[3],
        "build_completed_at": row[4],
    }


def insert_objects(
    index_path: str | Path,
    rows: Iterable[tuple[str, int, str | None, str | None, str | None, str, float | None, float | None]],
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO objects (
                object_type,
                object_id,
                name,
                normalized_name,
                wikidata_id,
                raw_tags_json,
                point_lat,
                point_lon
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            list(rows),
        )
        connection.commit()


def insert_object_aliases(
    index_path: str | Path,
    rows: Iterable[tuple[str, int, str, str, str]],
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO object_aliases (
                object_type,
                object_id,
                alias_key,
                alias_value,
                normalized_alias
            ) VALUES (?, ?, ?, ?, ?)
            """,
            list(rows),
        )
        connection.commit()


def insert_way_node_refs(index_path: str | Path, rows: Iterable[tuple[int, int, int]]) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO way_node_refs (way_id, sequence_index, node_id) VALUES (?, ?, ?)",
            list(rows),
        )
        connection.commit()


def insert_relation_members(
    index_path: str | Path,
    rows: Iterable[tuple[int, int, str, int, str]],
) -> None:
    with sqlite3.connect(Path(index_path)) as connection:
        connection.executemany(
            """
            INSERT OR REPLACE INTO relation_members (
                relation_id,
                sequence_index,
                member_type,
                member_ref,
                member_role
            ) VALUES (?, ?, ?, ?, ?)
            """,
            list(rows),
        )
        connection.commit()


def index_matches_source(
    index_path: str | Path,
    *,
    source_path: Path,
    source_size_bytes: int,
    source_mtime_epoch: int,
    expected_schema_version: int = SCHEMA_VERSION,
) -> bool:
    try:
        metadata = read_index_metadata(index_path)
    except RuntimeError:
        return False

    return bool(
        metadata["schema_version"] == expected_schema_version
        and metadata["source_path"] == source_path.as_posix()
        and metadata["source_size_bytes"] == source_size_bytes
        and metadata["source_mtime_epoch"] == source_mtime_epoch
        and metadata["build_completed_at"]
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