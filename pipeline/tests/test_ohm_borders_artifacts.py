import json
from pathlib import Path

import pipeline.ohm_borders.manifest as manifest_module
from pipeline.ohm_borders.artifacts import (
    artifact_dir_for_run,
    built_shard_path,
    enriched_shard_path,
    final_jsonl_path,
    parsed_shard_path,
    raw_shard_path,
    stage_done_marker_path,
    raw_overpass_path,
)
from pipeline.ohm_borders.manifest import create_manifest, save_manifest, update_manifest


def test_artifact_paths_are_deterministic_from_run_id(tmp_path: Path) -> None:
    artifact_root = tmp_path / "output" / "ohm_borders"
    artifact_dir = artifact_dir_for_run("20260411-120000", artifact_root)

    assert artifact_dir == artifact_root / "20260411-120000"
    assert raw_overpass_path(artifact_dir) == artifact_dir / "raw" / "overpass.json"
    assert final_jsonl_path(artifact_dir) == artifact_dir / "final" / "ohm_borders.jsonl"


def test_shard_paths_are_deterministic() -> None:
    artifact_dir = Path("output/ohm_borders/20260411-120000")

    assert raw_shard_path(artifact_dir, 4) == artifact_dir / "raw" / "raw-00004.jsonl"
    assert parsed_shard_path(artifact_dir, 1) == artifact_dir / "parsed" / "parsed-00001.jsonl"
    assert enriched_shard_path(artifact_dir, 7) == artifact_dir / "enriched" / "enriched-qids-00007.json"
    assert built_shard_path(artifact_dir, 12) == artifact_dir / "built" / "built-00012.jsonl"


def test_stage_done_marker_paths_are_deterministic() -> None:
    artifact_dir = Path("output/ohm_borders/20260411-120000")

    assert stage_done_marker_path(artifact_dir, "fetch") == artifact_dir / ".done" / "fetch.done"
    assert stage_done_marker_path(artifact_dir, "parse") == artifact_dir / ".done" / "parse.done"


def test_create_manifest_matches_documented_top_level_shape(tmp_path: Path) -> None:
    artifact_dir = artifact_dir_for_run("20260411-120000", tmp_path / "output" / "ohm_borders")

    manifest = create_manifest(
        run_id="20260411-120000",
        artifact_dir=artifact_dir,
        options={"parse_workers": 4, "parsed_shard_size": 100},
    )

    assert list(manifest.keys()) == ["run_id", "artifact_dir", "options", "summary", "stages"]
    assert manifest["run_id"] == "20260411-120000"
    assert manifest["artifact_dir"] == str(artifact_dir)
    assert manifest["options"] == {"parse_workers": 4, "parsed_shard_size": 100}
    assert manifest["summary"] == {}
    assert list(manifest["stages"].keys()) == ["fetch", "parse", "enrich", "build"]

    for stage_name in ("fetch", "parse", "enrich", "build"):
        assert list(manifest["stages"][stage_name].keys()) == [
            "status",
            "inputs",
            "outputs",
            "started_at",
            "finished_at",
            "failed_shards",
        ]
        assert manifest["stages"][stage_name] == {
            "status": "pending",
            "inputs": [],
            "outputs": [],
            "started_at": None,
            "finished_at": None,
            "failed_shards": [],
        }


def test_update_manifest_writes_temp_file_then_replaces_atomically(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "manifest.json"
    original = create_manifest(
        run_id="20260411-120000",
        artifact_dir=tmp_path / "output" / "ohm_borders" / "20260411-120000",
        options={},
    )
    save_manifest(manifest_path, original)

    observed: dict[str, object] = {}
    real_replace = manifest_module.os.replace

    def fake_replace(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        observed["source_name"] = source_path.name
        observed["destination"] = destination_path
        observed["tmp_exists_during_replace"] = source_path.exists()
        observed["tmp_payload"] = json.loads(source_path.read_text(encoding="utf-8"))
        observed["old_payload"] = json.loads(destination_path.read_text(encoding="utf-8"))
        real_replace(source_path, destination_path)

    monkeypatch.setattr(manifest_module.os, "replace", fake_replace)

    updated = update_manifest(
        manifest_path,
        lambda current: {
            **current,
            "summary": {"records_written": 3},
            "stages": {
                **current["stages"],
                "build": {
                    **current["stages"]["build"],
                    "status": "completed",
                    "outputs": ["final/ohm_borders.jsonl"],
                },
            },
        },
    )

    assert observed["source_name"] == "manifest.json.tmp"
    assert observed["destination"] == manifest_path
    assert observed["tmp_exists_during_replace"] is True
    assert observed["old_payload"]["summary"] == {}
    assert observed["tmp_payload"]["summary"] == {"records_written": 3}
    assert updated["summary"] == {"records_written": 3}
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["stages"]["build"]["status"] == "completed"
    assert not manifest_path.with_name("manifest.json.tmp").exists()


def test_load_manifest_raises_descriptive_error_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing-manifest.json"

    try:
        manifest_module.load_manifest(missing)
    except RuntimeError as exc:
        assert str(missing) in str(exc)
        assert "Manifest file not found" in str(exc)
    else:
        raise AssertionError("Expected load_manifest to raise RuntimeError")


def test_save_manifest_cleans_up_temp_file_when_replace_fails(tmp_path: Path, monkeypatch) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = create_manifest(
        run_id="20260411-120000",
        artifact_dir=tmp_path / "output" / "ohm_borders" / "20260411-120000",
        options={},
    )

    def fake_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(manifest_module.os, "replace", fake_replace)

    try:
        save_manifest(manifest_path, manifest)
    except RuntimeError as exc:
        assert "Failed to save manifest" in str(exc)
    else:
        raise AssertionError("Expected save_manifest to raise RuntimeError")

    assert not manifest_path.with_name("manifest.json.tmp").exists()