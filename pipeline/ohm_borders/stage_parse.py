from __future__ import annotations

import json
import logging
import os
import pickle
import sqlite3
import tempfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable

import orjson

from pipeline.ohm_borders.artifacts import ensure_artifact_dirs, parsed_dir, parsed_shard_path
from pipeline.ohm_borders.fetcher import assemble_geometry, parse_elements, parse_relation_subset
from pipeline.ohm_borders.stage_common import (
    _WORKER_POLL_INTERVAL_SECONDS,
    _load_jsonl_records,
    _load_or_create_manifest,
    _relative_artifact_path,
    _relation_elements,
    _resolve_parse_inputs,
    _sort_polities,
    _sorted_paths,
    _write_jsonl_atomic,
    _write_stage_update,
    default_parallelism,
    resolve_artifact_dir,
    resolve_run_id,
)

logger = logging.getLogger(__name__)

_PARSE_WORKER_SOURCE = ""
_PARSE_WORKER_OVERPASS_ELEMENTS: list[dict[str, Any]] = []
_PARSE_WORKER_RELATION_DB_PATH = ""
_PARSE_WORKER_RELATION_DB_CONN: sqlite3.Connection | None = None
_PARSE_WORKER_CHRONOLOGY_MEMBER_IDS: set[int] | None = None
_PARSE_WORKER_CHRONOLOGY_WIKIDATA_IDS: set[str] | None = None


def _init_parse_worker(parse_source: str, context_path: str) -> None:
    global _PARSE_WORKER_SOURCE
    global _PARSE_WORKER_OVERPASS_ELEMENTS
    global _PARSE_WORKER_RELATION_DB_PATH
    global _PARSE_WORKER_RELATION_DB_CONN
    global _PARSE_WORKER_CHRONOLOGY_MEMBER_IDS
    global _PARSE_WORKER_CHRONOLOGY_WIKIDATA_IDS

    _PARSE_WORKER_SOURCE = parse_source
    if context_path:
        with open(context_path, "rb") as fh:
            ctx = pickle.load(fh)
        _PARSE_WORKER_OVERPASS_ELEMENTS = ctx.get("overpass_elements", [])
        _PARSE_WORKER_RELATION_DB_PATH = ctx.get("relation_db_path", "")
        _PARSE_WORKER_RELATION_DB_CONN = None
        chronology_member_ids = ctx.get("chronology_member_ids")
        _PARSE_WORKER_CHRONOLOGY_MEMBER_IDS = set(chronology_member_ids) if chronology_member_ids else set()
        chronology_wikidata_ids = ctx.get("chronology_wikidata_ids")
        _PARSE_WORKER_CHRONOLOGY_WIKIDATA_IDS = set(chronology_wikidata_ids) if chronology_wikidata_ids else set()


def _run_parse_worker(input_index: int, input_path: str) -> tuple[int, int, list[dict[str, Any]]]:
    if _PARSE_WORKER_SOURCE == "raw_shards":
        shard_elements = _load_jsonl_records(Path(input_path))
        if _PARSE_WORKER_RELATION_DB_PATH:
            shard_polities = _parse_relation_subset_with_worker_lookup(
                shard_elements,
                chronology_member_ids=_PARSE_WORKER_CHRONOLOGY_MEMBER_IDS or set(),
                chronology_wikidata_ids=_PARSE_WORKER_CHRONOLOGY_WIKIDATA_IDS or set(),
            )
        else:
            shard_polities = parse_relation_subset(shard_elements, parser=parse_elements)
        relation_count = len(shard_elements)
    else:
        shard_polities = parse_elements(_PARSE_WORKER_OVERPASS_ELEMENTS)
        relation_count = len(_relation_elements(_PARSE_WORKER_OVERPASS_ELEMENTS))

    return input_index, relation_count, _sort_polities(shard_polities)


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
    parse_progress_interval = max(1, len(parse_input_paths) // 20)

    logger.info(
        "parse stage starting run_id=%s artifact_dir=%s source=%s input_shards=%s parsed_shard_size=%s parse_workers=%s resume=%s force=%s",
        run_id,
        resolved_artifact_dir,
        parse_source,
        len(parse_input_paths),
        resolved_shard_size,
        resolved_parse_workers,
        resume,
        force,
    )

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
        global_chronology_member_ids: set[int] | None = None
        global_chronology_wikidata_ids: set[str] | None = None
        relation_db_path = ""
        if parse_source == "overpass":
            raw_payload = json.loads(parse_input_paths[0].read_text(encoding="utf-8"))
            raw_elements = raw_payload.get("elements", [])
            overpass_elements = raw_elements if isinstance(raw_elements, list) else []
        elif parser is parse_elements:
            global_chronology_member_ids = _collect_chronology_member_ids_from_raw_shards(parse_input_paths)
            global_chronology_wikidata_ids = _collect_chronology_wikidata_ids_from_raw_shards(parse_input_paths)
            relation_db_path = _build_relation_lookup_db(parse_input_paths, resolved_artifact_dir)

        use_process_pool = (
            parser is parse_elements
            and parse_source == "raw_shards"
            and len(parse_input_paths) > 1
        )

        def execute_parse_work(input_index: int, input_path: Path) -> tuple[int, int, list[dict[str, Any]]]:
            if parse_source == "raw_shards":
                shard_elements = _load_jsonl_records(input_path)
                if parser is parse_elements and relation_db_path:
                    with sqlite3.connect(relation_db_path) as relation_db_conn:
                        shard_polities = _parse_relation_subset_with_db_lookup(
                            shard_elements,
                            chronology_member_ids=global_chronology_member_ids or set(),
                            chronology_wikidata_ids=global_chronology_wikidata_ids or set(),
                            relation_db_conn=relation_db_conn,
                        )
                else:
                    shard_polities = parse_relation_subset(
                        shard_elements,
                        parser=parser,
                    )
                relation_count = len(shard_elements)
            else:
                shard_polities = parser(overpass_elements)
                relation_count = len(_relation_elements(overpass_elements))

            return input_index, relation_count, _sort_polities(shard_polities)

        parse_futures: dict[int, Any] = {}
        max_workers = min(resolved_parse_workers, max(1, len(parse_input_paths)))

        logger.info(
            "parse stage executor=%s max_workers=%s",
            "process" if use_process_pool else "thread",
            max_workers,
        )

        _parse_context_path = ""
        _parse_lookup_db_path = relation_db_path
        if use_process_pool:
            ctx = {
                "overpass_elements": overpass_elements,
                "relation_db_path": relation_db_path,
                "chronology_member_ids": global_chronology_member_ids,
                "chronology_wikidata_ids": global_chronology_wikidata_ids,
            }
            _fh = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl", prefix="ohm_parse_ctx_")
            pickle.dump(ctx, _fh, protocol=pickle.HIGHEST_PROTOCOL)
            _fh.close()
            _parse_context_path = _fh.name
            logger.info("parse stage context_file=%s size_mb=%.1f", _parse_context_path, os.path.getsize(_parse_context_path) / 1_048_576)
            executor: ProcessPoolExecutor | ThreadPoolExecutor = ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=_init_parse_worker,
                initargs=(parse_source, _parse_context_path),
            )
        else:
            executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            for input_index, input_path in enumerate(parse_input_paths, start=1):
                if use_process_pool:
                    parse_futures[input_index] = executor.submit(_run_parse_worker, input_index, str(input_path))
                else:
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

                    if completed_inputs % parse_progress_interval == 0 or completed_inputs == len(parse_input_paths):
                        logger.info(
                            "parse stage progress completed_inputs=%s/%s active_inputs=%s output_shards_written=%s output_shards_skipped=%s",
                            completed_inputs,
                            len(parse_input_paths),
                            active_inputs,
                            written_shards,
                            skipped_shards,
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
            if _parse_context_path:
                try:
                    os.unlink(_parse_context_path)
                except OSError:
                    pass
            if _parse_lookup_db_path:
                try:
                    os.unlink(_parse_lookup_db_path)
                except OSError:
                    pass

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
        logger.info(
            "parse stage completed status=%s source=%s parsed_polities=%s parsed_shards=%s written=%s skipped=%s",
            stage_status,
            parse_source,
            parsed_polity_count,
            parsed_shard_count,
            written_shards,
            skipped_shards,
        )
    except Exception:
        logger.exception("parse stage failed")
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


def _get_worker_relation_db_conn() -> sqlite3.Connection:
    global _PARSE_WORKER_RELATION_DB_CONN

    if _PARSE_WORKER_RELATION_DB_CONN is None:
        if not _PARSE_WORKER_RELATION_DB_PATH:
            raise RuntimeError("parse worker relation db is not configured")
        _PARSE_WORKER_RELATION_DB_CONN = sqlite3.connect(_PARSE_WORKER_RELATION_DB_PATH)

    return _PARSE_WORKER_RELATION_DB_CONN


def _lookup_relation_payload(
    relation_id: int,
    *,
    relation_db_conn: sqlite3.Connection,
) -> dict[str, Any] | None:
    row = relation_db_conn.execute(
        "SELECT payload FROM relations WHERE relation_id = ?",
        (relation_id,),
    ).fetchone()
    if row is None:
        return None

    payload = row[0]
    if isinstance(payload, memoryview):
        payload = payload.tobytes()
    return orjson.loads(payload)


def _parse_relation_subset_with_worker_lookup(
    elements: list[dict[str, Any]],
    *,
    chronology_member_ids: set[int],
    chronology_wikidata_ids: set[str],
) -> list[dict[str, Any]]:
    return _parse_relation_subset_with_db_lookup(
        elements,
        chronology_member_ids=chronology_member_ids,
        chronology_wikidata_ids=chronology_wikidata_ids,
        relation_db_conn=_get_worker_relation_db_conn(),
    )


def _parse_relation_subset_with_db_lookup(
    elements: list[dict[str, Any]],
    *,
    chronology_member_ids: set[int],
    chronology_wikidata_ids: set[str],
    relation_db_conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    relation_elements: list[dict[str, Any]] = []
    chronology_ids: set[int] = set()

    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") != "relation" or "id" not in element:
            continue

        try:
            relation_id = int(element["id"])
        except (TypeError, ValueError):
            continue

        relation = {**element, "id": relation_id}
        relation_elements.append(relation)
        if relation.get("tags", {}).get("type") == "chronology":
            chronology_ids.add(relation_id)

    relation_elements.sort(key=lambda relation: relation["id"])

    polities: list[dict[str, Any]] = []

    for relation in relation_elements:
        relation_id = int(relation["id"])
        if relation_id not in chronology_ids:
            continue

        stages: list[dict[str, Any]] = []
        for member in relation.get("members", []):
            if member.get("type") != "relation" or "ref" not in member:
                continue
            try:
                member_relation_id = int(member["ref"])
            except (TypeError, ValueError):
                continue

            stage_relation = _lookup_relation_payload(member_relation_id, relation_db_conn=relation_db_conn)
            if stage_relation is None:
                continue

            stages.append(
                {
                    "relation_id": member_relation_id,
                    "tags": stage_relation.get("tags", {}),
                    "geometry": assemble_geometry(stage_relation.get("members", [])),
                }
            )

        polities.append(
            {
                "relation_id": relation_id,
                "tags": relation.get("tags", {}),
                "stages": stages,
            }
        )

    for relation in relation_elements:
        relation_id = int(relation["id"])
        if relation_id in chronology_ids or relation_id in chronology_member_ids:
            continue

        tags = relation.get("tags", {})
        if tags.get("boundary") != "administrative" or tags.get("admin_level") != "2":
            continue
        wikidata_id = tags.get("wikidata")
        if isinstance(wikidata_id, str) and wikidata_id in chronology_wikidata_ids:
            continue

        geometry = assemble_geometry(relation.get("members", []))
        polities.append(
            {
                "relation_id": relation_id,
                "tags": tags,
                "stages": [
                    {
                        "relation_id": relation_id,
                        "tags": tags,
                        "geometry": geometry,
                    }
                ],
            }
        )

    return polities


def _collect_chronology_member_ids_from_raw_shards(raw_shard_paths: list[Path]) -> set[int]:
    member_ids: set[int] = set()

    for shard_path in raw_shard_paths:
        for relation in _load_jsonl_records(shard_path):
            if relation.get("type") != "relation":
                continue
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


def _collect_chronology_wikidata_ids_from_raw_shards(raw_shard_paths: list[Path]) -> set[str]:
    wikidata_ids: set[str] = set()

    for shard_path in raw_shard_paths:
        for relation in _load_jsonl_records(shard_path):
            if relation.get("type") != "relation":
                continue
            if relation.get("tags", {}).get("type") != "chronology":
                continue

            wikidata_id = relation.get("tags", {}).get("wikidata")
            if isinstance(wikidata_id, str) and wikidata_id:
                wikidata_ids.add(wikidata_id)

    return wikidata_ids


def _build_relation_lookup_db(raw_shard_paths: list[Path], artifact_dir: Path) -> str:
    lookup_dir = artifact_dir / "_tmp"
    lookup_dir.mkdir(parents=True, exist_ok=True)
    lookup_path = lookup_dir / "parse_relation_lookup.sqlite"

    if lookup_path.exists():
        lookup_path.unlink()

    with sqlite3.connect(lookup_path) as conn:
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute(
            "CREATE TABLE relations (relation_id INTEGER PRIMARY KEY, payload BLOB NOT NULL)"
        )

        for shard_path in raw_shard_paths:
            rows: list[tuple[int, bytes]] = []
            for relation in _load_jsonl_records(shard_path):
                if relation.get("type") != "relation" or "id" not in relation:
                    continue
                try:
                    relation_id = int(relation["id"])
                except (TypeError, ValueError):
                    continue

                rows.append((relation_id, orjson.dumps({**relation, "id": relation_id})))

            if rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO relations (relation_id, payload) VALUES (?, ?)",
                    rows,
                )

        conn.commit()

    logger.info(
        "parse stage relation_lookup_db=%s size_mb=%.1f",
        lookup_path,
        lookup_path.stat().st_size / 1_048_576,
    )
    return str(lookup_path)
