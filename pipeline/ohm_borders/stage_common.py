from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson

from pipeline.ohm_borders.artifacts import artifact_dir_for_run, built_shard_path, raw_overpass_path
from pipeline.ohm_borders.manifest import create_manifest, load_manifest, save_manifest, update_manifest

_WORKER_POLL_INTERVAL_SECONDS = 0.1
logger = logging.getLogger(__name__)


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


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


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


def _write_relation_stage_update(
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
        stage = dict(current["relation_stages"][stage_name])
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
            "relation_stages": {
                **current["relation_stages"],
                stage_name: stage,
            },
        }

    return update_manifest(manifest_path, apply)
