from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.ohm_borders.artifacts import (
    ensure_artifact_dirs,
    raw_overpass_path,
    raw_shard_path,
    subgraph_closure_report_path,
    subgraph_edges_path,
    subgraph_seed_path,
)
from pipeline.ohm_borders.stage_common import (
    _chunk_records,
    _load_or_create_manifest,
    _relative_artifact_path,
    _relation_elements,
    _write_jsonl_atomic,
    _write_stage_update,
    _write_text_atomic,
    resolve_artifact_dir,
    resolve_run_id,
)
from pipeline.ohm_borders.subgraph_extractor import extract_country_subgraph


def run_extract_subgraph_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    input_path: str | Path,
    seed_qid: str | None = None,
    seed_name: str | None = None,
    max_depth: int,
    max_nodes: int,
    raw_shard_size: int = 200,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    resolved_input_path = Path(input_path)
    traversal_summary = {
        "subgraph_input_path": str(resolved_input_path),
        "subgraph_seed_qid": seed_qid,
        "subgraph_seed_name": seed_name,
        "subgraph_max_depth": max_depth,
        "subgraph_max_nodes": max_nodes,
        "subgraph_raw_shard_size": raw_shard_size,
    }
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options=traversal_summary,
    )

    reduced_payload_path = raw_overpass_path(resolved_artifact_dir)
    seed_path = subgraph_seed_path(resolved_artifact_dir)
    edges_path = subgraph_edges_path(resolved_artifact_dir)
    closure_report_path = subgraph_closure_report_path(resolved_artifact_dir)

    if resume and not force and reduced_payload_path.exists() and seed_path.exists() and closure_report_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        drift_keys = (
            "subgraph_input_path",
            "subgraph_seed_qid",
            "subgraph_seed_name",
            "subgraph_max_depth",
            "subgraph_max_nodes",
            "subgraph_raw_shard_size",
        )
        drift = [
            key
            for key in drift_keys
            if manifest.get("summary", {}).get(key) != traversal_summary.get(key)
        ]
        if drift:
            raise RuntimeError("Subgraph extraction parameters changed; rerun with --force or a new run_id.")

        _write_stage_update(
            manifest_path,
            "extract_subgraph",
            status="skipped",
            inputs=[str(resolved_input_path)],
            outputs=[
                _relative_artifact_path(resolved_artifact_dir, reduced_payload_path),
                _relative_artifact_path(resolved_artifact_dir, seed_path),
                _relative_artifact_path(resolved_artifact_dir, closure_report_path),
            ],
            summary=traversal_summary,
        )
        return {
            "status": "skipped",
            "artifact_dir": resolved_artifact_dir,
            "manifest_path": manifest_path,
            "raw_path": reduced_payload_path,
        }

    _write_stage_update(manifest_path, "extract_subgraph", status="running", inputs=[str(resolved_input_path)])

    overpass_payload = json.loads(resolved_input_path.read_text(encoding="utf-8-sig"))
    extraction = extract_country_subgraph(
        overpass_payload,
        seed_qid=seed_qid,
        seed_name=seed_name,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )

    _write_text_atomic(reduced_payload_path, json.dumps(extraction["reduced_payload"], ensure_ascii=False, separators=(",", ":")))
    _write_text_atomic(seed_path, json.dumps(extraction["seed"], ensure_ascii=True, indent=2))
    _write_jsonl_atomic(edges_path, extraction["graph_edges"])
    _write_text_atomic(closure_report_path, json.dumps(extraction["closure_report"], ensure_ascii=True, indent=2))

    relation_elements = _relation_elements(extraction["reduced_payload"].get("elements", []))
    relation_shards = _chunk_records(relation_elements, raw_shard_size)
    shard_paths: list[Path] = []
    for shard_index, shard_records in enumerate(relation_shards, start=1):
        shard_path = raw_shard_path(resolved_artifact_dir, shard_index)
        _write_jsonl_atomic(shard_path, shard_records)
        shard_paths.append(shard_path)

    outputs = [
        _relative_artifact_path(resolved_artifact_dir, reduced_payload_path),
        _relative_artifact_path(resolved_artifact_dir, seed_path),
        _relative_artifact_path(resolved_artifact_dir, edges_path),
        _relative_artifact_path(resolved_artifact_dir, closure_report_path),
        *[_relative_artifact_path(resolved_artifact_dir, shard_path) for shard_path in shard_paths],
    ]
    _write_stage_update(
        manifest_path,
        "extract_subgraph",
        status="completed",
        inputs=[str(resolved_input_path)],
        outputs=outputs,
        summary={
            **traversal_summary,
            "subgraph_relation_count": len(relation_elements),
            "subgraph_raw_shards": len(shard_paths),
        },
    )

    return {
        "status": "completed",
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "raw_path": reduced_payload_path,
        "relation_count": len(relation_elements),
        "shard_count": len(shard_paths),
    }