"""Resolve pending relationship targets by fetching them from Wikidata."""

import json
import logging
from pathlib import Path
from typing import Any

import psycopg

from pipeline.config import settings
from pipeline.wikidata.collections.egypt_fallback import (
    batch_fetch_wikidata,
    _is_egypt_domain,
    _infer_entity_type_from_properties,
)
from pipeline.wikidata.collections.artifacts import (
    collection_artifact_dir,
    entities_final_path,
    manifest_path,
    ensure_dirs,
)
from pipeline.wikidata.mapper.entity_mapper import EntityMapper
from pipeline.wikidata.dedup.deduplicator import Deduplicator

logger = logging.getLogger(__name__)


def fetch_unresolved_target_qids(
    batch_id: str | None = None,
    limit: int = 500,
    targets_file: Path | None = None,
) -> list[str]:
    """Get unresolved target QIDs from database or file."""
    if targets_file is not None:
        return _load_targets_from_file(targets_file, limit)
    return _load_targets_from_db(batch_id, limit)


def _load_targets_from_file(path: Path, limit: int) -> list[str]:
    """Load target QIDs from a text file (one QID per line)."""
    qids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        qid = line.strip()
        if qid and qid.startswith("Q"):
            qids.append(qid)
            if len(qids) >= limit:
                break
    return qids


def _load_targets_from_db(batch_id: str | None, limit: int) -> list[str]:
    """Query pipeline_relationship_hints for unresolved target QIDs."""
    conn = psycopg.connect(settings.database_url)
    try:
        with conn.cursor() as cur:
            query = """
                SELECT DISTINCT target_wikidata_id
                FROM pipeline_relationship_hints
                WHERE resolved = false
                  AND resolution_note = 'target_not_found'
            """
            params: list[Any] = []
            if batch_id:
                query += " AND batch_id = %s"
                params.append(batch_id)
            query += " ORDER BY target_wikidata_id"
            query += " LIMIT %s"
            params.append(limit)

            cur.execute(query, params)
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def resolve_pending_targets(
    batch_id: str | None = None,
    limit: int = 500,
    egypt_only: bool = True,
    targets_file: Path | None = None,
) -> dict[str, Any]:
    """Fetch unresolved targets from Wikidata and write importer-ready JSONL.

    Returns summary dict with counts.
    """
    target_qids = fetch_unresolved_target_qids(batch_id=batch_id, limit=limit, targets_file=targets_file)
    if not target_qids:
        return {"status": "empty", "target_count": 0, "entity_count": 0}

    logger.info(f"Fetched {len(target_qids)} unresolved target QIDs from DB")

    raw = batch_fetch_wikidata(target_qids)
    logger.info(f"Fetched {len(raw)} entities from Wikidata")

    mapper = EntityMapper()
    records: list[dict[str, Any]] = []
    skipped_egypt = 0
    skipped_map = 0

    for qid, item in raw.items():
        if egypt_only and not _is_egypt_domain(item):
            skipped_egypt += 1
            continue

        entity_type = _infer_entity_type_from_properties(item)
        mapped = mapper.map(item, entity_type)
        if mapped is None:
            skipped_map += 1
            continue

        records.append(mapped)

    deduplicator = Deduplicator()
    deduped = deduplicator.deduplicate(records)

    return {
        "status": "completed",
        "target_count": len(target_qids),
        "fetched_count": len(raw),
        "entity_count": len(deduped),
        "skipped_egypt": skipped_egypt,
        "skipped_map": skipped_map,
        "records": deduped,
    }


def write_resolved_entities(
    artifact_dir: Path,
    records: list[dict[str, Any]],
    batch_id: str | None = None,
) -> None:
    """Write resolved entities to JSONL for import."""
    ensure_dirs(artifact_dir)

    path = entities_final_path(artifact_dir)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "run_id": artifact_dir.name,
        "artifact_dir": str(artifact_dir),
        "source_batch_id": batch_id,
        "entity_count": len(records),
    }
    with open(manifest_path(artifact_dir), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote {len(records)} entities to {path}")
