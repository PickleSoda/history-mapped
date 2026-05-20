from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.ohm_borders.artifacts import (
    ensure_artifact_dirs,
    final_jsonl_path,
    parsed_dir,
    relation_candidates_dir,
    relation_candidates_shard_path,
    relation_enriched_shard_path,
    relation_entities_final_path,
    relation_hints_final_path,
    subgraph_closure_report_path,
)
from pipeline.ohm_borders.enricher import batch_enrich_qids
from pipeline.ohm_borders.relations_enricher import enrich_relation_candidates
from pipeline.ohm_borders.relations_extractor import extract_relation_candidates
from pipeline.ohm_borders.subgraph_extractor import validate_bundle_closure
from pipeline.ohm_borders.stage_common import (
    _count_jsonl_records,
    _load_jsonl_records,
    _load_or_create_manifest,
    _relative_artifact_path,
    _sorted_paths,
    _string_or_none,
    _write_jsonl_atomic,
    _write_relation_stage_update,
    _write_text_atomic,
    resolve_artifact_dir,
    resolve_run_id,
)


def _update_subgraph_bundle_validation(artifact_dir: Path) -> None:
    closure_report_path = subgraph_closure_report_path(artifact_dir)
    main_entities_path = final_jsonl_path(artifact_dir)
    relation_entities_path = relation_entities_final_path(artifact_dir)
    relation_hints_path = relation_hints_final_path(artifact_dir)

    if not closure_report_path.exists() or not main_entities_path.exists():
        return
    if not relation_entities_path.exists() or not relation_hints_path.exists():
        return

    closure_report = json.loads(closure_report_path.read_text(encoding="utf-8"))
    closure_report["bundle_validation"] = validate_bundle_closure(
        main_entities=_load_jsonl_records(main_entities_path),
        relation_entities=_load_jsonl_records(relation_entities_path),
        relation_hints=_load_jsonl_records(relation_hints_path),
    )
    _write_text_atomic(closure_report_path, json.dumps(closure_report, ensure_ascii=True, indent=2))


def run_relations_scan_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={},
    )

    parsed_paths = _sorted_paths(parsed_dir(resolved_artifact_dir), "parsed-*.jsonl")
    if not parsed_paths:
        raise RuntimeError(f"Parsed shard artifacts not found in: {parsed_dir(resolved_artifact_dir)}")

    relation_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in parsed_paths]
    _write_relation_stage_update(
        manifest_path,
        "scan",
        status="running",
        inputs=relation_inputs,
    )

    outputs: list[str] = []
    candidate_count = 0
    written_shards = 0

    for shard_index, parsed_path in enumerate(parsed_paths, start=1):
        output_path = relation_candidates_shard_path(resolved_artifact_dir, shard_index)
        outputs.append(_relative_artifact_path(resolved_artifact_dir, output_path))

        if resume and output_path.exists() and not force:
            candidate_count += _count_jsonl_records(output_path)
            continue

        shard_candidates: list[dict[str, Any]] = []
        for polity in _load_jsonl_records(parsed_path):
            shard_candidates.extend(extract_relation_candidates(polity))

        _write_jsonl_atomic(output_path, shard_candidates)
        candidate_count += len(shard_candidates)
        written_shards += 1

    stage_status = "skipped" if written_shards == 0 and resume else "completed"
    _write_relation_stage_update(
        manifest_path,
        "scan",
        status=stage_status,
        inputs=relation_inputs,
        outputs=outputs,
        summary={
            "relation_candidate_shards": len(parsed_paths),
            "relation_candidates": candidate_count,
        },
    )

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "candidate_count": candidate_count,
        "shard_count": len(parsed_paths),
        "output_dir": relation_candidates_dir(resolved_artifact_dir),
    }


def run_relations_enrich_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    resume: bool = False,
    force: bool = False,
    metadata_fetcher: Any = batch_enrich_qids,
    name_searcher: Any = None,
    wikipedia_enricher: Any | None = None,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={},
    )

    candidate_paths = _sorted_paths(relation_candidates_dir(resolved_artifact_dir), "relations-candidates-*.jsonl")
    if not candidate_paths:
        raise RuntimeError(f"Relation candidate artifacts not found in: {relation_candidates_dir(resolved_artifact_dir)}")

    relation_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in candidate_paths]
    _write_relation_stage_update(
        manifest_path,
        "enrich",
        status="running",
        inputs=relation_inputs,
    )

    outputs: list[str] = []
    enriched_candidate_count = 0
    written_shards = 0

    for shard_index, candidate_path in enumerate(candidate_paths, start=1):
        output_path = relation_enriched_shard_path(resolved_artifact_dir, shard_index)
        outputs.append(_relative_artifact_path(resolved_artifact_dir, output_path))

        if resume and output_path.exists() and not force:
            enriched_candidate_count += len(json.loads(output_path.read_text(encoding="utf-8")))
            continue

        candidates = _load_jsonl_records(candidate_path)
        enriched = enrich_relation_candidates(
            candidates,
            metadata_fetcher=metadata_fetcher,
            name_searcher=name_searcher,
            wikipedia_enricher=wikipedia_enricher,
        )

        _write_text_atomic(output_path, json.dumps(enriched, ensure_ascii=True, indent=2))
        enriched_candidate_count += len(enriched)
        written_shards += 1

    stage_status = "skipped" if written_shards == 0 and resume else "completed"
    _write_relation_stage_update(
        manifest_path,
        "enrich",
        status=stage_status,
        inputs=relation_inputs,
        outputs=outputs,
        summary={
            "relation_enriched_shards": len(candidate_paths),
            "relation_enriched_candidates": enriched_candidate_count,
        },
    )

    return {
        "status": stage_status,
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "candidate_count": enriched_candidate_count,
        "shard_count": len(candidate_paths),
    }


def run_relations_build_stage(
    *,
    run_id: str | None = None,
    artifact_dir: str | Path | None = None,
    resume: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    resolved_artifact_dir = resolve_artifact_dir(run_id=run_id, artifact_dir=artifact_dir)
    ensure_artifact_dirs(resolved_artifact_dir)

    resolved_run_id = resolve_run_id(run_id=run_id, artifact_dir=resolved_artifact_dir)
    manifest_path = _load_or_create_manifest(
        run_id=resolved_run_id,
        artifact_dir=resolved_artifact_dir,
        options={},
    )

    enriched_paths = _sorted_paths(resolved_artifact_dir / "relations_enriched", "relations-enriched-*.json")
    if not enriched_paths:
        raise RuntimeError(f"Relation enriched artifacts not found in: {resolved_artifact_dir / 'relations_enriched'}")

    relation_inputs = [_relative_artifact_path(resolved_artifact_dir, path) for path in enriched_paths]
    _write_relation_stage_update(manifest_path, "build", status="running", inputs=relation_inputs)

    entities_path = relation_entities_final_path(resolved_artifact_dir)
    hints_path = relation_hints_final_path(resolved_artifact_dir)

    if resume and entities_path.exists() and hints_path.exists() and not force:
        _update_subgraph_bundle_validation(resolved_artifact_dir)
        entity_count = _count_jsonl_records(entities_path)
        hint_count = _count_jsonl_records(hints_path)
        _write_relation_stage_update(
            manifest_path,
            "build",
            status="skipped",
            inputs=relation_inputs,
            outputs=[
                _relative_artifact_path(resolved_artifact_dir, entities_path),
                _relative_artifact_path(resolved_artifact_dir, hints_path),
            ],
            summary={
                "relation_final_entities": entity_count,
                "relation_final_hints": hint_count,
            },
        )
        return {
            "status": "skipped",
            "artifact_dir": resolved_artifact_dir,
            "manifest_path": manifest_path,
            "entity_count": entity_count,
            "hint_count": hint_count,
            "entities_path": entities_path,
            "hints_path": hints_path,
        }

    entity_records: dict[str, dict[str, Any]] = {}
    hint_records: dict[tuple[str, str | None, str | None, str | None, str | None], dict[str, Any]] = {}

    for enriched_path in enriched_paths:
        for record in json.loads(enriched_path.read_text(encoding="utf-8")):
            target_entity = record.get("target_entity") or {}
            entity_key = str(target_entity.get("wikidata_id") or target_entity.get("name") or "")
            if entity_key and entity_key not in entity_records:
                entity_records[entity_key] = target_entity

            hint_key = (
                str(record.get("source_wikidata_id") or ""),
                _string_or_none(record.get("target_wikidata_id")),
                _string_or_none(record.get("relationship_type")),
                _string_or_none(record.get("temporal_start")),
                _string_or_none(record.get("temporal_end")),
            )
            hint_records[hint_key] = {
                "source_wikidata_id": record.get("source_wikidata_id"),
                "source_name": record.get("source_name"),
                "relationship_type": record.get("relationship_type"),
                "target_wikidata_id": record.get("target_wikidata_id"),
                "target_label": record.get("target_label"),
                "temporal_start": record.get("temporal_start"),
                "temporal_end": record.get("temporal_end"),
                "confidence": "medium",
                "source": record.get("source"),
            }

    _write_jsonl_atomic(entities_path, list(entity_records.values()))
    _write_jsonl_atomic(hints_path, list(hint_records.values()))
    _update_subgraph_bundle_validation(resolved_artifact_dir)

    _write_relation_stage_update(
        manifest_path,
        "build",
        status="completed",
        inputs=relation_inputs,
        outputs=[
            _relative_artifact_path(resolved_artifact_dir, entities_path),
            _relative_artifact_path(resolved_artifact_dir, hints_path),
        ],
        summary={
            "relation_final_entities": len(entity_records),
            "relation_final_hints": len(hint_records),
        },
    )

    return {
        "status": "completed",
        "artifact_dir": resolved_artifact_dir,
        "manifest_path": manifest_path,
        "entity_count": len(entity_records),
        "hint_count": len(hint_records),
        "entities_path": entities_path,
        "hints_path": hints_path,
    }
