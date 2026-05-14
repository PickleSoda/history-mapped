from __future__ import annotations

import logging
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable

from pipeline.ohm_borders.artifacts import built_shard_path, enriched_dir, ensure_artifact_dirs, final_jsonl_path, parsed_dir
from pipeline.ohm_borders.mapper import map_polity_to_jsonl
from pipeline.ohm_borders.stage_common import (
    _WORKER_POLL_INTERVAL_SECONDS,
    _assemble_final_jsonl,
    _count_jsonl_records,
    _load_enrichment_index,
    _load_jsonl_records,
    _load_or_create_manifest,
    _relative_artifact_path,
    _sorted_paths,
    _write_jsonl_atomic,
    _write_stage_update,
    default_parallelism,
    resolve_artifact_dir,
    resolve_run_id,
)

logger = logging.getLogger(__name__)

_BUILD_WORKER_ARTIFACT_DIR = ""
_BUILD_WORKER_RESUME = False
_BUILD_WORKER_FORCE = False
_BUILD_WORKER_WIKIDATA_INDEX: dict[str, dict[str, Any]] = {}


def _init_build_worker(
    artifact_dir: str,
    resume: bool,
    force: bool,
    wikidata_index: dict[str, dict[str, Any]],
) -> None:
    global _BUILD_WORKER_ARTIFACT_DIR
    global _BUILD_WORKER_RESUME
    global _BUILD_WORKER_FORCE
    global _BUILD_WORKER_WIKIDATA_INDEX

    _BUILD_WORKER_ARTIFACT_DIR = artifact_dir
    _BUILD_WORKER_RESUME = resume
    _BUILD_WORKER_FORCE = force
    _BUILD_WORKER_WIKIDATA_INDEX = wikidata_index


def _run_build_worker(shard_index: int, parsed_path: str) -> tuple[int, str, bool]:
    artifact_dir = Path(_BUILD_WORKER_ARTIFACT_DIR)
    built_path = built_shard_path(artifact_dir, shard_index)
    relative_path = _relative_artifact_path(artifact_dir, built_path)

    if _BUILD_WORKER_RESUME and built_path.exists() and not _BUILD_WORKER_FORCE:
        return shard_index, relative_path, False

    parsed_records = _load_jsonl_records(Path(parsed_path))
    mapped_records = [map_polity_to_jsonl(record, _BUILD_WORKER_WIKIDATA_INDEX) for record in parsed_records]
    _write_jsonl_atomic(built_path, mapped_records)
    return shard_index, relative_path, True


def run_build_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    resume: bool = False,
    force: bool = False,
    build_workers: int | None = None,
    mapper: Callable[[dict[str, Any], dict[str, dict[str, Any]]], dict[str, Any]] = map_polity_to_jsonl,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={"build_workers": build_workers},
    )

    parsed_paths = _sorted_paths(parsed_dir(resolved_artifact_dir), "parsed-*.jsonl")
    if not parsed_paths:
        raise RuntimeError(f"Parsed shard artifacts not found in: {parsed_dir(resolved_artifact_dir)}")

    logger.info(
        "build stage starting run_id=%s artifact_dir=%s parsed_shards=%s build_workers=%s resume=%s force=%s",
        run_id,
        resolved_artifact_dir,
        len(parsed_paths),
        build_workers,
        resume,
        force,
    )

    enrichment_paths = _sorted_paths(enriched_dir(resolved_artifact_dir), "enriched-qids-*.json")
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
        wikidata_index = _load_enrichment_index(enrichment_paths)
        built_outputs: list[str] = []
        built_shards_written = 0
        built_shards_skipped = 0
        record_count = 0
        resolved_build_workers = max(1, build_workers or default_parallelism())
        max_build_workers = min(resolved_build_workers, max(1, len(parsed_paths)))
        build_progress_interval = max(1, len(parsed_paths) // 20)
        use_process_pool = mapper is map_polity_to_jsonl and len(parsed_paths) > 1

        logger.info(
            "build stage executor=%s max_workers=%s",
            "process" if use_process_pool else "thread",
            max_build_workers,
        )

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
        if use_process_pool:
            executor: ProcessPoolExecutor | ThreadPoolExecutor = ProcessPoolExecutor(
                max_workers=max_build_workers,
                initializer=_init_build_worker,
                initargs=(
                    str(resolved_artifact_dir),
                    resume,
                    force,
                    wikidata_index,
                ),
            )
        else:
            executor = ThreadPoolExecutor(max_workers=max_build_workers)
        try:
            for shard_index, parsed_path in enumerate(parsed_paths, start=1):
                if use_process_pool:
                    build_futures[shard_index] = executor.submit(_run_build_worker, shard_index, str(parsed_path))
                else:
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

                    if completed_shards % build_progress_interval == 0 or completed_shards == len(parsed_paths):
                        logger.info(
                            "build stage progress completed_shards=%s/%s active_shards=%s written=%s skipped=%s",
                            completed_shards,
                            len(parsed_paths),
                            len(parsed_paths) - completed_shards,
                            built_shards_written,
                            built_shards_skipped,
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
            },
        )
        logger.info(
            "build stage completed status=%s built_shards=%s written=%s skipped=%s final_records=%s",
            stage_status,
            len(parsed_paths),
            built_shards_written,
            built_shards_skipped,
            record_count,
        )
    except Exception:
        logger.exception("build stage failed")
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
