"""Artifact path helpers for staged OHM borders runs."""

from __future__ import annotations

from pathlib import Path


def artifact_dir_for_run(run_id: str, artifact_root: str | Path = "output/ohm_borders") -> Path:
    """Return the deterministic artifact directory for a run id."""
    return Path(artifact_root) / run_id


def raw_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "raw"


def done_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / ".done"


def parsed_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "parsed"


def enriched_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "enriched"


def built_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "built"


def final_dir(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "final"


def raw_overpass_path(artifact_dir: str | Path) -> Path:
    return raw_dir(artifact_dir) / "overpass.json"


def raw_shard_path(artifact_dir: str | Path, shard_index: int) -> Path:
    return raw_dir(artifact_dir) / f"raw-{shard_index:05d}.jsonl"


def stage_done_marker_path(artifact_dir: str | Path, stage_name: str) -> Path:
    if not stage_name.strip():
        raise ValueError("stage_name must not be empty")
    return done_dir(artifact_dir) / f"{stage_name}.done"


def parsed_shard_path(artifact_dir: str | Path, shard_index: int) -> Path:
    return parsed_dir(artifact_dir) / f"parsed-{shard_index:05d}.jsonl"


def enriched_shard_path(artifact_dir: str | Path, shard_index: int) -> Path:
    return enriched_dir(artifact_dir) / f"enriched-qids-{shard_index:05d}.json"


def built_shard_path(artifact_dir: str | Path, shard_index: int) -> Path:
    return built_dir(artifact_dir) / f"built-{shard_index:05d}.jsonl"


def final_jsonl_path(artifact_dir: str | Path) -> Path:
    return final_dir(artifact_dir) / "ohm_borders.jsonl"


def ensure_artifact_dirs(artifact_dir: str | Path) -> None:
    for directory in (
        raw_dir(artifact_dir),
        done_dir(artifact_dir),
        parsed_dir(artifact_dir),
        enriched_dir(artifact_dir),
        built_dir(artifact_dir),
        final_dir(artifact_dir),
    ):
        directory.mkdir(parents=True, exist_ok=True)