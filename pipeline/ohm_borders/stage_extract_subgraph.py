from __future__ import annotations

import json
import os
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
from pipeline.ohm_borders.index_builder import build_index
from pipeline.ohm_borders.index_builder import source_fingerprint_for_file
from pipeline.ohm_borders.index_store import SCHEMA_VERSION, index_matches_source, read_index_metadata
from pipeline.ohm_borders.subgraph_extractor import extract_country_subgraph_from_index, resolve_country_subgraph_seed_from_index


def run_extract_subgraph_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    input_path: str | Path,
    index_path: str | Path | None = None,
    seed_qid: str | None = None,
    seed_name: str | None = None,
    max_depth: int,
    max_nodes: int,
    raw_shard_size: int = 200,
    build_index_if_missing: bool = False,
    auto_select_fuzzy: bool = False,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    resolved_input_path = Path(input_path)
    resolved_index_path = _resolve_index_path(input_path=resolved_input_path, index_path=index_path)
    resolved_seed = _prepare_resolved_seed(
        input_path=resolved_input_path,
        index_path=resolved_index_path,
        seed_qid=seed_qid,
        seed_name=seed_name,
        build_index_if_missing=build_index_if_missing,
        auto_select_fuzzy=auto_select_fuzzy,
    )
    traversal_summary = {
        "subgraph_input_path": str(resolved_input_path),
        "subgraph_index_path": str(resolved_index_path),
        "subgraph_seed_qid": seed_qid,
        "subgraph_seed_name": seed_name,
        "subgraph_seed_relation_ids": list(resolved_seed["relation_ids"]),
        "subgraph_resolved_seed_qid": resolved_seed.get("wikidata_id"),
        "subgraph_resolved_seed_name": resolved_seed.get("name"),
        "subgraph_max_depth": max_depth,
        "subgraph_max_nodes": max_nodes,
        "subgraph_raw_shard_size": raw_shard_size,
        "subgraph_build_index_if_missing": build_index_if_missing,
        "subgraph_auto_select_fuzzy": auto_select_fuzzy,
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
            "subgraph_index_path",
            "subgraph_max_depth",
            "subgraph_max_nodes",
            "subgraph_raw_shard_size",
            "subgraph_auto_select_fuzzy",
        )
        drift = [
            key
            for key in drift_keys
            if manifest.get("summary", {}).get(key) != traversal_summary.get(key)
        ]
        if drift:
            raise RuntimeError("Subgraph extraction parameters changed; rerun with --force or a new run_id.")

        existing_seed = json.loads(seed_path.read_text(encoding="utf-8"))
        if list(existing_seed.get("relation_ids", [])) != list(resolved_seed["relation_ids"]):
            raise RuntimeError("Resolved subgraph seed changed; rerun with --force or a new run_id.")

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

    extraction = extract_country_subgraph_from_index(
        resolved_index_path,
        seed_qid=seed_qid,
        seed_name=seed_name,
        max_depth=max_depth,
        max_nodes=max_nodes,
        auto_select_fuzzy=auto_select_fuzzy,
    )

    _write_text_atomic(reduced_payload_path, json.dumps(extraction["reduced_payload"], ensure_ascii=False, separators=(",", ":")))
    _write_text_atomic(
        seed_path,
        json.dumps(
            {
                **extraction["seed"],
                "extraction": {
                    "input_path": str(resolved_input_path),
                    "index_path": str(resolved_index_path),
                    "max_depth": max_depth,
                    "max_nodes": max_nodes,
                    "auto_select_fuzzy": auto_select_fuzzy,
                },
            },
            ensure_ascii=True,
            indent=2,
        ),
    )
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


def _resolve_index_path(*, input_path: Path, index_path: str | Path | None) -> Path:
    if index_path is not None:
        return Path(index_path)

    env_index_path = os.environ.get("OHM_SUBGRAPH_INDEX_PATH")
    if env_index_path:
        return Path(env_index_path)

    return input_path.parent / "overpass.sqlite3"


def _prepare_resolved_seed(
    *,
    input_path: Path,
    index_path: Path,
    seed_qid: str | None,
    seed_name: str | None,
    build_index_if_missing: bool,
    auto_select_fuzzy: bool,
) -> dict[str, Any]:
    _ensure_compatible_index(
        input_path=input_path,
        index_path=index_path,
        build_index_if_missing=build_index_if_missing,
    )
    return resolve_country_subgraph_seed_from_index(
        index_path,
        seed_qid=seed_qid,
        seed_name=seed_name,
        auto_select_fuzzy=auto_select_fuzzy,
    )


def _ensure_compatible_index(*, input_path: Path, index_path: Path, build_index_if_missing: bool) -> None:
    if not index_path.exists():
        if not build_index_if_missing:
            raise RuntimeError(
                f"No compatible index found at {index_path}. Run `py -m pipeline borders build-index --input {input_path} --index-path {index_path}` "
                "or pass --build-index-if-missing."
            )
        build_index(input_path, index_path=index_path, force=False)
        return

    source_fingerprint = source_fingerprint_for_file(input_path)
    try:
        metadata = read_index_metadata(index_path)
    except Exception as exc:  # pragma: no cover - defensive guard for malformed indexes.
        raise RuntimeError(
            f"Index at {index_path} is unreadable or incomplete. Rebuild it with `py -m pipeline borders build-index --input {input_path} --index-path {index_path} --force`."
        ) from exc

    if metadata.get("schema_version") != SCHEMA_VERSION or not index_matches_source(
        index_path,
        source_fingerprint_sha256=source_fingerprint,
        expected_schema_version=SCHEMA_VERSION,
    ):
        raise RuntimeError(
            f"Index at {index_path} is incompatible with {input_path}. Rebuild it with `py -m pipeline borders build-index --input {input_path} --index-path {index_path} --force`."
        )