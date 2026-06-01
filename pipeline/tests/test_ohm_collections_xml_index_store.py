import json
import sqlite3
from pathlib import Path

from pipeline.ohm_collections.xml_index_store import (
    SCHEMA_VERSION,
    index_matches_source,
    initialize_index_schema,
    insert_object_aliases,
    insert_objects,
    insert_relation_members,
    insert_way_node_refs,
    read_index_metadata,
    write_completed_metadata,
)


def _table_columns(db_path: Path, table_name: str) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()

    return [str(row[1]) for row in rows]


def test_initialize_index_schema_creates_expected_tables_and_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"

    initialize_index_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

    assert {
        "index_metadata",
        "objects",
        "object_aliases",
        "way_node_refs",
        "relation_members",
    }.issubset(tables)
    assert _table_columns(db_path, "index_metadata") == [
        "schema_version",
        "source_path",
        "source_size_bytes",
        "source_mtime_epoch",
        "build_completed_at",
    ]
    assert _table_columns(db_path, "objects") == [
        "object_type",
        "object_id",
        "name",
        "normalized_name",
        "wikidata_id",
        "raw_tags_json",
        "point_lat",
        "point_lon",
    ]
    assert _table_columns(db_path, "object_aliases") == [
        "object_type",
        "object_id",
        "alias_key",
        "alias_value",
        "normalized_alias",
    ]
    assert _table_columns(db_path, "way_node_refs") == ["way_id", "sequence_index", "node_id"]
    assert _table_columns(db_path, "relation_members") == [
        "relation_id",
        "sequence_index",
        "member_type",
        "member_ref",
        "member_role",
    ]


def test_write_completed_metadata_persists_a_single_metadata_row(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    initialize_index_schema(db_path)

    write_completed_metadata(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
    )
    write_completed_metadata(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=8192,
        source_mtime_epoch=1716201234,
    )

    metadata = read_index_metadata(db_path)

    with sqlite3.connect(db_path) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM index_metadata").fetchone()[0]

    assert row_count == 1
    assert metadata == {
        "schema_version": SCHEMA_VERSION,
        "source_path": "output/map.xml",
        "source_size_bytes": 8192,
        "source_mtime_epoch": 1716201234,
        "build_completed_at": metadata["build_completed_at"],
    }
    assert isinstance(metadata["build_completed_at"], str)


def test_insert_helpers_persist_objects_aliases_and_member_references(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    initialize_index_schema(db_path)

    insert_objects(
        db_path,
        [
            (
                "node",
                100,
                "Ancient Memphis",
                "ancient memphis",
                "Q123",
                json.dumps({"name": "Ancient Memphis", "wikidata": "Q123"}),
                29.871,
                31.205,
            ),
            (
                "way",
                200,
                "Temple District",
                "temple district",
                None,
                json.dumps({"name": "Temple District"}),
                None,
                None,
            ),
            (
                "relation",
                300,
                "Kingdom of Egypt",
                "kingdom of egypt",
                "Q456",
                json.dumps({"name": "Kingdom of Egypt", "wikidata": "Q456"}),
                None,
                None,
            ),
        ],
    )
    insert_object_aliases(
        db_path,
        [
            ("node", 100, "alt_name", "Ineb-Hedj", "ineb hedj"),
            ("node", 100, "name:en", "Ancient Memphis", "ancient memphis"),
            (
                "relation",
                300,
                "short_name",
                "Egypt",
                "egypt",
            ),
        ],
    )
    insert_way_node_refs(db_path, [(200, 0, 100), (200, 1, 101), (200, 2, 102)])
    insert_relation_members(
        db_path,
        [(300, 0, "way", 200, "outer"), (300, 1, "node", 100, "label")],
    )

    with sqlite3.connect(db_path) as connection:
        object_rows = connection.execute(
            "SELECT object_type, object_id, normalized_name, wikidata_id, point_lat, point_lon "
            "FROM objects ORDER BY object_type, object_id"
        ).fetchall()
        relation_payload = connection.execute(
            "SELECT raw_tags_json FROM objects WHERE object_type = 'relation' AND object_id = 300"
        ).fetchone()[0]
        alias_rows = connection.execute(
            "SELECT object_type, object_id, alias_key, alias_value, normalized_alias "
            "FROM object_aliases ORDER BY object_type, object_id, alias_key"
        ).fetchall()
        way_refs = connection.execute(
            "SELECT way_id, sequence_index, node_id FROM way_node_refs ORDER BY sequence_index"
        ).fetchall()
        relation_members = connection.execute(
            "SELECT relation_id, sequence_index, member_type, member_ref, member_role "
            "FROM relation_members ORDER BY sequence_index"
        ).fetchall()

    assert object_rows == [
        ("node", 100, "ancient memphis", "Q123", 29.871, 31.205),
        ("relation", 300, "kingdom of egypt", "Q456", None, None),
        ("way", 200, "temple district", None, None, None),
    ]
    assert json.loads(relation_payload) == {"name": "Kingdom of Egypt", "wikidata": "Q456"}
    assert alias_rows == [
        ("node", 100, "alt_name", "Ineb-Hedj", "ineb hedj"),
        ("node", 100, "name:en", "Ancient Memphis", "ancient memphis"),
        ("relation", 300, "short_name", "Egypt", "egypt"),
    ]
    assert way_refs == [(200, 0, 100), (200, 1, 101), (200, 2, 102)]
    assert relation_members == [(300, 0, "way", 200, "outer"), (300, 1, "node", 100, "label")]


def test_index_matches_source_requires_matching_schema_path_size_and_mtime(tmp_path: Path) -> None:
    db_path = tmp_path / "ohm-xml-index.sqlite3"
    initialize_index_schema(db_path)
    write_completed_metadata(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
    )

    assert index_matches_source(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
    ) is True
    assert index_matches_source(
        db_path,
        source_path=Path("output/other-map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
    ) is False
    assert index_matches_source(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=9999,
        source_mtime_epoch=1716200000,
    ) is False
    assert index_matches_source(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716209999,
    ) is False

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE index_metadata SET schema_version = ?", (SCHEMA_VERSION + 1,))
        connection.commit()

    assert index_matches_source(
        db_path,
        source_path=Path("output/map.xml"),
        source_size_bytes=4096,
        source_mtime_epoch=1716200000,
    ) is False