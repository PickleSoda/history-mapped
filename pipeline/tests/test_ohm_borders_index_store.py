import json
import sqlite3
from pathlib import Path

import pytest

from pipeline.ohm_borders.index_store import (
    PAYLOAD_FORMAT_VERSION,
    SCHEMA_VERSION,
    acquire_build_lock,
    index_matches_source,
    insert_chronology_edges,
    insert_qid_edges,
    insert_qid_to_relations,
    insert_relations,
    initialize_index_schema,
    load_relations_by_ids,
    open_index_readonly,
    read_index_metadata,
    relation_ids_for_wikidata_id,
    release_build_lock,
    write_completed_metadata,
)


def _table_columns(db_path: Path, table_name: str) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()

    return [str(row[1]) for row in rows]


def test_initialize_index_schema_creates_expected_tables_and_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-index.sqlite3"

    initialize_index_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

    assert {"index_metadata", "relations", "chronology_edges", "qid_edges", "qid_to_relations"}.issubset(tables)
    assert _table_columns(db_path, "index_metadata") == [
        "schema_version",
        "payload_format_version",
        "source_fingerprint_sha256",
        "source_path",
        "source_size_bytes",
        "source_mtime_epoch",
        "build_completed_at",
        "fuzzy_matcher_name",
        "fuzzy_matcher_version",
        "fuzzy_threshold",
    ]
    assert _table_columns(db_path, "relations") == [
        "relation_id",
        "name",
        "normalized_name",
        "wikidata_id",
        "is_chronology",
        "payload_json",
    ]


def test_write_completed_metadata_persists_single_metadata_row(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-index.sqlite3"
    initialize_index_schema(db_path)

    write_completed_metadata(
        db_path,
        source_path=Path("output/ohm_borders/global-2026-04-14/raw/overpass.json"),
        source_fingerprint_sha256="abc123",
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
        fuzzy_matcher_name="rapidfuzz",
        fuzzy_matcher_version="3.9.1",
        fuzzy_threshold=0.85,
    )

    metadata = read_index_metadata(db_path)

    assert metadata == {
        "schema_version": SCHEMA_VERSION,
        "payload_format_version": PAYLOAD_FORMAT_VERSION,
        "source_fingerprint_sha256": "abc123",
        "source_path": "output/ohm_borders/global-2026-04-14/raw/overpass.json",
        "source_size_bytes": 4096,
        "source_mtime_epoch": 1716200000,
        "build_completed_at": metadata["build_completed_at"],
        "fuzzy_matcher_name": "rapidfuzz",
        "fuzzy_matcher_version": "3.9.1",
        "fuzzy_threshold": 0.85,
    }
    assert isinstance(metadata["build_completed_at"], str)


def test_acquire_build_lock_writes_process_metadata_and_rejects_active_lock(tmp_path: Path) -> None:
    index_path = tmp_path / "ohm-index.sqlite3"

    lock_path = acquire_build_lock(index_path, source_path=Path("source.json"), stale_timeout_seconds=300)
    payload = json.loads(lock_path.read_text(encoding="utf-8"))

    assert lock_path == index_path.with_suffix(index_path.suffix + ".lock")
    assert payload["source_path"] == "source.json"
    assert isinstance(payload["pid"], int)
    assert isinstance(payload["hostname"], str)
    assert isinstance(payload["started_at"], str)

    with pytest.raises(RuntimeError, match="already running"):
        acquire_build_lock(index_path, source_path=Path("source.json"), stale_timeout_seconds=300)

    release_build_lock(lock_path)
    assert not lock_path.exists()


def test_acquire_build_lock_cleans_up_stale_lock(tmp_path: Path) -> None:
    index_path = tmp_path / "ohm-index.sqlite3"
    lock_path = index_path.with_suffix(index_path.suffix + ".lock")
    lock_path.write_text(
        json.dumps(
            {
                "pid": 999999,
                "hostname": "test-host",
                "started_at": "2000-01-01T00:00:00+00:00",
                "source_path": "source.json",
            }
        ),
        encoding="utf-8",
    )

    acquired = acquire_build_lock(index_path, source_path=Path("source.json"), stale_timeout_seconds=0)

    assert acquired == lock_path
    release_build_lock(acquired)


def test_acquire_build_lock_creates_parent_directory_for_nested_index_path(tmp_path: Path) -> None:
    index_path = tmp_path / "indexes" / "ohm-index.sqlite3"

    lock_path = acquire_build_lock(index_path, source_path=Path("source.json"), stale_timeout_seconds=300)

    assert lock_path.exists()
    assert lock_path.parent == index_path.parent
    release_build_lock(lock_path)


def test_insert_helpers_persist_rows_and_support_lookup_helpers(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-index.sqlite3"
    initialize_index_schema(db_path)

    insert_relations(
        db_path,
        [
            (100, "Roman Empire", "roman empire", "Q1", True, '{"id":100}'),
            (101, "Roman Empire at peak", "roman empire at peak", "Q1", False, '{"id":101}'),
            (200, "Roman Republic", "roman republic", "Q2", False, '{"id":200}'),
        ],
    )
    insert_chronology_edges(db_path, [(100, 101)])
    insert_qid_edges(db_path, [(101, "successor_wikidata", "Q3")])
    insert_qid_to_relations(db_path, [("Q1", 100), ("Q1", 101), ("Q2", 200)])

    assert relation_ids_for_wikidata_id(db_path, "Q1") == [100, 101]
    assert load_relations_by_ids(db_path, [101, 200]) == {
        101: {"id": 101},
        200: {"id": 200},
    }

    with sqlite3.connect(db_path) as connection:
        chronology_edges = connection.execute(
            "SELECT chronology_relation_id, member_relation_id FROM chronology_edges"
        ).fetchall()
        qid_edges = connection.execute(
            "SELECT source_relation_id, edge_kind, target_wikidata_id FROM qid_edges"
        ).fetchall()

    assert chronology_edges == [(100, 101)]
    assert qid_edges == [(101, "successor_wikidata", "Q3")]


def test_index_matches_source_validates_schema_and_fingerprint(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-index.sqlite3"
    initialize_index_schema(db_path)
    write_completed_metadata(
        db_path,
        source_path=Path("output/ohm_borders/global-2026-04-14/raw/overpass.json"),
        source_fingerprint_sha256="abc123",
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
        fuzzy_matcher_name="rapidfuzz",
        fuzzy_matcher_version="3.9.1",
        fuzzy_threshold=0.85,
    )

    assert index_matches_source(db_path, source_fingerprint_sha256="abc123") is True
    assert index_matches_source(db_path, source_fingerprint_sha256="different") is False

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE index_metadata SET schema_version = ?", (SCHEMA_VERSION + 1,))
        connection.commit()

    assert index_matches_source(db_path, source_fingerprint_sha256="abc123") is False


def test_open_index_readonly_returns_read_only_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-index.sqlite3"
    initialize_index_schema(db_path)

    with open_index_readonly(db_path) as connection:
        table_count = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        assert table_count >= 5

        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
            connection.execute("CREATE TABLE forbidden (id INTEGER)")