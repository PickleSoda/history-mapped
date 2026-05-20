import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

import pipeline.ohm_borders.index_builder as builder_module
from pipeline.ohm_borders.index_builder import build_index
from pipeline.ohm_borders.index_store import read_index_metadata


def _fixture_overpass() -> dict:
    return {
        "version": 0.6,
        "elements": [
            {
                "type": "relation",
                "id": 100,
                "tags": {
                    "type": "chronology",
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Empire",
                    "wikidata": "Q1",
                },
                "members": [
                    {"type": "relation", "ref": 101, "role": ""},
                    {"type": "relation", "ref": 102, "role": ""},
                ],
            },
            {
                "type": "relation",
                "id": 101,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Empire at peak",
                    "wikidata": "Q1",
                    "predecessor:wikidata": "Q2",
                    "successor:wikidata": "Q3",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 102,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Late Roman Empire",
                    "wikidata": "Q1",
                    "start_event:wikidata": "Q9",
                },
                "members": [],
            },
            {
                "type": "relation",
                "id": 200,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "name": "Roman Republic",
                    "wikidata": "Q2",
                    "successor:wikidata": "Q1",
                },
                "members": [],
            },
        ],
    }


def _write_fixture(path: Path, *, encoding: str = "utf-8") -> None:
    path.write_text(json.dumps(_fixture_overpass()), encoding=encoding)


def test_build_index_streams_fixture_into_sqlite_tables(tmp_path: Path) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path)

    result = build_index(source_path, index_path=index_path)

    assert result["status"] == "completed"
    metadata = read_index_metadata(index_path)
    assert metadata["source_path"] == source_path.as_posix()

    with sqlite3.connect(index_path) as connection:
        relation_count = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        chronology_edge_count = connection.execute("SELECT COUNT(*) FROM chronology_edges").fetchone()[0]
        qid_edge_count = connection.execute("SELECT COUNT(*) FROM qid_edges").fetchone()[0]

    assert relation_count == 4
    assert chronology_edge_count == 2
    assert qid_edge_count == 4


def test_build_index_reuses_identical_content_and_rejects_different_content_without_force(tmp_path: Path) -> None:
    first_source = tmp_path / "first.json"
    second_source = tmp_path / "second.json"
    third_source = tmp_path / "third.json"
    index_path = tmp_path / "overpass.sqlite3"

    _write_fixture(first_source)
    _write_fixture(second_source)
    altered = _fixture_overpass()
    altered["elements"][0]["tags"]["name"] = "Changed Empire"
    third_source.write_text(json.dumps(altered), encoding="utf-8")

    first_result = build_index(first_source, index_path=index_path)
    second_result = build_index(second_source, index_path=index_path)

    assert first_result["status"] == "completed"
    assert second_result["status"] == "skipped"

    with pytest.raises(RuntimeError, match="--force"):
        build_index(third_source, index_path=index_path)


def test_build_index_accepts_bom_prefixed_input_and_cleans_up_temp_file_on_replace_failure(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "overpass-bom.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path, encoding="utf-8-sig")

    assert build_index(source_path, index_path=index_path)["status"] == "completed"

    broken_source = tmp_path / "overpass-again.json"
    _write_fixture(broken_source)

    temp_paths: list[Path] = []
    real_replace = builder_module.os.replace

    def fake_replace(source: str | Path, destination: str | Path) -> None:
        temp_paths.append(Path(source))
        raise OSError("replace failed")

    monkeypatch.setattr(builder_module.os, "replace", fake_replace)

    with pytest.raises(RuntimeError, match="replace"):
        build_index(broken_source, index_path=index_path, force=True)

    assert temp_paths
    assert all(not temp_path.exists() for temp_path in temp_paths)
    monkeypatch.setattr(builder_module.os, "replace", real_replace)


def test_build_index_force_replace_failure_preserves_existing_completed_index(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path)
    build_index(source_path, index_path=index_path)
    original_metadata = read_index_metadata(index_path)

    changed_payload = _fixture_overpass()
    changed_payload["elements"][0]["tags"]["name"] = "Changed Roman Empire"
    source_path.write_text(json.dumps(changed_payload), encoding="utf-8")

    def fake_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(builder_module.os, "replace", fake_replace)

    with pytest.raises(RuntimeError, match="retry"):
        build_index(source_path, index_path=index_path, force=True)

    assert read_index_metadata(index_path) == original_metadata


def test_build_index_uses_streaming_parser_without_full_json_fallback(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path)

    parser_calls: list[str] = []
    standard_json = __import__("json")

    class _FakeIjson:
        @staticmethod
        def items(handle, prefix):
            parser_calls.append(prefix)
            payload = standard_json.JSONDecoder().decode(handle.read().decode("utf-8"))
            for relation in payload["elements"]:
                yield relation

    monkeypatch.setattr(builder_module, "ijson", _FakeIjson())
    monkeypatch.setattr(
        builder_module.json,
        "loads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("fallback json.loads should not be used")),
    )

    result = build_index(source_path, index_path=index_path)

    assert result["status"] == "completed"
    assert parser_calls == ["elements.item"]


def test_build_index_accepts_decimal_values_from_streaming_parser(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path)

    payload = _fixture_overpass()
    payload["elements"][0]["bounds"] = {
        "minlat": Decimal("40.100"),
        "minlon": Decimal("20.200"),
        "maxlat": Decimal("41.300"),
        "maxlon": Decimal("21.400"),
    }

    class _FakeIjson:
        @staticmethod
        def items(handle, prefix):
            del handle, prefix
            for relation in payload["elements"]:
                yield relation

    monkeypatch.setattr(builder_module, "ijson", _FakeIjson())

    result = build_index(source_path, index_path=index_path)

    assert result["status"] == "completed"
    with sqlite3.connect(index_path) as connection:
        stored_payload = connection.execute(
            "SELECT payload_json FROM relations WHERE relation_id = 100"
        ).fetchone()[0]

    assert json.loads(stored_payload)["bounds"] == {
        "minlat": 40.1,
        "minlon": 20.2,
        "maxlat": 41.3,
        "maxlon": 21.4,
    }


def test_build_index_cleanup_does_not_mask_original_failure_when_temp_remove_fails(tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    _write_fixture(source_path)

    monkeypatch.setattr(
        builder_module,
        "_write_relation_records",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("decimal explode")),
    )

    original_unlink = Path.unlink

    def fake_unlink(self: Path, missing_ok: bool = False):
        if self == index_path.with_name(f"{index_path.name}.tmp.{builder_module.os.getpid()}"):
            raise PermissionError("temp file still locked")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    with pytest.raises(RuntimeError, match="decimal explode"):
        build_index(source_path, index_path=index_path)