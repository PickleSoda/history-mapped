"""Tests for event artifact path helpers."""

from pathlib import Path

from pipeline.ohm_borders.artifacts import (
    event_candidates_dir,
    event_candidate_shard_path,
    event_enriched_dir,
    event_enriched_shard_path,
    event_final_refs_path,
    event_final_matches_path,
)


def test_event_candidates_dir_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_candidates_dir(artifact_dir) == artifact_dir / "events" / "candidates"


def test_event_candidate_shard_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_candidate_shard_path(artifact_dir, 1) == artifact_dir / "events" / "candidates" / "event-candidates-00001.jsonl"


def test_event_enriched_dir_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_enriched_dir(artifact_dir) == artifact_dir / "events" / "enriched"


def test_event_enriched_shard_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_enriched_shard_path(artifact_dir, 1) == artifact_dir / "events" / "enriched" / "event-enriched-00001.json"


def test_event_final_refs_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_final_refs_path(artifact_dir) == artifact_dir / "events" / "final" / "ohm_border_event_refs.jsonl"


def test_event_final_matches_path_is_deterministic(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "output" / "ohm_borders" / "run-001"
    assert event_final_matches_path(artifact_dir) == artifact_dir / "events" / "final" / "ohm_border_event_matches.jsonl"