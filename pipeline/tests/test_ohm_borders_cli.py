from pathlib import Path
import json

from click.testing import CliRunner

import pipeline.__main__ as main_module
import pipeline.ohm_borders.__main__ as ohm_main_module
from pipeline.__main__ import cli
from pipeline.ohm_borders.__main__ import cli as borders_cli


def test_borders_run_executes_full_staged_workflow_and_propagates_options(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "artifacts"
    final_path = artifact_dir / "final" / "ohm_borders.jsonl"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text('{"name":"Testland"}\n', encoding="utf-8")

    stage_calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_query_text(query_file):
        assert query_file is None
        return "[out:json];relation(1);out geom;"

    def fake_run_fetch_stage(**kwargs):
        stage_calls.append(("fetch", kwargs))
        return {"status": "completed", "element_count": 1, "raw_path": artifact_dir / "raw" / "overpass.json"}

    def fake_run_parse_stage(**kwargs):
        stage_calls.append(("parse", kwargs))
        return {"status": "completed", "polity_count": 2, "shard_count": 1}

    def fake_run_enrich_stage(**kwargs):
        stage_calls.append(("enrich", kwargs))
        return {"status": "completed", "qid_count": 2, "shard_count": 1}

    def fake_run_build_stage(**kwargs):
        stage_calls.append(("build", kwargs))
        return {"status": "completed", "record_count": 2, "final_path": final_path}

    monkeypatch.setattr(main_module, "load_query_text", fake_load_query_text)
    monkeypatch.setattr(main_module, "run_fetch_stage", fake_run_fetch_stage)
    monkeypatch.setattr(main_module, "run_parse_stage", fake_run_parse_stage)
    monkeypatch.setattr(main_module, "run_enrich_stage", fake_run_enrich_stage)
    monkeypatch.setattr(main_module, "run_build_stage", fake_run_build_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "run",
            "--run-id",
            "run-001",
            "--artifact-dir",
            str(artifact_dir),
            "--parsed-shard-size",
            "23",
            "--raw-shard-size",
            "77",
            "--parse-workers",
            "4",
            "--build-workers",
            "6",
            "--enrich-batch-size",
            "11",
            "--enrich-workers",
            "5",
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert [stage_name for stage_name, _ in stage_calls] == ["fetch", "parse", "enrich", "build"]

    fetch_kwargs = stage_calls[0][1]
    parse_kwargs = stage_calls[1][1]
    enrich_kwargs = stage_calls[2][1]
    build_kwargs = stage_calls[3][1]

    assert fetch_kwargs == {
        "run_id": "run-001",
        "artifact_dir": artifact_dir,
        "query": "[out:json];relation(1);out geom;",
        "raw_shard_size": 77,
        "resume": True,
        "force": True,
    }
    assert parse_kwargs == {
        "run_id": "run-001",
        "artifact_dir": artifact_dir,
        "parsed_shard_size": 23,
        "parse_workers": 4,
        "resume": True,
        "force": True,
    }
    assert enrich_kwargs == {
        "run_id": "run-001",
        "artifact_dir": artifact_dir,
        "enrich_batch_size": 11,
        "enrich_workers": 5,
        "resume": True,
        "force": True,
    }
    assert build_kwargs == {
        "run_id": "run-001",
        "artifact_dir": artifact_dir,
        "resume": True,
        "force": True,
        "build_workers": 6,
    }


def test_borders_compatibility_mode_runs_staged_workflow_and_writes_output(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "artifacts"
    final_path = artifact_dir / "final" / "ohm_borders.jsonl"
    output_path = tmp_path / "ohm_borders_global.jsonl"
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text('{"name":"Compatland"}\n', encoding="utf-8")

    stage_calls: list[tuple[str, dict[str, object]]] = []

    def fake_load_query_text(query_file):
        assert query_file is None
        return "[out:json];relation(2);out geom;"

    def fake_run_fetch_stage(**kwargs):
        stage_calls.append(("fetch", kwargs))
        return {"status": "completed", "element_count": 1, "raw_path": artifact_dir / "raw" / "overpass.json"}

    def fake_run_parse_stage(**kwargs):
        stage_calls.append(("parse", kwargs))
        return {"status": "completed", "polity_count": 1, "shard_count": 1}

    def fake_run_enrich_stage(**kwargs):
        stage_calls.append(("enrich", kwargs))
        return {"status": "completed", "qid_count": 1, "shard_count": 1}

    def fake_run_build_stage(**kwargs):
        stage_calls.append(("build", kwargs))
        return {"status": "completed", "record_count": 1, "final_path": final_path}

    monkeypatch.setattr(main_module, "load_query_text", fake_load_query_text)
    monkeypatch.setattr(main_module, "run_fetch_stage", fake_run_fetch_stage)
    monkeypatch.setattr(main_module, "run_parse_stage", fake_run_parse_stage)
    monkeypatch.setattr(main_module, "run_enrich_stage", fake_run_enrich_stage)
    monkeypatch.setattr(main_module, "run_build_stage", fake_run_build_stage)

    result = runner.invoke(
        cli,
        [
            "borders",
            "--output",
            str(output_path),
            "--run-id",
            "compat-run",
            "--artifact-dir",
            str(artifact_dir),
            "--parsed-shard-size",
            "17",
            "--raw-shard-size",
            "31",
            "--parse-workers",
            "3",
            "--build-workers",
            "8",
            "--enrich-batch-size",
            "9",
            "--enrich-workers",
            "2",
            "--resume",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert [stage_name for stage_name, _ in stage_calls] == ["fetch", "parse", "enrich", "build"]
    assert output_path.read_text(encoding="utf-8") == '{"name":"Compatland"}\n'
    assert stage_calls[0][1]["run_id"] == "compat-run"
    assert stage_calls[0][1]["raw_shard_size"] == 31
    assert stage_calls[1][1]["parsed_shard_size"] == 17
    assert stage_calls[1][1]["parse_workers"] == 3
    assert stage_calls[2][1]["enrich_batch_size"] == 9
    assert stage_calls[2][1]["enrich_workers"] == 2
    assert stage_calls[3][1]["build_workers"] == 8
    assert stage_calls[3][1]["resume"] is True
    assert stage_calls[3][1]["force"] is True


def test_borders_enrich_output_names_cli_wires_paths_and_batch_size(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    input_path = tmp_path / "ohm_borders.jsonl"
    output_path = tmp_path / "ohm_borders_enriched.jsonl"
    input_path.write_text('{"name":"Testland"}\n', encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_enrich_output_jsonl_missing_qids(**kwargs):
        captured.update(kwargs)
        output_path.write_text('{"name":"Testland","wikidata_id":"Q1"}\n', encoding="utf-8")
        return {"record_count": 1, "searched_count": 1, "matched_count": 1, "output_path": output_path}

    monkeypatch.setattr(main_module, "enrich_output_jsonl_missing_qids", fake_enrich_output_jsonl_missing_qids)

    result = runner.invoke(
        cli,
        [
            "borders",
            "enrich-output-names",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--enrich-batch-size",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert captured["input_path"] == input_path
    assert captured["output_path"] == output_path
    assert captured["batch_size"] == 25


def test_root_borders_extract_subgraph_cli_writes_subset_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    artifact_dir = tmp_path / "subset"
    input_path.write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "relation",
                        "id": 10,
                        "tags": {
                            "boundary": "administrative",
                            "admin_level": "2",
                            "name": "Roman Empire",
                            "wikidata": "Q1",
                            "successor:wikidata": "Q2",
                        },
                        "members": [],
                    },
                    {
                        "type": "relation",
                        "id": 20,
                        "tags": {
                            "boundary": "administrative",
                            "admin_level": "2",
                            "name": "Byzantine Empire",
                            "wikidata": "Q2",
                        },
                        "members": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        [
            "borders",
            "extract-subgraph",
            "--input",
            str(input_path),
            "--artifact-dir",
            str(artifact_dir),
            "--seed-qid",
            "Q1",
            "--build-index-if-missing",
            "--max-depth",
            "1",
            "--max-nodes",
            "10",
            "--raw-shard-size",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert (artifact_dir / "raw" / "overpass.json").exists()
    assert (artifact_dir / "subgraph" / "closure_report.json").exists()


def test_extract_subgraph_cli_passes_index_options(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    artifact_dir = tmp_path / "subset"
    index_path = tmp_path / "subset-index.sqlite3"
    input_path.write_text(json.dumps({"elements": []}), encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_run_extract_subgraph_stage(**kwargs):
        captured.update(kwargs)
        raw_path = artifact_dir / "raw" / "overpass.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text('{"elements":[]}', encoding="utf-8")
        return {"status": "completed", "raw_path": raw_path, "relation_count": 0}

    monkeypatch.setattr(ohm_main_module, "run_extract_subgraph_stage", fake_run_extract_subgraph_stage)

    result = runner.invoke(
        borders_cli,
        [
            "extract-subgraph",
            "--input",
            str(input_path),
            "--artifact-dir",
            str(artifact_dir),
            "--index-path",
            str(index_path),
            "--seed-name",
            "roman empire",
            "--build-index-if-missing",
            "--auto-select-fuzzy",
            "--max-depth",
            "1",
            "--max-nodes",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert captured["input_path"] == input_path
    assert captured["artifact_dir"] == artifact_dir
    assert captured["index_path"] == index_path
    assert captured["seed_name"] == "roman empire"
    assert captured["build_index_if_missing"] is True
    assert captured["auto_select_fuzzy"] is True


def test_ohm_borders_extract_subgraph_cli_supports_resume(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    artifact_dir = tmp_path / "subset"
    input_path.write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "relation",
                        "id": 10,
                        "tags": {
                            "boundary": "administrative",
                            "admin_level": "2",
                            "name": "Roman Empire",
                            "wikidata": "Q1",
                        },
                        "members": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    first = runner.invoke(
        borders_cli,
        [
            "extract-subgraph",
            "--input",
            str(input_path),
            "--artifact-dir",
            str(artifact_dir),
            "--seed-qid",
            "Q1",
            "--build-index-if-missing",
            "--max-depth",
            "0",
            "--max-nodes",
            "10",
        ],
    )
    second = runner.invoke(
        borders_cli,
        [
            "extract-subgraph",
            "--input",
            str(input_path),
            "--artifact-dir",
            str(artifact_dir),
            "--seed-qid",
            "Q1",
            "--build-index-if-missing",
            "--max-depth",
            "0",
            "--max-nodes",
            "10",
            "--resume",
        ],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "skipped" in second.output.lower()


def test_build_index_cli_passes_input_and_force(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    input_path.write_text(json.dumps({"elements": []}), encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_build_index(source_path, *, index_path, force=False, stale_timeout_seconds=900):
        captured["source_path"] = source_path
        captured["index_path"] = index_path
        captured["force"] = force
        return {"status": "completed", "index_path": index_path, "relation_count": 0}

    monkeypatch.setattr(ohm_main_module, "build_index", fake_build_index)

    result = runner.invoke(
        borders_cli,
        [
            "build-index",
            "--input",
            str(input_path),
            "--index-path",
            str(index_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "source_path": input_path,
        "index_path": index_path,
        "force": True,
    }


def test_root_borders_build_index_cli_is_wired(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    input_path.write_text(json.dumps({"elements": []}), encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_build_index(source_path, *, index_path, force=False, stale_timeout_seconds=900):
        captured["source_path"] = source_path
        captured["index_path"] = index_path
        captured["force"] = force
        return {"status": "completed", "index_path": index_path, "relation_count": 0}

    monkeypatch.setattr(ohm_main_module, "build_index", fake_build_index)

    result = runner.invoke(
        cli,
        [
            "borders",
            "build-index",
            "--input",
            str(input_path),
            "--index-path",
            str(index_path),
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "source_path": input_path,
        "index_path": index_path,
        "force": False,
    }


def test_extract_subgraph_cli_fails_for_incompatible_index_with_rebuild_guidance(tmp_path: Path) -> None:
    runner = CliRunner()
    input_path = tmp_path / "overpass.json"
    index_path = tmp_path / "overpass.sqlite3"
    input_path.write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "relation",
                        "id": 10,
                        "tags": {
                            "boundary": "administrative",
                            "admin_level": "2",
                            "name": "Roman Empire",
                            "wikidata": "Q1",
                        },
                        "members": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert runner.invoke(
        borders_cli,
        [
            "build-index",
            "--input",
            str(input_path),
            "--index-path",
            str(index_path),
        ],
    ).exit_code == 0

    input_path.write_text(
        json.dumps(
            {
                "elements": [
                    {
                        "type": "relation",
                        "id": 10,
                        "tags": {
                            "boundary": "administrative",
                            "admin_level": "2",
                            "name": "Changed Roman Empire",
                            "wikidata": "Q1",
                        },
                        "members": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        borders_cli,
        [
            "extract-subgraph",
            "--input",
            str(input_path),
            "--index-path",
            str(index_path),
            "--run-id",
            "incompatible-index",
            "--seed-qid",
            "Q1",
            "--max-depth",
            "0",
            "--max-nodes",
            "10",
        ],
    )

    assert result.exit_code != 0
    assert result.exception is not None
    assert "build-index" in str(result.exception)
    assert "--force" in str(result.exception)