from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from pipeline.ohm_borders.artifacts import ensure_artifact_dirs, enriched_shard_path, final_jsonl_path, parsed_dir
from pipeline.ohm_borders.enricher import batch_enrich_qids
from pipeline.ohm_borders.stage_common import (
    _collect_unique_qids,
    _load_or_create_manifest,
    _relative_artifact_path,
    _sorted_paths,
    _write_stage_update,
    resolve_artifact_dir,
    resolve_run_id,
)

logger = logging.getLogger(__name__)


def run_enrich_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    enrich_batch_size: int | None = None,
    enrich_workers: int | None = None,
    enrich_names: bool = False,
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

    logger.info(
        "enrich stage starting run_id=%s artifact_dir=%s parsed_shards=%s enrich_batch_size=%s enrich_workers=%s resume=%s force=%s",
        run_id,
        resolved_artifact_dir,
        len(parsed_paths),
        resolved_batch_size,
        resolved_workers,
        resume,
        force,
    )

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
                        logger.exception("enrich stage batch failed batch_index=%s shard=%s", batch_index, relative_path)
                        failed_shards.append(relative_path)
                        continue

                    shard_path.parent.mkdir(parents=True, exist_ok=True)
                    shard_path.write_text(
                        json.dumps(batch_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        encoding="utf-8",
                    )
                    written_shards += 1
                    logger.info(
                        "enrich stage batch completed batch_index=%s/%s shard=%s qids=%s",
                        batch_index,
                        len(batches),
                        relative_path,
                        len(batches[batch_index - 1]),
                    )

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
        logger.info(
            "enrich stage completed status=%s unique_qids=%s shards=%s written=%s skipped=%s failed=%s",
            stage_status,
            len(unique_qids),
            len(batches),
            written_shards,
            skipped_shards,
            len(failed_shards),
        )

        if enrich_names:
            logger.info("enrich stage name search starting enriched_shards=%s", len(batches))
            from pipeline.ohm_borders.enricher import enrich_output_jsonl_missing_qids

            final_path = final_jsonl_path(resolved_artifact_dir)
            if final_path.exists():
                name_enriched_path = final_path.with_name(f"{final_path.stem}.name-enriched.jsonl")
                name_result = enrich_output_jsonl_missing_qids(
                    input_path=final_path,
                    output_path=name_enriched_path,
                    batch_size=resolved_batch_size,
                )
                logger.info(
                    "enrich stage name search completed searched=%s matched=%s output=%s",
                    name_result["searched_count"],
                    name_result["matched_count"],
                    name_enriched_path,
                )

    except Exception:
        logger.exception("enrich stage failed")
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
