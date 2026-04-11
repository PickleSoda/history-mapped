import json
from pathlib import Path

from click.testing import CliRunner
import orjson

import pipeline.__main__ as main_module
from pipeline.__main__ import cli
from pipeline.ohm_borders.artifacts import (
    built_shard_path,
    enriched_shard_path,
    final_jsonl_path,
    parsed_shard_path,
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
        return {"elements": [{"id": 1}, {"id": 2}]}

    result = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="[out:json];relation(1);out geom;",
        fetcher=fake_fetch_raw,
    )

    raw_path = raw_overpass_path(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"

    assert result["status"] == "completed"
    assert json.loads(raw_path.read_text(encoding="utf-8")) == {"elements": [{"id": 1}, {"id": 2}]}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["stages"]["fetch"]["status"] == "completed"
    assert manifest["stages"]["fetch"]["outputs"] == ["raw/overpass.json"]
    assert manifest["summary"]["raw_elements"] == 2


def test_parse_stage_writes_parsed_shards_and_manifest_summary(tmp_path: Path) -> None:
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
    assert manifest["summary"]["parsed_polities"] == 3
    assert manifest["summary"]["parsed_shards"] == 2
    assert manifest["summary"]["parse_workers"] == 3


def test_fetch_stage_resume_skips_existing_raw_unless_forced(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    raw_path = raw_overpass_path(artifact_dir)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps({"elements": [{"id": "existing"}]}, separators=(",", ":")), encoding="utf-8")

    calls: list[str] = []

    def fake_fetch_raw(query: str) -> dict:
        calls.append(query)
        return {"elements": [{"id": "fresh"}]}

    skipped = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="query-1",
        resume=True,
        fetcher=fake_fetch_raw,
    )
    forced = run_fetch_stage(
        run_id="run-001",
        artifact_dir=artifact_dir,
        query="query-2",
        resume=True,
        force=True,
        fetcher=fake_fetch_raw,
    )

    assert skipped["status"] == "skipped"
    assert forced["status"] == "completed"
    assert calls == ["query-2"]
    assert json.loads(raw_path.read_text(encoding="utf-8")) == {"elements": [{"id": "fresh"}]}


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
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-123"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["query"] == "[out:json];relation(42);out geom;"
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

    result = run_build_stage(run_id="run-001", artifact_dir=artifact_dir, no_enrich=True)
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
            "--no-enrich",
        ],
    )

    assert result.exit_code == 0
    assert observed["run_id"] == "run-999"
    assert observed["artifact_dir"] == tmp_path / "artifacts"
    assert observed["resume"] is True
    assert observed["force"] is True
    assert observed["no_enrich"] is True