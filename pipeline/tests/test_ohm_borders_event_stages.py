"""Tests for OHM border event stage orchestration."""

import json
from pathlib import Path

from pipeline.ohm_borders.event_extractor import extract_event_refs
from pipeline.ohm_borders.stage_events import run_event_scan_stage, run_event_build_stage


def test_event_scan_reads_parsed_shards_and_writes_candidates(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    parsed_dir = artifact_dir / "parsed"
    parsed_dir.mkdir(parents=True)

    # Create manifest first
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"run_id": "run-001", "event_stages": {}}, ensure_ascii=False), encoding="utf-8")

    parsed_shard = parsed_dir / "parsed-00001.jsonl"
    parsed_shard.write_text(
        '{"relation_id":1,"tags":{"name":"Romania"},"stages":[{"relation_id":10,"tags":{"start_event":"Declaration of Kingdom"},"geometry":null}]}' + "\n",
        encoding="utf-8",
    )

    result = run_event_scan_stage(run_id="run-001", artifact_dir=artifact_dir, candidate_shard_size=10)
    assert result["reference_count"] == 1

    candidates_dir = artifact_dir / "events" / "candidates"
    assert candidates_dir.exists()
    assert any(candidates_dir.iterdir())


def test_event_build_writes_final_refs_and_matches(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    enriched_dir = artifact_dir / "events" / "enriched"
    enriched_dir.mkdir(parents=True)

    # Create manifest first
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"run_id": "run-001", "event_stages": {}}, ensure_ascii=False), encoding="utf-8")

    enriched_dir.joinpath("event-enriched-00001.json").write_text(
        '[{"event_label":"Test","resolved_wikidata_id":"Q1","match_source":"explicit_qid"}]',
        encoding="utf-8",
    )

    result = run_event_build_stage(run_id="run-001", artifact_dir=artifact_dir)
    assert result["status"] == "completed"
    assert (artifact_dir / "events" / "final" / "ohm_border_event_refs.jsonl").exists()
    assert (artifact_dir / "events" / "final" / "ohm_border_event_matches.jsonl").exists()