import json
import logging

from click.testing import CliRunner

import pipeline.ohm_links.__main__ as ohm_links_main
from pipeline.ohm_links.fetcher import BOUNDARIES_QUERY, PLACES_WITH_WIKIDATA_QUERY
from pipeline.ohm_links.writer import read_jsonl, write_manifest, write_part, write_records

IDS_QUERY_WAY_3 = "[out:json][timeout:600];(way(id:3););out tags;"


def _record(osm_type, osm_id, name):
    return {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "wikidata_id": None,
        "name": name,
        "name_en": None,
        "admin_level": None,
        "place": None,
        "start_date": None,
        "end_date": None,
        "tags": {"name": name},
    }


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_write_records_writes_jsonl_and_keeps_first_duplicate(tmp_path):
    path = tmp_path / "run" / "ohm_links.jsonl"
    records = [
        _record("relation", 1880, "Imperium Romanum"),
        _record("node", 1880, "Same id, other type"),
        _record("relation", 1880, "Later duplicate"),
        _record("node", 42, "Roma"),
    ]

    counts = write_records(records, path)

    assert counts == {"records": 3, "duplicates": 1}
    assert [(r["osm_type"], r["osm_id"], r["name"]) for r in _read_jsonl(path)] == [
        ("relation", 1880, "Imperium Romanum"),
        ("node", 1880, "Same id, other type"),
        ("node", 42, "Roma"),
    ]
    assert [p.name for p in path.parent.iterdir()] == ["ohm_links.jsonl"]


def test_write_records_keeps_non_ascii_text_readable(tmp_path):
    path = tmp_path / "ohm_links.jsonl"

    write_records([_record("relation", 1, "Römisches Reich")], path)

    assert "Römisches Reich" in path.read_text(encoding="utf-8")


def test_write_part_round_trips_through_read_jsonl_and_replaces_atomically(tmp_path):
    path = tmp_path / "boundaries.jsonl"
    path.write_text("stale\n", encoding="utf-8")
    records = [_record("relation", 1, "A"), _record("relation", 2, "B")]

    assert write_part(records, path) == 2

    assert list(read_jsonl(path)) == records
    assert [p.name for p in tmp_path.iterdir()] == ["boundaries.jsonl"]


def test_write_manifest_records_run_id_and_counts(tmp_path):
    path = tmp_path / "manifest.json"

    write_manifest(path, "20261031-1200", {"records": 3, "duplicates": 1})

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "20261031-1200"
    assert manifest["counts"] == {"records": 3, "duplicates": 1}
    assert manifest["generated_at"]


def _stub_fetch(monkeypatch, responses):
    queries = []

    def stub_fetch_elements(query):
        queries.append(query)
        return responses[query]

    monkeypatch.setattr(ohm_links_main, "fetch_elements", stub_fetch_elements)
    return queries


def test_fetch_command_writes_part_files_merged_file_and_manifest(tmp_path, monkeypatch, caplog):
    responses = {
        BOUNDARIES_QUERY: [
            {"type": "relation", "id": 1880, "tags": {"boundary": "administrative", "wikidata": "Q2277"}},
            {"type": "relation", "id": 9, "tags": {"boundary": "administrative", "place": "country"}},
        ],
        PLACES_WITH_WIKIDATA_QUERY: [
            {"type": "relation", "id": 9, "tags": {"boundary": "administrative", "place": "country"}},
            {"type": "node", "id": 42, "tags": {"place": "city", "wikidata": "Q220"}},
        ],
        IDS_QUERY_WAY_3: [
            {"type": "way", "id": 3, "tags": {"name": "Wall"}},
            {"type": "way", "id": 4},
        ],
    }
    queries = _stub_fetch(monkeypatch, responses)
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("way/3\n", encoding="utf-8")
    out_dir = tmp_path / "ohm_links"
    caplog.set_level(logging.INFO, logger="pipeline.ohm_links")

    result = CliRunner().invoke(
        ohm_links_main.cli,
        ["fetch", "--run-id", "test-run", "--out-dir", str(out_dir), "--ids-file", str(ids_file)],
    )

    assert result.exit_code == 0, result.output
    assert queries == list(responses)
    run_dir = out_dir / "test-run"
    assert sorted(p.name for p in run_dir.iterdir()) == [
        "boundaries.jsonl",
        "ids.jsonl",
        "manifest.json",
        "ohm_links.jsonl",
        "places.jsonl",
    ]
    assert [(r["osm_type"], r["osm_id"]) for r in _read_jsonl(run_dir / "places.jsonl")] == [
        ("relation", 9),
        ("node", 42),
    ]
    assert [(r["osm_type"], r["osm_id"]) for r in _read_jsonl(run_dir / "ohm_links.jsonl")] == [
        ("relation", 1880),
        ("relation", 9),
        ("node", 42),
        ("way", 3),
    ]
    counts = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["counts"]
    assert counts["elements"] == 6
    assert counts["skipped"] == 1
    assert counts["records"] == 4
    assert counts["duplicates"] == 1
    assert "batch 1/1 (1 ids)" in caplog.text


def test_fetch_command_resume_keeps_existing_part_and_skips_its_query(tmp_path, monkeypatch):
    run_dir = tmp_path / "resumed"
    write_part([_record("relation", 1880, "Imperium Romanum")], run_dir / "boundaries.jsonl")
    responses = {
        PLACES_WITH_WIKIDATA_QUERY: [{"type": "node", "id": 42, "tags": {"place": "city", "wikidata": "Q220"}}],
    }
    queries = _stub_fetch(monkeypatch, responses)

    result = CliRunner().invoke(
        ohm_links_main.cli,
        ["fetch", "--run-id", "resumed", "--out-dir", str(tmp_path), "--resume"],
    )

    assert result.exit_code == 0, result.output
    assert queries == [PLACES_WITH_WIKIDATA_QUERY]
    assert [(r["osm_type"], r["osm_id"]) for r in _read_jsonl(run_dir / "ohm_links.jsonl")] == [
        ("relation", 1880),
        ("node", 42),
    ]


def test_fetch_command_without_resume_refetches_existing_part(tmp_path, monkeypatch):
    run_dir = tmp_path / "rerun"
    write_part([_record("relation", 1, "Stale")], run_dir / "places.jsonl")
    queries = _stub_fetch(monkeypatch, {PLACES_WITH_WIKIDATA_QUERY: []})

    result = CliRunner().invoke(
        ohm_links_main.cli,
        ["fetch", "--run-id", "rerun", "--out-dir", str(tmp_path), "--skip-boundaries"],
    )

    assert result.exit_code == 0, result.output
    assert queries == [PLACES_WITH_WIKIDATA_QUERY]
    assert _read_jsonl(run_dir / "ohm_links.jsonl") == []


def test_fetch_command_refuses_to_run_with_nothing_selected(tmp_path, monkeypatch):
    monkeypatch.setattr(ohm_links_main, "fetch_elements", lambda query: [])

    result = CliRunner().invoke(
        ohm_links_main.cli,
        ["fetch", "--out-dir", str(tmp_path), "--skip-boundaries", "--skip-places"],
    )

    assert result.exit_code != 0
    assert not any(tmp_path.iterdir())
