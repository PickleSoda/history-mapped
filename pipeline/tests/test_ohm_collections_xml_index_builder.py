import inspect
import json
import os
import sqlite3
from pathlib import Path

import pytest

import pipeline.ohm_collections.xml_index_builder as builder_module
from pipeline.ohm_collections.xml_index_builder import build_index
from pipeline.ohm_collections.xml_index_store import (
    SCHEMA_VERSION,
    initialize_index_schema,
    insert_object_aliases,
    insert_objects,
    insert_relation_members,
    insert_way_node_refs,
    read_index_metadata,
)


def _fixture_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="pytest">
  <node id="100" lat="29.871" lon="31.205">
    <tag k="name" v="Ancient Memphis" />
    <tag k="name:en" v="Ancient Memphis" />
    <tag k="alt_name" v="Ineb-Hedj" />
    <tag k="wikidata" v="Q123" />
    <tag k="historic" v="city" />
  </node>
  <node id="101" lat="29.872" lon="31.206" />
  <node id="102" lat="29.873" lon="31.207" />
  <way id="200">
    <nd ref="100" />
    <nd ref="101" />
    <nd ref="102" />
    <tag k="name" v="Temple District" />
    <tag k="official_name" v="Temple District of Memphis" />
    <tag k="wikidata" v="Q200" />
  </way>
  <relation id="300">
    <member type="way" ref="200" role="outer" />
    <member type="node" ref="100" role="label" />
    <tag k="name" v="Kingdom of Egypt" />
    <tag k="short_name" v="Egypt" />
    <tag k="wikidata" v="Q456" />
    <tag k="type" v="boundary" />
  </relation>
</osm>
"""


def _updated_fixture_xml() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="pytest">
    <node id="100" lat="29.871" lon="31.205">
        <tag k="name" v="Ancient Memphis Rebuilt" />
        <tag k="name:en" v="Memphis Restored" />
        <tag k="alt_name" v="White Walls" />
        <tag k="wikidata" v="Q999" />
        <tag k="historic" v="city" />
    </node>
    <node id="103" lat="29.874" lon="31.208" />
    <node id="104" lat="29.875" lon="31.209" />
    <way id="200">
        <nd ref="103" />
        <nd ref="104" />
        <tag k="name" v="Sacred Precinct" />
        <tag k="official_name" v="Sacred Precinct of Memphis" />
        <tag k="wikidata" v="Q201" />
    </way>
    <relation id="300">
        <member type="way" ref="200" role="boundary" />
        <member type="node" ref="103" role="label" />
        <member type="node" ref="104" role="admin_centre" />
        <tag k="name" v="Kingdom of Kemet" />
        <tag k="short_name" v="Kemet" />
        <tag k="wikidata" v="Q789" />
        <tag k="type" v="boundary" />
    </relation>
</osm>
"""


def _fixture_with_skipped_elements() -> str:
    return """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="pytest">
  <node id="100" lat="29.871" lon="31.205">
    <tag k="name" v="Valid Memphis" />
  </node>
  <node lat="29.872" lon="31.206">
    <tag k="name" v="Missing Node Id" />
  </node>
  <relation id="300">
    <member type="way" role="outer" />
    <tag k="name" v="Broken Relation" />
  </relation>
</osm>
"""


def _write_fixture(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _read_index_contents(index_path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(index_path) as connection:
        objects = connection.execute(
            "SELECT object_type, object_id, name, normalized_name, wikidata_id, point_lat, point_lon "
            "FROM objects ORDER BY object_type, object_id"
        ).fetchall()
        object_aliases = connection.execute(
            "SELECT object_type, object_id, alias_key, alias_value, normalized_alias "
            "FROM object_aliases ORDER BY object_type, object_id, alias_key"
        ).fetchall()
        way_node_refs = connection.execute(
            "SELECT way_id, sequence_index, node_id FROM way_node_refs ORDER BY way_id, sequence_index, node_id"
        ).fetchall()
        relation_members = connection.execute(
            "SELECT relation_id, sequence_index, member_type, member_ref, member_role "
            "FROM relation_members ORDER BY relation_id, sequence_index, member_type, member_ref, member_role"
        ).fetchall()

    return {
        "objects": objects,
        "object_aliases": object_aliases,
        "way_node_refs": way_node_refs,
        "relation_members": relation_members,
    }


def _expected_fixture_index_contents() -> dict[str, list[tuple]]:
    return {
        "objects": [
            ("node", 100, "Ancient Memphis", "ancient memphis", "Q123", 29.871, 31.205),
            ("node", 101, None, None, None, 29.872, 31.206),
            ("node", 102, None, None, None, 29.873, 31.207),
            ("relation", 300, "Kingdom of Egypt", "kingdom of egypt", "Q456", None, None),
            ("way", 200, "Temple District", "temple district", "Q200", None, None),
        ],
        "object_aliases": [
            ("node", 100, "alt_name", "Ineb-Hedj", "ineb hedj"),
            ("node", 100, "name:en", "Ancient Memphis", "ancient memphis"),
            ("relation", 300, "short_name", "Egypt", "egypt"),
            ("way", 200, "official_name", "Temple District of Memphis", "temple district of memphis"),
        ],
        "way_node_refs": [(200, 0, 100), (200, 1, 101), (200, 2, 102)],
        "relation_members": [(300, 0, "way", 200, "outer"), (300, 1, "node", 100, "label")],
    }


def _expected_updated_fixture_index_contents() -> dict[str, list[tuple]]:
    return {
        "objects": [
            ("node", 100, "Ancient Memphis Rebuilt", "ancient memphis rebuilt", "Q999", 29.871, 31.205),
            ("node", 103, None, None, None, 29.874, 31.208),
            ("node", 104, None, None, None, 29.875, 31.209),
            ("relation", 300, "Kingdom of Kemet", "kingdom of kemet", "Q789", None, None),
            ("way", 200, "Sacred Precinct", "sacred precinct", "Q201", None, None),
        ],
        "object_aliases": [
            ("node", 100, "alt_name", "White Walls", "white walls"),
            ("node", 100, "name:en", "Memphis Restored", "memphis restored"),
            ("relation", 300, "short_name", "Kemet", "kemet"),
            ("way", 200, "official_name", "Sacred Precinct of Memphis", "sacred precinct of memphis"),
        ],
        "way_node_refs": [(200, 0, 103), (200, 1, 104)],
        "relation_members": [
            (300, 0, "way", 200, "boundary"),
            (300, 1, "node", 103, "label"),
            (300, 2, "node", 104, "admin_centre"),
        ],
    }


def _seed_interrupted_build_state(
    index_path: Path,
    source_path: Path,
    source_size_bytes: int,
    source_mtime_epoch: int,
) -> None:
    initialize_index_schema(index_path)

    with sqlite3.connect(index_path) as connection:
        connection.execute(
            "INSERT INTO index_metadata (schema_version, source_path, source_size_bytes, source_mtime_epoch, build_completed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                SCHEMA_VERSION,
                source_path.as_posix(),
                source_size_bytes,
                source_mtime_epoch,
                None,
            ),
        )
        connection.commit()

    insert_objects(
        index_path,
        [
            (
                "node",
                100,
                "Ancient Memphis Partial",
                "ancient memphis partial",
                "Q-STALE-NODE",
                json.dumps({"name": "Ancient Memphis Partial", "wikidata": "Q-STALE-NODE"}),
                10.0,
                20.0,
            ),
            (
                "node",
                999,
                "Crashed Node",
                "crashed node",
                None,
                json.dumps({"name": "Crashed Node"}),
                0.0,
                0.0,
            ),
            (
                "way",
                200,
                "Temple District Partial",
                "temple district partial",
                "Q-STALE-WAY",
                json.dumps({"name": "Temple District Partial", "wikidata": "Q-STALE-WAY"}),
                None,
                None,
            ),
            (
                "relation",
                300,
                "Kingdom of Egypt Partial",
                "kingdom of egypt partial",
                "Q-STALE-REL",
                json.dumps({"name": "Kingdom of Egypt Partial", "wikidata": "Q-STALE-REL"}),
                None,
                None,
            ),
        ],
    )
    insert_object_aliases(
        index_path,
        [
            ("node", 100, "alt_name", "Crash Alias", "crash alias"),
            ("node", 999, "name:en", "Ghost Row", "ghost row"),
            ("relation", 300, "short_name", "Partial Egypt", "partial egypt"),
            ("way", 200, "official_name", "Temple District Partial", "temple district partial"),
        ],
    )
    insert_way_node_refs(index_path, [(200, 0, 999), (200, 1, 1000)])
    insert_relation_members(
        index_path,
        [(300, 0, "way", 999, "outer"), (300, 1, "node", 999, "label")],
    )


def test_build_index_exposes_force_but_not_resume_at_the_builder_layer() -> None:
    parameters = inspect.signature(build_index).parameters

    assert "force" in parameters
    assert parameters["force"].default is False
    assert "resume" not in parameters


def test_build_index_streams_osm_xml_fixture_into_sqlite_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    _write_fixture(source_path, _fixture_xml())

    def fail_full_document_xml_load(*_args, **_kwargs):
        raise AssertionError("full-document XML helpers should not be used for streamed XML indexing")

    monkeypatch.setattr(builder_module.ET, "parse", fail_full_document_xml_load)
    monkeypatch.setattr(builder_module.ET, "fromstring", fail_full_document_xml_load)
    monkeypatch.setattr(builder_module.ET, "fromstringlist", fail_full_document_xml_load)
    monkeypatch.setattr(builder_module.ET, "XML", fail_full_document_xml_load)
    monkeypatch.setattr(builder_module.ET.ElementTree, "parse", fail_full_document_xml_load)

    result = build_index(source_path, index_path=index_path)

    assert result["status"] == "completed"

    metadata = read_index_metadata(index_path)
    assert metadata["source_path"] == source_path.as_posix()

    with sqlite3.connect(index_path) as connection:
        object_count = connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        stored_objects = connection.execute(
            "SELECT object_type, object_id, normalized_name, wikidata_id, point_lat, point_lon, raw_tags_json "
            "FROM objects WHERE object_id IN (100, 200, 300) ORDER BY object_type, object_id"
        ).fetchall()
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
        referenced_nodes = connection.execute(
            "SELECT object_id, point_lat, point_lon FROM objects "
            "WHERE object_type = 'node' AND object_id IN (101, 102) ORDER BY object_id"
        ).fetchall()

    assert object_count == 5
    assert [
        (
            object_type,
            object_id,
            normalized_name,
            wikidata_id,
            point_lat,
            point_lon,
            json.loads(raw_tags_json),
        )
        for object_type, object_id, normalized_name, wikidata_id, point_lat, point_lon, raw_tags_json in stored_objects
    ] == [
        (
            "node",
            100,
            "ancient memphis",
            "Q123",
            29.871,
            31.205,
            {
                "name": "Ancient Memphis",
                "name:en": "Ancient Memphis",
                "alt_name": "Ineb-Hedj",
                "wikidata": "Q123",
                "historic": "city",
            },
        ),
        (
            "relation",
            300,
            "kingdom of egypt",
            "Q456",
            None,
            None,
            {
                "name": "Kingdom of Egypt",
                "short_name": "Egypt",
                "wikidata": "Q456",
                "type": "boundary",
            },
        ),
        (
            "way",
            200,
            "temple district",
            "Q200",
            None,
            None,
            {
                "name": "Temple District",
                "official_name": "Temple District of Memphis",
                "wikidata": "Q200",
            },
        ),
    ]
    assert alias_rows == [
        ("node", 100, "alt_name", "Ineb-Hedj", "ineb hedj"),
        ("node", 100, "name:en", "Ancient Memphis", "ancient memphis"),
        ("relation", 300, "short_name", "Egypt", "egypt"),
        ("way", 200, "official_name", "Temple District of Memphis", "temple district of memphis"),
    ]
    assert way_refs == [(200, 0, 100), (200, 1, 101), (200, 2, 102)]
    assert relation_members == [(300, 0, "way", 200, "outer"), (300, 1, "node", 100, "label")]
    assert referenced_nodes == [(101, 29.872, 31.206), (102, 29.873, 31.207)]


def test_build_index_reuses_a_compatible_completed_index_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    _write_fixture(source_path, _fixture_xml())

    first_result = build_index(source_path, index_path=index_path)
    assert first_result["status"] == "completed"

    monkeypatch.setattr(
        builder_module.ET,
        "iterparse",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("iterparse should not run when resume skips a compatible index")
        ),
    )

    second_result = build_index(source_path, index_path=index_path)

    assert second_result["status"] == "skipped"


def test_build_index_rebuilds_a_matching_index_missing_completion_metadata(tmp_path: Path) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    _write_fixture(source_path, _fixture_xml())
    source_mtime_epoch = 1_716_200_000
    os.utime(source_path, (source_mtime_epoch, source_mtime_epoch))

    source_size_bytes = source_path.stat().st_size

    _seed_interrupted_build_state(
        index_path,
        source_path=source_path,
        source_size_bytes=source_size_bytes,
        source_mtime_epoch=source_mtime_epoch,
    )

    result = build_index(source_path, index_path=index_path)
    metadata = read_index_metadata(index_path)
    rebuilt_contents = _read_index_contents(index_path)

    assert result["status"] == "completed"
    assert rebuilt_contents == _expected_fixture_index_contents()
    assert metadata["source_path"] == source_path.as_posix()
    assert metadata["build_completed_at"]


def test_build_index_requires_force_to_rebuild_on_source_change_and_replaces_stale_rows(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    _write_fixture(source_path, _fixture_xml())

    first_result = build_index(source_path, index_path=index_path)
    assert first_result["status"] == "completed"
    first_metadata = read_index_metadata(index_path)

    _write_fixture(source_path, _updated_fixture_xml())

    with pytest.raises(RuntimeError, match="force"):
        build_index(source_path, index_path=index_path)

    second_result = build_index(source_path, index_path=index_path, force=True)
    second_metadata = read_index_metadata(index_path)
    rebuilt_contents = _read_index_contents(index_path)

    with sqlite3.connect(index_path) as connection:
        stale_old_nodes = connection.execute(
            "SELECT COUNT(*) FROM objects WHERE object_type = 'node' AND object_id IN (101, 102)"
        ).fetchone()[0]

    assert second_result["status"] == "completed"
    assert second_metadata["source_size_bytes"] == source_path.stat().st_size
    assert second_metadata["source_mtime_epoch"] >= first_metadata["source_mtime_epoch"]
    assert second_metadata["build_completed_at"] != first_metadata["build_completed_at"]
    assert rebuilt_contents == _expected_updated_fixture_index_contents()
    assert stale_old_nodes == 0


def test_build_index_force_replace_failure_preserves_existing_index_and_cleans_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    _write_fixture(source_path, _fixture_xml())

    build_index(source_path, index_path=index_path)
    original_metadata = read_index_metadata(index_path)
    original_contents = _read_index_contents(index_path)

    updated_xml = _fixture_xml().replace("Kingdom of Egypt", "Kingdom of Egypt Updated")
    _write_fixture(source_path, updated_xml)

    temp_paths: list[Path] = []

    def fake_replace(source: str | Path, destination: str | Path) -> None:
        del destination
        temp_paths.append(Path(source))
        raise OSError("replace failed")

    monkeypatch.setattr(builder_module.os, "replace", fake_replace)

    with pytest.raises(RuntimeError, match="replace"):
        build_index(source_path, index_path=index_path, force=True)

    assert read_index_metadata(index_path) == original_metadata
    assert _read_index_contents(index_path) == original_contents
    assert temp_paths
    assert all(not temp_path.exists() for temp_path in temp_paths)


def test_build_index_records_skipped_element_diagnostics_without_aborting_the_run(tmp_path: Path) -> None:
    source_path = tmp_path / "map.xml"
    index_path = tmp_path / "map.sqlite3"
    diagnostics_path = index_path.with_suffix(index_path.suffix + ".skipped.jsonl")
    _write_fixture(source_path, _fixture_with_skipped_elements())

    result = build_index(source_path, index_path=index_path)

    assert result["status"] == "completed"
    assert result["skipped_elements"] == 2
    assert result["diagnostics_path"] == diagnostics_path.as_posix()

    with sqlite3.connect(index_path) as connection:
        object_count = connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0]

    diagnostics = [json.loads(line) for line in diagnostics_path.read_text(encoding="utf-8").splitlines()]

    assert object_count == 1
    assert [
        (record["element_tag"], record["element_id"], record["reason_code"])
        for record in diagnostics
    ] == [
        ("node", None, "missing_id"),
        ("relation", 300, "missing_member_ref"),
    ]
    assert all(isinstance(record["reason"], str) and record["reason"] for record in diagnostics)