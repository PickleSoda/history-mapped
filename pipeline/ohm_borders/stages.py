"""Staged OHM borders fetch/parse helpers."""

from __future__ import annotations

import json
import os
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
    raw_shard_path,
    stage_done_marker_path,
    parsed_dir,
    raw_overpass_path,
)
from pipeline.ohm_borders.enricher import batch_enrich_qids
from pipeline.ohm_borders.fetcher import fetch_raw, parse_elements, parse_relation_subset
from pipeline.ohm_borders.manifest import create_manifest, load_manifest, save_manifest, update_manifest
from pipeline.ohm_borders.mapper import map_polity_to_jsonl


_WORKER_POLL_INTERVAL_SECONDS = 0.1


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
    raw_shard_size: int = 200,
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
    except Exception:
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
    resolved_parse_workers = max(1, parse_workers or default_parallelism())
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={
            "parsed_shard_size": resolved_shard_size,
            "parse_workers": resolved_parse_workers,
        },
    )
    parse_source, parse_input_paths = _resolve_parse_inputs(resolved_artifact_dir)
    parse_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in parse_input_paths]

    _write_stage_update(
        manifest_path,
        "parse",
        status="running",
        inputs=parse_inputs,
        summary={
            "parse_input_shards_total": len(parse_input_paths),
            "parse_input_shards_completed": 0,
            "parse_input_shards_active": len(parse_input_paths),
        },
    )

    stage_status = "completed"
    parsed_polity_count = 0
    parsed_shard_count = 0

    try:
        outputs: list[str] = []
        skipped_shards = 0
        written_shards = 0
        parsed_relation_inputs = 0
        pending_records: list[dict[str, Any]] = []

        overpass_elements: list[dict[str, Any]] = []
        global_relation_index: dict[int, dict[str, Any]] | None = None
        global_chronology_member_ids: set[int] | None = None
        if parse_source == "overpass":
            raw_payload = json.loads(parse_input_paths[0].read_text(encoding="utf-8"))
            raw_elements = raw_payload.get("elements", [])
            overpass_elements = raw_elements if isinstance(raw_elements, list) else []
        elif parser is parse_elements:
            global_relation_index = _build_global_relation_index(parse_input_paths)
            global_chronology_member_ids = _collect_chronology_member_ids(global_relation_index)

        def execute_parse_work(input_index: int, input_path: Path) -> tuple[int, int, list[dict[str, Any]]]:
            if parse_source == "raw_shards":
                shard_elements = _load_jsonl_records(input_path)
                shard_polities = parse_relation_subset(
                    shard_elements,
                    parser=parser,
                    relation_index=global_relation_index,
                    chronology_member_ids=global_chronology_member_ids,
                )
                relation_count = len(shard_elements)
            else:
                shard_polities = parser(overpass_elements)
                relation_count = len(_relation_elements(overpass_elements))

            return input_index, relation_count, _sort_polities(shard_polities)

        parse_futures: dict[int, Any] = {}
        max_workers = min(resolved_parse_workers, max(1, len(parse_input_paths)))

        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            for input_index, input_path in enumerate(parse_input_paths, start=1):
                parse_futures[input_index] = executor.submit(execute_parse_work, input_index, input_path)

            future_to_index = {future: index for index, future in parse_futures.items()}
            pending_futures = set(future_to_index.keys())
            completed_by_index: dict[int, tuple[int, list[dict[str, Any]]]] = {}
            completed_inputs = 0
            next_output_shard_index = 1

            while completed_inputs < len(parse_input_paths):
                done, pending_futures = wait(
                    pending_futures,
                    timeout=_WORKER_POLL_INTERVAL_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    continue

                for future in done:
                    input_index = future_to_index[future]
                    _, relation_count, parsed_polities = future.result()
                    completed_by_index[input_index] = (relation_count, parsed_polities)

                while (completed_inputs + 1) in completed_by_index:
                    next_input_index = completed_inputs + 1
                    relation_count, parsed_polities = completed_by_index.pop(next_input_index)
                    parsed_relation_inputs += relation_count
                    parsed_polity_count += len(parsed_polities)
                    pending_records.extend(parsed_polities)
                    completed_inputs = next_input_index

                    active_inputs = max(0, len(parse_input_paths) - completed_inputs)
                    _write_stage_update(
                        manifest_path,
                        "parse",
                        status="running",
                        inputs=parse_inputs,
                        summary={
                            "parse_input_shards_total": len(parse_input_paths),
                            "parse_input_shards_completed": completed_inputs,
                            "parse_input_shards_active": active_inputs,
                        },
                    )

                    while len(pending_records) >= resolved_shard_size:
                        shard_records = pending_records[:resolved_shard_size]
                        del pending_records[:resolved_shard_size]

                        shard_path = parsed_shard_path(resolved_artifact_dir, next_output_shard_index)
                        outputs.append(_relative_artifact_path(resolved_artifact_dir, shard_path))

                        if resume and shard_path.exists() and not force:
                            skipped_shards += 1
                        else:
                            _write_jsonl_atomic(shard_path, shard_records)
                            written_shards += 1

                        next_output_shard_index += 1

            if pending_records:
                shard_path = parsed_shard_path(resolved_artifact_dir, next_output_shard_index)
                outputs.append(_relative_artifact_path(resolved_artifact_dir, shard_path))

                if resume and shard_path.exists() and not force:
                    skipped_shards += 1
                else:
                    _write_jsonl_atomic(shard_path, pending_records)
                    written_shards += 1
        except Exception:
            for future in parse_futures.values():
                future.cancel()
            raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        parsed_shard_count = len(outputs)

        expected_paths = {parsed_shard_path(resolved_artifact_dir, index) for index in range(1, parsed_shard_count + 1)}
        for existing_path in _sorted_paths(parsed_dir(resolved_artifact_dir), "parsed-*.jsonl"):
            if existing_path not in expected_paths:
                existing_path.unlink()

        stage_status = "skipped" if parsed_shard_count and skipped_shards == parsed_shard_count else "completed"
        _write_stage_update(
            manifest_path,
            "parse",
            status=stage_status,
            inputs=parse_inputs,
            outputs=outputs,
            summary={
                "parsed_source": parse_source,
                "parsed_input_shards": len(parse_input_paths),
                "parsed_input_relations": parsed_relation_inputs,
                "parsed_polities": parsed_polity_count,
                "parsed_shards": parsed_shard_count,
                "parsed_shards_skipped": skipped_shards,
                "parsed_shards_written": written_shards,
                "parsed_shard_size": resolved_shard_size,
                "parse_workers": resolved_parse_workers,
                "parse_input_shards_total": len(parse_input_paths),
                "parse_input_shards_completed": len(parse_input_paths),
                "parse_input_shards_active": 0,
            },
        )
    except Exception:
        _write_stage_update(
            manifest_path,
            "parse",
            status="failed",
            inputs=parse_inputs,
        )
        raise

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "polity_count": parsed_polity_count,
        "shard_count": parsed_shard_count,
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
    build_workers: int | None = None,
    mapper: Callable[[dict[str, Any], dict[str, dict[str, Any]]], dict[str, Any]] = map_polity_to_jsonl,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={"no_enrich": no_enrich, "build_workers": build_workers},
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
        summary={
            "built_shards_total": len(parsed_paths),
            "built_shards_completed": 0,
            "built_shards_active": len(parsed_paths),
        },
    )

    try:
        wikidata_index = {} if no_enrich else _load_enrichment_index(enrichment_paths)
        built_outputs: list[str] = []
        built_shards_written = 0
        built_shards_skipped = 0
        record_count = 0
        resolved_build_workers = max(1, build_workers or default_parallelism())
        max_build_workers = min(resolved_build_workers, max(1, len(parsed_paths)))

        def execute_build_work(shard_index: int, parsed_path: Path) -> tuple[int, str, bool]:
            built_path = built_shard_path(resolved_artifact_dir, shard_index)
            relative_path = _relative_artifact_path(resolved_artifact_dir, built_path)

            if resume and built_path.exists() and not force:
                return shard_index, relative_path, False

            parsed_records = _load_jsonl_records(parsed_path)
            mapped_records = [mapper(record, wikidata_index) for record in parsed_records]
            _write_jsonl_atomic(built_path, mapped_records)
            return shard_index, relative_path, True

        build_futures: dict[int, Any] = {}
        executor = ThreadPoolExecutor(max_workers=max_build_workers)
        try:
            for shard_index, parsed_path in enumerate(parsed_paths, start=1):
                build_futures[shard_index] = executor.submit(execute_build_work, shard_index, parsed_path)

            future_to_index = {future: index for index, future in build_futures.items()}
            pending_futures = set(future_to_index.keys())
            completed_by_index: dict[int, tuple[str, bool]] = {}
            completed_shards = 0

            while completed_shards < len(parsed_paths):
                done, pending_futures = wait(
                    pending_futures,
                    timeout=_WORKER_POLL_INTERVAL_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    continue

                for future in done:
                    shard_index = future_to_index[future]
                    _, relative_path, did_write = future.result()
                    completed_by_index[shard_index] = (relative_path, did_write)

                while (completed_shards + 1) in completed_by_index:
                    next_shard_index = completed_shards + 1
                    relative_path, did_write = completed_by_index.pop(next_shard_index)
                    built_outputs.append(relative_path)
                    if did_write:
                        built_shards_written += 1
                    else:
                        built_shards_skipped += 1

                    completed_shards = next_shard_index
                    _write_stage_update(
                        manifest_path,
                        "build",
                        status="running",
                        inputs=build_inputs,
                        failed_shards=[],
                        summary={
                            "built_shards_total": len(parsed_paths),
                            "built_shards_completed": completed_shards,
                            "built_shards_active": len(parsed_paths) - completed_shards,
                        },
                    )
        except Exception:
            for future in build_futures.values():
                future.cancel()
            raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

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
                "built_shards_total": len(parsed_paths),
                "built_shards_written": built_shards_written,
                "built_shards_skipped": built_shards_skipped,
                "built_shards_completed": len(parsed_paths),
                "built_shards_active": 0,
                "build_workers": resolved_build_workers,
                "build_workers_used": max_build_workers,
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


def _resolve_parse_inputs(artifact_dir: Path) -> tuple[str, list[Path]]:
    raw_shards = _sorted_paths(artifact_dir / "raw", "raw-*.jsonl")
    if raw_shards:
        return "raw_shards", raw_shards

    raw_path = raw_overpass_path(artifact_dir)
    if raw_path.exists():
        return "overpass", [raw_path]

    raise RuntimeError(f"Raw parse artifacts not found in: {artifact_dir / 'raw'}")


def _relation_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []

    for element in elements:
        if element.get("type") != "relation" or "id" not in element:
            continue

        try:
            relation_id = int(element["id"])
        except (TypeError, ValueError):
            continue

        relations.append({**element, "id": relation_id})

    relations.sort(key=lambda relation: relation["id"])
    return relations


def _polity_sort_key(polity: dict[str, Any]) -> tuple[int, str]:
    relation_id = polity.get("relation_id")
    try:
        relation_value = int(relation_id)
    except (TypeError, ValueError):
        relation_value = 2**63 - 1

    return relation_value, str(relation_id)


def _sort_polities(polities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(polities, key=_polity_sort_key)


def _chunk_records(records: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    return [records[index:index + chunk_size] for index in range(0, len(records), chunk_size)]


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


def _write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    payload = bytearray()
    for record in records:
        payload.extend(orjson.dumps(record))
        payload.extend(b"\n")
    _write_bytes_atomic(path, bytes(payload))


def _write_text_atomic(path: Path, payload: str) -> None:
    _write_bytes_atomic(path, payload.encode("utf-8"))


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")

    with temp_path.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temp_path, path)


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


def _build_global_relation_index(raw_shard_paths: list[Path]) -> dict[int, dict[str, Any]]:
    relation_index: dict[int, dict[str, Any]] = {}

    for shard_path in raw_shard_paths:
        for relation in _load_jsonl_records(shard_path):
            if relation.get("type") != "relation" or "id" not in relation:
                continue

            try:
                relation_id = int(relation["id"])
            except (TypeError, ValueError):
                continue

            relation_index[relation_id] = {**relation, "id": relation_id}

    return relation_index


def _collect_chronology_member_ids(relation_index: dict[int, dict[str, Any]]) -> set[int]:
    member_ids: set[int] = set()

    for relation in relation_index.values():
        if relation.get("tags", {}).get("type") != "chronology":
            continue

        for member in relation.get("members", []):
            if member.get("type") != "relation" or "ref" not in member:
                continue

            try:
                member_ids.add(int(member["ref"]))
            except (TypeError, ValueError):
                continue

    return member_ids


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