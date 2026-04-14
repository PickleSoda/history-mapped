from pathlib import Path

from click.testing import CliRunner

import pipeline.__main__ as main_module
from pipeline.__main__ import cli


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
        "no_enrich": False,
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

    def fake_run_build_stage(**kwargs):
        stage_calls.append(("build", kwargs))
        return {"status": "completed", "record_count": 1, "final_path": final_path}

    monkeypatch.setattr(main_module, "load_query_text", fake_load_query_text)
    monkeypatch.setattr(main_module, "run_fetch_stage", fake_run_fetch_stage)
    monkeypatch.setattr(main_module, "run_parse_stage", fake_run_parse_stage)
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
            "--no-enrich",
        ],
    )

    assert result.exit_code == 0
    assert [stage_name for stage_name, _ in stage_calls] == ["fetch", "parse", "build"]
    assert output_path.read_text(encoding="utf-8") == '{"name":"Compatland"}\n'
    assert stage_calls[0][1]["run_id"] == "compat-run"
    assert stage_calls[0][1]["raw_shard_size"] == 31
    assert stage_calls[1][1]["parsed_shard_size"] == 17
    assert stage_calls[1][1]["parse_workers"] == 3
    assert stage_calls[2][1]["no_enrich"] is True
    assert stage_calls[2][1]["build_workers"] == 8
    assert stage_calls[2][1]["resume"] is True
    assert stage_calls[2][1]["force"] is True


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