"""Manifest helpers for staged OHM borders runs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

STAGE_NAMES = ("fetch", "parse", "enrich", "build")


def _empty_stage() -> dict[str, Any]:
    return {
        "status": "pending",
        "inputs": [],
        "outputs": [],
        "started_at": None,
        "finished_at": None,
        "failed_shards": [],
    }


def create_manifest(run_id: str, artifact_dir: str | Path, options: dict[str, Any] | None = None) -> dict[str, Any]:
    if not run_id.strip():
        raise ValueError("run_id must not be empty")

    return {
        "run_id": run_id,
        "artifact_dir": str(Path(artifact_dir)),
        "options": dict(options or {}),
        "summary": {},
        "stages": {stage_name: _empty_stage() for stage_name in STAGE_NAMES},
    }


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Manifest file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Manifest file is not valid JSON: {path}") from exc


def save_manifest(manifest_path: str | Path, manifest: dict[str, Any]) -> Path:
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")

    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to save manifest: {path}") from exc

    return path


def update_manifest(
    manifest_path: str | Path,
    updater: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    current = load_manifest(manifest_path)
    updated = updater(current)
    save_manifest(manifest_path, updated)
    return updated