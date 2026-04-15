import json
from pathlib import Path
import time

from click.testing import CliRunner
import orjson

import pipeline.__main__ as main_module
from pipeline.__main__ import cli
from pipeline.ohm_borders.artifacts import (
    built_shard_path,
    enriched_shard_path,
    final_jsonl_path,
    parsed_shard_path,
    raw_shard_path,
    stage_done_marker_path,
    raw_overpass_path,
)
from pipeline.ohm_borders.stages import (
    run_build_stage,
    run_enrich_stage,
    run_fetch_stage,
    run_parse_stage,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for record in records:
            handle.write(orjson.dumps(record) + b"\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_fetch_stage_writes_raw_overpass_and_manifest_summary(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    def fake_fetch_raw(query: str) -> dict:
        assert query == "[out:json];relation(1);out geom;"
        return {
            "elements": [
                {"type": "relation", "id": 2, "tags": {"name": "Second"}},
                {"type": "relation", "id": 1, "tags": {"name": "First"}},
                {"type": "way", "id": 999},
            ]
        }

    result = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="[out:json];relation(1);out geom;",
        raw_shard_size=1,
        fetcher=fake_fetch_raw,
    )

    raw_path = raw_overpass_path(artifact_dir)
    shard_one = raw_shard_path(artifact_dir, 1)
    shard_two = raw_shard_path(artifact_dir, 2)
    done_marker = stage_done_marker_path(artifact_dir, "fetch")
    manifest_path = artifact_dir / "manifest.json"

    assert result["status"] == "completed"
    assert json.loads(raw_path.read_text(encoding="utf-8")) == {
        "elements": [
            {"type": "relation", "id": 2, "tags": {"name": "Second"}},
            {"type": "relation", "id": 1, "tags": {"name": "First"}},
            {"type": "way", "id": 999},
        ]
    }
    assert [json.loads(line) for line in shard_one.read_text(encoding="utf-8").splitlines()] == [
        {"type": "relation", "id": 1, "tags": {"name": "First"}}
    ]
    assert [json.loads(line) for line in shard_two.read_text(encoding="utf-8").splitlines()] == [
        {"type": "relation", "id": 2, "tags": {"name": "Second"}}
    ]
    assert done_marker.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stages"]["fetch"]["status"] == "completed"
    assert manifest["stages"]["fetch"]["outputs"] == [
        "raw/overpass.json",
        "raw/raw-00001.jsonl",
        "raw/raw-00002.jsonl",
        ".done/fetch.done",
    ]
    assert manifest["summary"]["raw_elements"] == 3
    assert manifest["summary"]["raw_relation_elements"] == 2
    assert manifest["summary"]["raw_shards"] == 2
    assert manifest["summary"]["raw_shard_size"] == 1


def test_parse_stage_falls_back_to_overpass_when_raw_shards_absent(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    raw_path = raw_overpass_path(artifact_dir)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"elements": [{"id": 1}, {"id": 2}, {"id": 3}]}, separators=(",", ":")), encoding="utf-8")

    def fake_parse_elements(elements: list[dict]) -> list[dict]:
        assert elements == [{"id": 1}, {"id": 2}, {"id": 3}]
        return [
            {"relation_id": 101, "tags": {"name": "Alpha"}, "stages": []},
            {"relation_id": 102, "tags": {"name": "Beta"}, "stages": []},
            {"relation_id": 103, "tags": {"name": "Gamma"}, "stages": []},
        ]

    result = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=3,
        parser=fake_parse_elements,
    )

    shard_one = parsed_shard_path(artifact_dir, 1)
    shard_two = parsed_shard_path(artifact_dir, 2)
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert len(shard_one.read_text(encoding="utf-8").splitlines()) == 2
    assert len(shard_two.read_text(encoding="utf-8").splitlines()) == 1
    assert manifest["stages"]["parse"]["status"] == "completed"
    assert manifest["stages"]["parse"]["outputs"] == ["parsed/parsed-00001.jsonl", "parsed/parsed-00002.jsonl"]
    assert manifest["summary"]["parsed_source"] == "overpass"
    assert manifest["summary"]["parsed_polities"] == 3
    assert manifest["summary"]["parsed_shards"] == 2
    assert manifest["summary"]["parse_workers"] == 3


def test_parse_stage_prefers_raw_shards_and_writes_deterministic_outputs(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    raw_overpass_path(artifact_dir).parent.mkdir(parents=True, exist_ok=True)
    raw_overpass_path(artifact_dir).write_text(
        json.dumps({"elements": [{"id": 999}]}, separators=(",", ":")),
        encoding="utf-8",
    )

    _write_jsonl(
        raw_shard_path(artifact_dir, 1),
        [
            {"type": "relation", "id": 2, "tags": {"name": "Two"}, "members": []},
            {"type": "relation", "id": 1, "tags": {"name": "One"}, "members": []},
        ],
    )
    _write_jsonl(
        raw_shard_path(artifact_dir, 2),
        [
            {"type": "relation", "id": 4, "tags": {"name": "Four"}, "members": []},
            {"type": "relation", "id": 3, "tags": {"name": "Three"}, "members": []},
        ],
    )

    parse_calls: list[list[int]] = []

    def fake_parse_elements(elements: list[dict]) -> list[dict]:
        relation_ids = [int(element["id"]) for element in elements]
        parse_calls.append(relation_ids)

        # Return intentionally reversed records so the stage must stabilize order.
        return [
            {"relation_id": relation_id, "tags": {"name": str(relation_id)}, "stages": []}
            for relation_id in sorted(relation_ids, reverse=True)
        ]

    first = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        parser=fake_parse_elements,
    )

    first_contents = [
        _read_jsonl(parsed_shard_path(artifact_dir, 1)),
        _read_jsonl(parsed_shard_path(artifact_dir, 2)),
    ]

    second = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        force=True,
        parser=fake_parse_elements,
    )

    second_contents = [
        _read_jsonl(parsed_shard_path(artifact_dir, 1)),
        _read_jsonl(parsed_shard_path(artifact_dir, 2)),
    ]
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert len(parse_calls) == 4
    assert sorted(parse_calls) == [[1, 2], [1, 2], [3, 4], [3, 4]]
    assert first_contents == second_contents
    assert [record["relation_id"] for record in first_contents[0]] == [1, 2]
    assert [record["relation_id"] for record in first_contents[1]] == [3, 4]
    assert manifest["summary"]["parsed_source"] == "raw_shards"
    assert manifest["summary"]["parsed_input_shards"] == 2
    assert manifest["summary"]["parsed_input_relations"] == 4
    assert manifest["summary"]["parse_input_shards_total"] == 2
    assert manifest["summary"]["parse_input_shards_completed"] == 2
    assert manifest["summary"]["parse_input_shards_active"] == 0


def test_parse_stage_resolves_chronology_members_across_raw_shards(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"

    _write_jsonl(
        raw_shard_path(artifact_dir, 1),
        [
            {
                "type": "relation",
                "id": 200,
                "tags": {
                    "type": "chronology",
                    "boundary": "administrative",
                    "name": "Evolving State",
                    "wikidata": "Q1000",
                },
                "members": [{"type": "relation", "ref": 201, "role": ""}],
            }
        ],
    )
    _write_jsonl(
        raw_shard_path(artifact_dir, 2),
        [
            {
                "type": "relation",
                "id": 201,
                "tags": {
                    "boundary": "administrative",
                    "admin_level": "2",
                    "start_date": "1800",
                    "end_date": "1850",
                },
                "members": [
                    {
                        "type": "way",
                        "ref": 10,
                        "role": "outer",
                        "geometry": [
                            {"lat": 0.0, "lon": 0.0},
                            {"lat": 2.0, "lon": 0.0},
                            {"lat": 2.0, "lon": 2.0},
                            {"lat": 0.0, "lon": 0.0},
                        ],
                    }
                ],
            },
            {
                "type": "relation",
                "id": 300,
                "tags": {"boundary": "administrative", "admin_level": "2", "name": "Standalone"},
                "members": [],
            },
        ],
    )

    result = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=10,
        parse_workers=2,
    )

    parsed_records = _read_jsonl(parsed_shard_path(artifact_dir, 1))
    chronology = next(record for record in parsed_records if record["relation_id"] == 200)

    assert result["status"] == "completed"
    assert [record["relation_id"] for record in parsed_records] == [200, 300]
    assert [stage["relation_id"] for stage in chronology["stages"]] == [201]


def test_fetch_stage_resume_skips_existing_raw_unless_forced(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    raw_path = raw_overpass_path(artifact_dir)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"elements": [{"id": "existing"}]}, separators=(",", ":")), encoding="utf-8")

    calls: list[str] = []

    def fake_fetch_raw(query: str) -> dict:
        calls.append(query)
        return {"elements": [{"type": "relation", "id": 321}]}

    skipped = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="query-1",
        raw_shard_size=1,
        resume=True,
        fetcher=fake_fetch_raw,
    )
    forced = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="query-2",
        raw_shard_size=1,
        resume=True,
        force=True,
        fetcher=fake_fetch_raw,
    )

    assert skipped["status"] == "skipped"
    assert forced["status"] == "completed"
    assert calls == ["query-2"]
    assert json.loads(raw_path.read_text(encoding="utf-8")) == {"elements": [{"type": "relation", "id": 321}]}
    assert raw_shard_path(artifact_dir, 1).exists()


def test_parse_stage_resume_skips_existing_completed_shards_unless_forced(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    raw_path = raw_overpass_path(artifact_dir)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"elements": [{"id": 1}, {"id": 2}, {"id": 3}]}, separators=(",", ":")), encoding="utf-8")

    first_shard = parsed_shard_path(artifact_dir, 1)
    second_shard = parsed_shard_path(artifact_dir, 2)
    first_shard.parent.mkdir(parents=True, exist_ok=True)
    first_shard.write_text("existing-one\n", encoding="utf-8")
    second_shard.write_text("existing-two\n", encoding="utf-8")

    def fake_parse_elements(_: list[dict]) -> list[dict]:
        return [
            {"relation_id": 101, "tags": {"name": "Alpha"}, "stages": []},
            {"relation_id": 102, "tags": {"name": "Beta"}, "stages": []},
            {"relation_id": 103, "tags": {"name": "Gamma"}, "stages": []},
        ]

    skipped = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        resume=True,
        parser=fake_parse_elements,
    )
    forced = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        resume=True,
        force=True,
        parser=fake_parse_elements,
    )

    assert skipped["status"] == "skipped"
    assert first_shard.read_text(encoding="utf-8") == '{"relation_id":101,"tags":{"name":"Alpha"},"stages":[]}\n{"relation_id":102,"tags":{"name":"Beta"},"stages":[]}\n'
    assert second_shard.read_text(encoding="utf-8") == '{"relation_id":103,"tags":{"name":"Gamma"},"stages":[]}\n'
    assert forced["status"] == "completed"


def test_parse_stage_resume_force_applies_per_output_shard_for_raw_source(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        raw_shard_path(artifact_dir, 1),
        [
            {"type": "relation", "id": 1, "tags": {"name": "One"}, "members": []},
            {"type": "relation", "id": 2, "tags": {"name": "Two"}, "members": []},
            {"type": "relation", "id": 3, "tags": {"name": "Three"}, "members": []},
        ],
    )

    existing_first = parsed_shard_path(artifact_dir, 1)
    existing_first.parent.mkdir(parents=True, exist_ok=True)
    existing_first.write_text("existing-first\n", encoding="utf-8")

    def fake_parse_elements(elements: list[dict]) -> list[dict]:
        return [
            {"relation_id": int(element["id"]), "tags": element.get("tags", {}), "stages": []}
            for element in elements
        ]

    resumed = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        resume=True,
        parser=fake_parse_elements,
    )

    assert resumed["status"] == "completed"
    assert existing_first.read_text(encoding="utf-8") == "existing-first\n"
    assert _read_jsonl(parsed_shard_path(artifact_dir, 2)) == [
        {"relation_id": 3, "tags": {"name": "Three"}, "stages": []}
    ]

    forced = run_parse_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        parsed_shard_size=2,
        parse_workers=2,
        resume=True,
        force=True,
        parser=fake_parse_elements,
    )
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert forced["status"] == "completed"
    assert _read_jsonl(parsed_shard_path(artifact_dir, 1)) == [
        {"relation_id": 1, "tags": {"name": "One"}, "stages": []},
        {"relation_id": 2, "tags": {"name": "Two"}, "stages": []},
    ]
    assert _read_jsonl(parsed_shard_path(artifact_dir, 2)) == [
        {"relation_id": 3, "tags": {"name": "Three"}, "stages": []}
    ]
    assert manifest["summary"]["parsed_shards_written"] == 2
    assert manifest["summary"]["parsed_shards_skipped"] == 0


def test_borders_fetch_cli_wires_run_id_artifact_dir_query_file_and_flags(tmp_path: Path, monkeypatch) -> None:
    query_file = tmp_path / "query.overpass"
    query_file.write_text("[out:json];relation(42);out geom;", encoding="utf-8")
    runner = CliRunner()
    observed: dict[str, object] = {}

    def fake_run_fetch_stage(**kwargs):
        observed.update(kwargs)
        return {"status": "completed", "artifact_dir": kwargs["artifact_dir"], "raw_path": "raw/overpass.json", "element_count": 1}

    monkeypatch.setattr(main_module, "run_fetch_stage", fake_run_fetch_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "fetch",
            "--run-id",
            "run-123",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--query-file",
            str(query_file),
            "--raw-shard-size",
            "13",
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-123"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["query"] == "[out:json];relation(42);out geom;"
    assert observed["raw_shard_size"] == 13
    assert observed["resume"] is True
    assert observed["force"] is True


def test_borders_parse_cli_uses_documented_defaults_and_wires_flags(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    observed: dict[str, object] = {}

    def fake_default_parallelism() -> int:
        return 7

    def fake_run_parse_stage(**kwargs):
        observed.update(kwargs)
        return {"status": "completed", "artifact_dir": kwargs["artifact_dir"], "shard_count": 2, "polity_count": 3}

    monkeypatch.setattr(main_module, "default_parallelism", fake_default_parallelism)
    monkeypatch.setattr(main_module, "run_parse_stage", fake_run_parse_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "parse",
            "--run-id",
            "run-456",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-456"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["parsed_shard_size"] == 100
    assert observed["parse_workers"] == 7
    assert observed["resume"] is True
    assert observed["force"] is True


def test_enrich_stage_batches_unique_qids_and_records_failed_shards(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        parsed_shard_path(artifact_dir, 1),
        [
            {"relation_id": 101, "tags": {"name": "Alpha", "wikidata": "Q2"}, "stages": []},
            {"relation_id": 102, "tags": {"name": "Beta", "wikidata": "Q1"}, "stages": []},
        ],
    )
    _write_jsonl(
        parsed_shard_path(artifact_dir, 2),
        [
            {"relation_id": 103, "tags": {"name": "Gamma", "wikidata": "Q2"}, "stages": []},
            {"relation_id": 104, "tags": {"name": "Delta", "wikidata": "Q3"}, "stages": []},
        ],
    )

    calls: list[tuple[str, ...]] = []

    def fake_enrich(qids: list[str], batch_size: int) -> dict[str, dict]:
        calls.append(tuple(qids))
        assert batch_size == 2
        if qids == ["Q3"]:
            raise RuntimeError("temporary sparql failure")
        return {qid: {"name_en": f"Name {qid}", "aliases_en": [], "description": f"Desc {qid}"} for qid in qids}

    result = run_enrich_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        enrich_batch_size=2,
        enrich_workers=2,
        enricher=fake_enrich,
    )

    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    first_enriched = enriched_shard_path(artifact_dir, 1)
    second_enriched = enriched_shard_path(artifact_dir, 2)

    assert result["status"] == "completed"
    assert calls == [("Q1", "Q2"), ("Q3",)]
    assert first_enriched.exists()
    assert not second_enriched.exists()
    assert json.loads(first_enriched.read_text(encoding="utf-8")) == {
        "Q1": {"name_en": "Name Q1", "aliases_en": [], "description": "Desc Q1"},
        "Q2": {"name_en": "Name Q2", "aliases_en": [], "description": "Desc Q2"},
    }
    assert manifest["stages"]["enrich"]["status"] == "completed"
    assert manifest["stages"]["enrich"]["failed_shards"] == ["enriched/enriched-qids-00002.json"]
    assert manifest["summary"]["enrich_unique_qids"] == 3
    assert manifest["summary"]["enrich_shards"] == 2


def test_build_stage_loads_enrichment_index_and_writes_deterministic_outputs(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        parsed_shard_path(artifact_dir, 1),
        [
            {
                "relation_id": 400,
                "tags": {"name": "Republic of Venice", "wikidata": "Q4948"},
                "stages": [
                    {
                        "relation_id": 401,
                        "tags": {"start_date": "1390", "end_date": "1363"},
                        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [2, 0], [2, 2], [0, 0]]]]},
                    },
                    {
                        "relation_id": 402,
                        "tags": {"start_date": "1391", "end_date": "1404"},
                        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [3, 0], [3, 3], [0, 0]]]]},
                    },
                ],
            }
        ],
    )
    _write_jsonl(
        parsed_shard_path(artifact_dir, 2),
        [
            {
                "relation_id": 100,
                "tags": {
                    "name": "Testland",
                    "name:en": "Testland (EN)",
                    "wikidata": "Q999",
                    "start_date": "1900",
                    "end_date": "1950",
                },
                "stages": [
                    {
                        "relation_id": 100,
                        "tags": {"start_date": "1900", "end_date": "1950"},
                        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]},
                    }
                ],
            }
        ],
    )

    enriched_shard_path(artifact_dir, 1).parent.mkdir(parents=True, exist_ok=True)
    enriched_shard_path(artifact_dir, 1).write_text(
        json.dumps(
            {
                "Q4948": {"name_en": "Republic of Venice", "description": "former state", "aliases_en": []},
                "Q999": {"name_en": "Testland", "description": "A test polity", "aliases_en": ["TL"]},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = run_build_stage(run_id="run-001", artifact_dir=artifact_dir)

    built_one = _read_jsonl(built_shard_path(artifact_dir, 1))
    built_two = _read_jsonl(built_shard_path(artifact_dir, 2))
    final_records = _read_jsonl(final_jsonl_path(artifact_dir))

    assert result["status"] == "completed"
    assert [record["_ohm_relation_id"] for record in final_records] == ["400", "100"]
    assert built_one[0]["name"] == "Republic of Venice"
    assert built_one[0]["_geometry_periods"] == [
        {
            "ohm_relation_id": "402",
            "external_type": "relation",
            "start_year": 1391,
            "end_year": 1404,
            "start_date": "1391",
            "end_date": "1404",
            "geojson": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [3, 0], [3, 3], [0, 0]]]]},
            "label": "Republic of Venice (1391-1404)",
            "external_tags": {"start_date": "1391", "end_date": "1404"},
        }
    ]
    assert built_two[0]["alternative_names"] == ["TL"]
    assert final_records == built_one + built_two


def test_build_stage_parallel_workers_still_produce_deterministic_order(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        parsed_shard_path(artifact_dir, 1),
        [{"relation_id": 1, "tags": {"name": "One"}, "stages": []}],
    )
    _write_jsonl(
        parsed_shard_path(artifact_dir, 2),
        [{"relation_id": 2, "tags": {"name": "Two"}, "stages": []}],
    )
    _write_jsonl(
        parsed_shard_path(artifact_dir, 3),
        [{"relation_id": 3, "tags": {"name": "Three"}, "stages": []}],
    )

    def delayed_mapper(record: dict, _: dict) -> dict:
        # Force out-of-order worker completion; final output must remain shard-ordered.
        delay = {1: 0.03, 2: 0.01, 3: 0.0}[int(record["relation_id"])]
        time.sleep(delay)
        return {
            "name": record["tags"]["name"],
            "_ohm_relation_id": str(record["relation_id"]),
        }

    first = run_build_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        build_workers=3,
        mapper=delayed_mapper,
    )
    first_records = _read_jsonl(final_jsonl_path(artifact_dir))

    second = run_build_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        build_workers=3,
        force=True,
        mapper=delayed_mapper,
    )
    second_records = _read_jsonl(final_jsonl_path(artifact_dir))
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert [record["_ohm_relation_id"] for record in first_records] == ["1", "2", "3"]
    assert first_records == second_records
    assert manifest["summary"]["built_shards_total"] == 3
    assert manifest["summary"]["built_shards_completed"] == 3
    assert manifest["summary"]["built_shards_active"] == 0
    assert manifest["summary"]["build_workers_used"] == 3


def test_build_stage_resume_only_rebuilds_missing_outputs(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        parsed_shard_path(artifact_dir, 1),
        [{"relation_id": 1, "tags": {"name": "Alpha"}, "stages": []}],
    )
    _write_jsonl(
        parsed_shard_path(artifact_dir, 2),
        [{"relation_id": 2, "tags": {"name": "Beta"}, "stages": []}],
    )

    existing_record = {"name": "Existing", "_ohm_relation_id": "1"}
    built_shard_path(artifact_dir, 1).parent.mkdir(parents=True, exist_ok=True)
    built_shard_path(artifact_dir, 1).write_text(json.dumps(existing_record) + "\n", encoding="utf-8")
    final_jsonl_path(artifact_dir).parent.mkdir(parents=True, exist_ok=True)
    final_jsonl_path(artifact_dir).write_text("stale\n", encoding="utf-8")

    result = run_build_stage(run_id="run-001", artifact_dir=artifact_dir, resume=True)
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    final_records = _read_jsonl(final_jsonl_path(artifact_dir))

    assert result["status"] == "completed"
    assert _read_jsonl(built_shard_path(artifact_dir, 1)) == [existing_record]
    assert final_records[0] == existing_record
    assert final_records[1]["name"] == "Beta"
    assert manifest["summary"]["built_shards_skipped"] == 1
    assert manifest["summary"]["built_shards_written"] == 1
    assert manifest["summary"]["built_shards_total"] == 2


def test_build_stage_no_enrich_succeeds_with_empty_index(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    _write_jsonl(
        parsed_shard_path(artifact_dir, 1),
        [
            {
                "relation_id": 100,
                "tags": {
                    "name": "Testland",
                    "name:en": "Testland (EN)",
                    "wikidata": "Q999",
                    "start_date": "1900",
                    "end_date": "1950",
                },
                "stages": [
                    {
                        "relation_id": 100,
                        "tags": {"start_date": "1900", "end_date": "1950"},
                        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]},
                    }
                ],
            }
        ],
    )

    result = run_build_stage(run_id="run-001", artifact_dir=artifact_dir)
    built_records = _read_jsonl(built_shard_path(artifact_dir, 1))

    assert result["status"] == "completed"
    assert built_records == [
        {
            "name": "Testland (EN)",
            "entity_type": "political_entity",
            "entity_group": "POLITY",
            "wikidata_id": "Q999",
            "alternative_names": [],
            "summary": None,
            "temporal_start": "1900",
            "temporal_end": "1950",
            "verification_status": "ohm_draft",
            "confidence": "medium",
            "location_method": "ohm_nominatim",
            "location_confidence": "high",
            "_ohm_relation_id": "100",
            "_geometry_periods": [
                {
                    "ohm_relation_id": "100",
                    "external_type": "relation",
                    "start_year": 1900,
                    "end_year": 1950,
                    "start_date": "1900",
                    "end_date": "1950",
                    "geojson": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]},
                    "label": "Testland (EN) (1900-1950)",
                    "external_tags": {"start_date": "1900", "end_date": "1950"},
                }
            ],
        }
    ]


def test_borders_enrich_cli_uses_documented_defaults_and_wires_flags(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    observed: dict[str, object] = {}

    def fake_run_enrich_stage(**kwargs):
        observed.update(kwargs)
        return {"status": "completed", "artifact_dir": kwargs["artifact_dir"], "qid_count": 3, "shard_count": 2}

    monkeypatch.setattr(main_module, "run_enrich_stage", fake_run_enrich_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "enrich",
            "--run-id",
            "run-789",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-789"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["enrich_batch_size"] == 50
    assert observed["enrich_workers"] == 4
    assert observed["resume"] is True
    assert observed["force"] is True


def test_borders_build_cli_wires_resume_force_and_no_enrich(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    observed: dict[str, object] = {}

    def fake_run_build_stage(**kwargs):
        observed.update(kwargs)
        return {"status": "completed", "artifact_dir": kwargs["artifact_dir"], "record_count": 3, "final_path": "final/ohm_borders.jsonl"}

    monkeypatch.setattr(main_module, "run_build_stage", fake_run_build_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "build",
            "--run-id",
            "run-999",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--resume",
            "--force",
            "--build-workers",
            "9",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-999"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["resume"] is True
    assert observed["force"] is True
    assert observed["build_workers"] == 9