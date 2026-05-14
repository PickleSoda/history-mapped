from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from pipeline.ohm_borders.artifacts import ensure_artifact_dirs, raw_overpass_path, raw_shard_path, stage_done_marker_path
from pipeline.ohm_borders.fetcher import fetch_raw
from pipeline.ohm_borders.stage_common import (
    _chunk_records,
    _load_or_create_manifest,
    _relation_elements,
    _relative_artifact_path,
    _timestamp,
    _write_jsonl_atomic,
    _write_stage_update,
    _write_text_atomic,
    resolve_artifact_dir,
    resolve_run_id,
)

logger = logging.getLogger(__name__)


def run_fetch_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    query: str,
    raw_shard_size: int = 200,
    resume: bool = False,
    force: bool = False,
    fetcher: Callable[[str], dict[str, Any]] = fetch_raw,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    logger.info(
        "fetch stage starting run_id=%s artifact_dir=%s raw_shard_size=%s resume=%s force=%s",
        run_id,
        resolved_artifact_dir,
        raw_shard_size,
        resume,
        force,
    )

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={"raw_shard_size": raw_shard_size},
    )
    raw_path = raw_overpass_path(resolved_artifact_dir)
    done_marker_path = stage_done_marker_path(resolved_artifact_dir, "fetch")

    if raw_shard_size < 1:
        raise ValueError("raw_shard_size must be >= 1")

    if resume and raw_path.exists() and not force:
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        shard_result = _materialize_raw_relation_shards(
            artifact_dir=resolved_artifact_dir,
            raw_payload=raw_payload,
            raw_shard_size=raw_shard_size,
            done_marker_path=done_marker_path,
            force=False,
        )

        outputs = [_relative_artifact_path(resolved_artifact_dir, raw_path)]
        outputs.extend(_relative_artifact_path(resolved_artifact_dir, path) for path in shard_result["shard_paths"])
        outputs.append(_relative_artifact_path(resolved_artifact_dir, done_marker_path))

        stage_status = "skipped" if shard_result["written_shards"] == 0 else "completed"
        _write_stage_update(
            manifest_path,
            "fetch",
            status=stage_status,
            inputs=["query"],
            outputs=outputs,
            summary={
                "raw_elements": shard_result["element_count"],
                "raw_relation_elements": shard_result["relation_count"],
                "raw_shards": len(shard_result["shard_paths"]),
                "raw_shards_written": shard_result["written_shards"],
                "raw_shards_skipped": shard_result["skipped_shards"],
                "raw_shard_size": raw_shard_size,
            },
        )
        logger.info(
            "fetch stage resume complete status=%s raw_elements=%s raw_relations=%s raw_shards=%s written=%s skipped=%s",
            stage_status,
            shard_result["element_count"],
            shard_result["relation_count"],
            len(shard_result["shard_paths"]),
            shard_result["written_shards"],
            shard_result["skipped_shards"],
        )
        return {
            "status": stage_status,
            "artifact_dir": resolved_artifact_dir,
            "manifest_path": manifest_path,
            "raw_path": raw_path,
            "element_count": shard_result["element_count"],
            "shard_count": len(shard_result["shard_paths"]),
        }

    _write_stage_update(manifest_path, "fetch", status="running", inputs=["query"])

    try:
        logger.info("fetch stage requesting overpass payload")
        raw_payload = fetcher(query)
        _write_text_atomic(raw_path, json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":")))

        shard_result = _materialize_raw_relation_shards(
            artifact_dir=resolved_artifact_dir,
            raw_payload=raw_payload,
            raw_shard_size=raw_shard_size,
            done_marker_path=done_marker_path,
            force=True,
        )

        outputs = [_relative_artifact_path(resolved_artifact_dir, raw_path)]
        outputs.extend(_relative_artifact_path(resolved_artifact_dir, path) for path in shard_result["shard_paths"])
        outputs.append(_relative_artifact_path(resolved_artifact_dir, done_marker_path))

        _write_stage_update(
            manifest_path,
            "fetch",
            status="completed",
            inputs=["query"],
            outputs=outputs,
            summary={
                "raw_elements": shard_result["element_count"],
                "raw_relation_elements": shard_result["relation_count"],
                "raw_shards": len(shard_result["shard_paths"]),
                "raw_shards_written": shard_result["written_shards"],
                "raw_shards_skipped": shard_result["skipped_shards"],
                "raw_shard_size": raw_shard_size,
            },
        )
        logger.info(
            "fetch stage completed raw_elements=%s raw_relations=%s raw_shards=%s written=%s skipped=%s",
            shard_result["element_count"],
            shard_result["relation_count"],
            len(shard_result["shard_paths"]),
            shard_result["written_shards"],
            shard_result["skipped_shards"],
        )
    except Exception:
        logger.exception("fetch stage failed")
        _write_stage_update(manifest_path, "fetch", status="failed", inputs=["query"])
        raise

    return {
        "status": "completed",
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "raw_path": raw_path,
        "element_count": shard_result["element_count"],
        "shard_count": len(shard_result["shard_paths"]),
    }


def _materialize_raw_relation_shards(
    *,
    artifact_dir: Path,
    raw_payload: dict[str, Any],
    raw_shard_size: int,
    done_marker_path: Path,
    force: bool,
) -> dict[str, Any]:
    elements = raw_payload.get("elements", [])
    relation_elements = _relation_elements(elements if isinstance(elements, list) else [])
    relation_shards = _chunk_records(relation_elements, raw_shard_size)

    shard_paths = [raw_shard_path(artifact_dir, index) for index in range(1, len(relation_shards) + 1)]

    existing_raw_shards = sorted(raw_shard_path_item for raw_shard_path_item in artifact_dir.joinpath("raw").glob("raw-*.jsonl"))
    expected_raw_shards = set(shard_paths)
    for stale_path in existing_raw_shards:
        if stale_path not in expected_raw_shards:
            stale_path.unlink()

    written_shards = 0
    skipped_shards = 0

    for shard_index, shard_records in enumerate(relation_shards, start=1):
        shard_path = raw_shard_path(artifact_dir, shard_index)

        if not force and shard_path.exists():
            skipped_shards += 1
            continue

        _write_jsonl_atomic(shard_path, shard_records)
        written_shards += 1

    marker_payload = {
        "stage": "fetch",
        "relation_count": len(relation_elements),
        "shard_count": len(relation_shards),
        "completed_at": _timestamp(),
    }
    if force or not done_marker_path.exists() or written_shards > 0:
        _write_text_atomic(done_marker_path, json.dumps(marker_payload, ensure_ascii=True, separators=(",", ":")))

    return {
        "element_count": len(elements) if isinstance(elements, list) else 0,
        "relation_count": len(relation_elements),
        "shard_paths": shard_paths,
        "written_shards": written_shards,
        "skipped_shards": skipped_shards,
    }
