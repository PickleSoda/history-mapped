"""Staged OHM borders fetch/parse helpers."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import orjson

from pipeline.ohm_borders.artifacts import (
    artifact_dir_for_run,
    built_shard_path,
    ensure_artifact_dirs,
    enriched_dir,
    enriched_shard_path,
    final_jsonl_path,
    parsed_shard_path,
    parsed_dir,
    raw_overpass_path,
)
from pipeline.ohm_borders.enricher import batch_enrich_qids
from pipeline.ohm_borders.fetcher import fetch_raw, parse_elements
from pipeline.ohm_borders.manifest import create_manifest, load_manifest, save_manifest, update_manifest
from pipeline.ohm_borders.mapper import map_polity_to_jsonl


def default_parallelism() -> int:
    cpu_total = os.cpu_count() or 1
    return max(1, cpu_total - 1)


def resolve_run_id(run_id: str | None = None, artifact_dir: str | Path | None = None) -> str:
    if run_id:
        return run_id
    if artifact_dir is not None:
        return Path(artifact_dir).name
    raise ValueError("run_id or artifact_dir is required")


def resolve_artifact_dir(run_id: str | None = None, artifact_dir: str | Path | None = None) -> Path:
    if artifact_dir is not None:
        return Path(artifact_dir)
    return artifact_dir_for_run(resolve_run_id(run_id=run_id, artifact_dir=artifact_dir))


def manifest_path_for(artifact_dir: str | Path) -> Path:
    return Path(artifact_dir) / "manifest.json"


def plan_parsed_shards(polities: list[dict[str, Any]], shard_size: int) -> list[list[dict[str, Any]]]:
    if shard_size < 1:
        raise ValueError("parsed_shard_size must be >= 1")

    return [polities[index:index + shard_size] for index in range(0, len(polities), shard_size)]


def run_fetch_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    query: str,
    resume: bool = False,
    force: bool = False,
    fetcher: Callable[[str], dict[str, Any]] = fetch_raw,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={},
    )
    raw_path = raw_overpass_path(resolved_artifact_dir)

    if resume and raw_path.exists() and not force:
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        element_count = len(raw_payload.get("elements", []))
        _write_stage_update(
            manifest_path,
            "fetch",
            status="skipped",
            inputs=["query"],
            outputs=[_relative_artifact_path(resolved_artifact_dir, raw_path)],
            summary={"raw_elements": element_count},
        )
        return {
            "status": "skipped",
            "artifact_dir": resolved_artifact_dir,
            "manifest_path": manifest_path,
            "raw_path": raw_path,
            "element_count": element_count,
        }

    _write_stage_update(manifest_path, "fetch", status="running", inputs=["query"])

    try:
        raw_payload = fetcher(query)
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        element_count = len(raw_payload.get("elements", []))

        _write_stage_update(
            manifest_path,
            "fetch",
            status="completed",
            inputs=["query"],
            outputs=[_relative_artifact_path(resolved_artifact_dir, raw_path)],
            summary={"raw_elements": element_count},
        )
    except Exception:
        _write_stage_update(manifest_path, "fetch", status="failed", inputs=["query"])
        raise

    return {
        "status": "completed",
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "raw_path": raw_path,
        "element_count": element_count,
    }


def run_parse_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    parsed_shard_size: int | None = None,
    parse_workers: int | None = None,
    resume: bool = False,
    force: bool = False,
    parser: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] = parse_elements,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    resolved_shard_size = parsed_shard_size or 100
    resolved_parse_workers = parse_workers or default_parallelism()
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={
            "parsed_shard_size": resolved_shard_size,
            "parse_workers": resolved_parse_workers,
        },
    )
    raw_path = raw_overpass_path(resolved_artifact_dir)
    if not raw_path.exists():
        raise RuntimeError(f"Raw overpass artifact not found: {raw_path}")

    _write_stage_update(
        manifest_path,
        "parse",
        status="running",
        inputs=[_relative_artifact_path(resolved_artifact_dir, raw_path)],
    )

    try:
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
        polities = parser(raw_payload.get("elements", []))
        shards = plan_parsed_shards(polities, resolved_shard_size)

        outputs: list[str] = []
        skipped_shards = 0
        written_shards = 0

        for shard_index, shard_records in enumerate(shards, start=1):
            shard_path = parsed_shard_path(resolved_artifact_dir, shard_index)
            outputs.append(_relative_artifact_path(resolved_artifact_dir, shard_path))

            if resume and shard_path.exists() and not force:
                skipped_shards += 1
                continue

            shard_path.parent.mkdir(parents=True, exist_ok=True)
            with shard_path.open("wb") as handle:
                for polity in shard_records:
                    handle.write(orjson.dumps(polity) + b"\n")
            written_shards += 1

        stage_status = "skipped" if shards and skipped_shards == len(shards) else "completed"
        _write_stage_update(
            manifest_path,
            "parse",
            status=stage_status,
            inputs=[_relative_artifact_path(resolved_artifact_dir, raw_path)],
            outputs=outputs,
            summary={
                "parsed_polities": len(polities),
                "parsed_shards": len(shards),
                "parsed_shards_skipped": skipped_shards,
                "parsed_shards_written": written_shards,
                "parsed_shard_size": resolved_shard_size,
                "parse_workers": resolved_parse_workers,
            },
        )
    except Exception:
        _write_stage_update(
            manifest_path,
            "parse",
            status="failed",
            inputs=[_relative_artifact_path(resolved_artifact_dir, raw_path)],
        )
        raise

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "polity_count": len(polities),
        "shard_count": len(shards),
    }


def run_enrich_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    enrich_batch_size: int | None = None,
    enrich_workers: int | None = None,
    resume: bool = False,
    force: bool = False,
    enricher: Callable[[list[str], int], dict[str, dict[str, Any]]] = batch_enrich_qids,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    resolved_batch_size = enrich_batch_size or 50
    resolved_workers = max(1, enrich_workers or 4)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={
            "enrich_batch_size": resolved_batch_size,
            "enrich_workers": resolved_workers,
        },
    )

    parsed_paths = _sorted_paths(parsed_dir(resolved_artifact_dir), "parsed-*.jsonl")
    if not parsed_paths:
        raise RuntimeError(f"Parsed shard artifacts not found in: {parsed_dir(resolved_artifact_dir)}")

    parsed_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in parsed_paths]
    _write_stage_update(
        manifest_path,
        "enrich",
        status="running",
        inputs=parsed_inputs,
        failed_shards=[],
    )

    try:
        unique_qids = _collect_unique_qids(parsed_paths)
        batches = [unique_qids[index:index + resolved_batch_size] for index in range(0, len(unique_qids), resolved_batch_size)]

        outputs: list[str] = []
        failed_shards: list[str] = []
        written_shards = 0
        skipped_shards = 0

        def execute_batch(batch_index: int, qids: list[str]) -> tuple[int, list[str], dict[str, dict[str, Any]]]:
            return batch_index, qids, enricher(qids, resolved_batch_size)

        pending_batches: list[tuple[int, list[str], Path, str]] = []

        for batch_index, qids in enumerate(batches, start=1):
            shard_path = enriched_shard_path(resolved_artifact_dir, batch_index)
            relative_path = _relative_artifact_path(resolved_artifact_dir, shard_path)
            outputs.append(relative_path)

            if resume and shard_path.exists() and not force:
                skipped_shards += 1
                continue

            pending_batches.append((batch_index, qids, shard_path, relative_path))

        if pending_batches:
            with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
                futures = [
                    (batch_index, shard_path, relative_path, executor.submit(execute_batch, batch_index, qids))
                    for batch_index, qids, shard_path, relative_path in pending_batches
                ]

                for batch_index, shard_path, relative_path, future in sorted(futures, key=lambda item: item[0]):
                    try:
                        _, _, batch_payload = future.result()
                    except Exception:
                        failed_shards.append(relative_path)
                        continue

                    shard_path.parent.mkdir(parents=True, exist_ok=True)
                    shard_path.write_text(
                        json.dumps(batch_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    written_shards += 1

        stage_status = "skipped" if batches and skipped_shards == len(batches) else "completed"
        _write_stage_update(
            manifest_path,
            "enrich",
            status=stage_status,
            inputs=parsed_inputs,
            outputs=[output for output in outputs if output not in failed_shards],
            failed_shards=failed_shards,
            summary={
                "enrich_unique_qids": len(unique_qids),
                "enrich_shards": len(batches),
                "enrich_shards_written": written_shards,
                "enrich_shards_skipped": skipped_shards,
                "enrich_batch_size": resolved_batch_size,
                "enrich_workers": resolved_workers,
            },
        )
    except Exception:
        _write_stage_update(
            manifest_path,
            "enrich",
            status="failed",
            inputs=parsed_inputs,
            failed_shards=[],
        )
        raise

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "qid_count": len(unique_qids),
        "shard_count": len(batches),
    }


def run_build_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    resume: bool = False,
    force: bool = False,
    no_enrich: bool = False,
    mapper: Callable[[dict[str, Any], dict[str, dict[str, Any]]], dict[str, Any]] = map_polity_to_jsonl,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={"no_enrich": no_enrich},
    )

    parsed_paths = _sorted_paths(parsed_dir(resolved_artifact_dir), "parsed-*.jsonl")
    if not parsed_paths:
        raise RuntimeError(f"Parsed shard artifacts not found in: {parsed_dir(resolved_artifact_dir)}")

    enrichment_paths = [] if no_enrich else _sorted_paths(enriched_dir(resolved_artifact_dir), "enriched-qids-*.json")
    build_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in parsed_paths]
    build_inputs.extend(_relative_artifact_path(resolved_artifact_dir, path) for path in enrichment_paths)

    _write_stage_update(
        manifest_path,
        "build",
        status="running",
        inputs=build_inputs,
        failed_shards=[],
    )

    try:
        wikidata_index = {} if no_enrich else _load_enrichment_index(enrichment_paths)
        built_outputs: list[str] = []
        built_shards_written = 0
        built_shards_skipped = 0
        record_count = 0

        for shard_index, parsed_path in enumerate(parsed_paths, start=1):
            built_path = built_shard_path(resolved_artifact_dir, shard_index)
            built_outputs.append(_relative_artifact_path(resolved_artifact_dir, built_path))

            if resume and built_path.exists() and not force:
                built_shards_skipped += 1
                continue

            parsed_records = _load_jsonl_records(parsed_path)
            mapped_records = [mapper(record, wikidata_index) for record in parsed_records]

            built_path.parent.mkdir(parents=True, exist_ok=True)
            with built_path.open("wb") as handle:
                for mapped_record in mapped_records:
                    handle.write(orjson.dumps(mapped_record) + b"\n")

            built_shards_written += 1

        final_path = final_jsonl_path(resolved_artifact_dir)
        final_relative_path = _relative_artifact_path(resolved_artifact_dir, final_path)
        should_write_final = force or built_shards_written > 0 or not final_path.exists() or not resume

        if should_write_final:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            record_count = _assemble_final_jsonl(resolved_artifact_dir, parsed_paths, final_path)
        else:
            record_count = _count_jsonl_records(final_path)

        stage_status = "skipped" if built_shards_written == 0 and not should_write_final else "completed"
        _write_stage_update(
            manifest_path,
            "build",
            status=stage_status,
            inputs=build_inputs,
            outputs=built_outputs + [final_relative_path],
            failed_shards=[],
            summary={
                "built_shards": len(parsed_paths),
                "built_shards_written": built_shards_written,
                "built_shards_skipped": built_shards_skipped,
                "build_records": record_count,
                "build_no_enrich": no_enrich,
            },
        )
    except Exception:
        _write_stage_update(
            manifest_path,
            "build",
            status="failed",
            inputs=build_inputs,
            failed_shards=[],
        )
        raise

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "record_count": record_count,
        "final_path": final_path,
    }


def _load_or_create_manifest(run_id: str, artifact_dir: Path, options: dict[str, Any]) -> Path:
    manifest_path = manifest_path_for(artifact_dir)
    if manifest_path.exists():
        manifest = load_manifest(manifest_path)
        manifest["options"].update(options)
    else:
        manifest = create_manifest(run_id=run_id, artifact_dir=artifact_dir, options=options)

    save_manifest(manifest_path, manifest)
    return manifest_path


def _relative_artifact_path(artifact_dir: Path, artifact_path: Path) -> str:
    return artifact_path.relative_to(artifact_dir).as_posix()


def _sorted_paths(directory: Path, pattern: str) -> list[Path]:
    return sorted(directory.glob(pattern))


def _load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as handle:
        return [orjson.loads(line) for line in handle if line.strip()]


def _collect_unique_qids(parsed_paths: list[Path]) -> list[str]:
    qids: set[str] = set()

    for parsed_path in parsed_paths:
        for record in _load_jsonl_records(parsed_path):
            qid = record.get("tags", {}).get("wikidata")
            if qid:
                qids.add(qid)

    return sorted(qids)


def _load_enrichment_index(enrichment_paths: list[Path]) -> dict[str, dict[str, Any]]:
    wikidata_index: dict[str, dict[str, Any]] = {}

    for enrichment_path in enrichment_paths:
        wikidata_index.update(json.loads(enrichment_path.read_text(encoding="utf-8")))

    return wikidata_index


def _assemble_final_jsonl(artifact_dir: Path, parsed_paths: list[Path], final_path: Path) -> int:
    record_count = 0

    with final_path.open("wb") as destination:
        for shard_index, _ in enumerate(parsed_paths, start=1):
            built_path = built_shard_path(artifact_dir, shard_index)
            if not built_path.exists():
                continue

            with built_path.open("rb") as source:
                for line in source:
                    if not line.strip():
                        continue
                    destination.write(line)
                    record_count += 1

    return record_count


def _count_jsonl_records(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_stage_update(
    manifest_path: Path,
    stage_name: str,
    *,
    status: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    failed_shards: list[str] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def apply(current: dict[str, Any]) -> dict[str, Any]:
        stage = dict(current["stages"][stage_name])
        started_at = stage.get("started_at") or _timestamp()

        next_inputs = stage.get("inputs", []) if inputs is None else list(inputs)
        next_outputs = stage.get("outputs", []) if outputs is None else list(outputs)
        next_failed_shards = stage.get("failed_shards", []) if failed_shards is None else list(failed_shards)

        stage.update(
            {
                "status": status,
                "inputs": next_inputs,
                "outputs": next_outputs,
                "failed_shards": next_failed_shards,
                "started_at": started_at,
                "finished_at": None if status == "running" else _timestamp(),
            }
        )

        return {
            **current,
            "summary": {**current.get("summary", {}), **(summary or {})},
            "stages": {
                **current["stages"],
                stage_name: stage,
            },
        }

    return update_manifest(manifest_path, apply)