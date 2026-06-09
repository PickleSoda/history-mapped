from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

import click
import requests
from rich.console import Console

from pipeline.ohm_collections.collection_builder import build_collection_artifacts
from pipeline.ohm_collections.entity_enricher import enrich_candidate
from pipeline.ohm_collections.egypt_rules import evaluate_candidate
from pipeline.ohm_collections.point_resolver import resolve_best_point
from pipeline.ohm_collections.xml_index_builder import build_index
from pipeline.ohm_borders.relations_enricher import enrich_relation_candidates
from pipeline.ohm_borders.relations_extractor import extract_relation_candidates
from pipeline.wikidata.mapper.relationship_mapper import get_relationship_type
from pipeline.wikidata.collections.egypt_seed_set import load_seed_set
from pipeline.wikidata.collections.egypt_fallback import (
    fetch_seed_entities,
    apply_bounded_expansion,
    build_collection_artifacts as build_egypt_collection_artifacts,
)
from pipeline.wikidata.collections.artifacts import collection_artifact_dir
from pipeline.wikidata.collections.resolve_pending import (
    resolve_pending_targets,
    write_resolved_entities,
)

console = Console(legacy_windows=False)

_WIKIDATA_RELATION_PROPERTIES: tuple[str, ...] = (
    "P155",  # preceded_by
    "P156",  # succeeded_by
    "P828",  # has_cause -> resulted_from
    "P1542", # has_effect -> caused
    "P131",  # part_of
    "P361",  # part_of
    "P527",  # contains
    "P17",   # part_of
)


def _default_output_root(run_id: str) -> Path:
    return Path("output") / "ohm_collections" / run_id


def run_egypt_build(
    *,
    xml_index_path: Path,
    ohm_index_path: Path | None,
    run_id: str,
    output_root: Path | None,
    resume: bool,
    force: bool,
    candidate_enricher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, object]:
    del ohm_index_path

    resolved_output_root = output_root or _default_output_root(run_id)
    manifest_path = resolved_output_root / "manifest.json"
    if resume and manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "status": "skipped",
            "output_root": resolved_output_root,
            "manifest_path": manifest_path,
            "manifest": manifest,
        }

    included_candidates: list[dict[str, Any]] = []
    excluded_candidates: list[dict[str, Any]] = []

    for candidate in _load_index_candidates(xml_index_path):
        decision = evaluate_candidate(candidate)
        candidate["decision"] = {
            "reasons": decision["reasons"],
            "ambiguity": decision["ambiguity"],
        }
        candidate["point_resolution"] = resolve_best_point(
            xml_index_path,
            object_type=str(candidate["_ohm_object_type"]),
            object_id=int(candidate["_ohm_object_id"]),
        )
        candidate["fallback_geojson"] = None

        if decision["include"]:
            if candidate_enricher is not None:
                candidate = candidate_enricher(candidate)
            if _is_relation_backed_polity(candidate):
                candidate["border_record"] = _border_record_for_candidate(candidate)
            included_candidates.append(candidate)
        else:
            excluded_candidates.append(candidate)

    manifest = build_collection_artifacts(
        included_candidates,
        output_root=resolved_output_root,
        excluded_candidates=excluded_candidates,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "status": "completed",
        "output_root": resolved_output_root,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def run_egypt_relations(
    *,
    run_id: str,
    output_root: Path | None,
    resume: bool,
    force: bool,
) -> dict[str, object]:
    resolved_output_root = output_root or _default_output_root(run_id)
    relations_dir = resolved_output_root / "relations_final"
    entities_path = relations_dir / "ohm_relation_entities.jsonl"
    hints_path = relations_dir / "ohm_relation_hints.jsonl"

    if resume and entities_path.exists() and hints_path.exists() and not force:
        return {
            "status": "skipped",
            "entities_path": entities_path,
            "hints_path": hints_path,
            "entity_count": 0,
            "hint_count": 0,
        }

    relations_dir.mkdir(parents=True, exist_ok=True)
    included_records = _read_jsonl_records(resolved_output_root / "reports" / "included.jsonl")
    entity_records_input = _read_jsonl_records(resolved_output_root / "entities_final" / "egypt_collection.jsonl")

    name_by_qid = _name_lookup_by_qid(included_records, entity_records_input)
    included_qids = sorted(name_by_qid.keys())

    relation_candidates: list[dict[str, Any]] = []
    for record in included_records:
        relation_candidates.extend(_relation_candidates_for_included_record(record))
    for record in entity_records_input:
        relation_candidates.extend(_relation_candidates_from_entity_hints(record))
    relation_candidates.extend(_relation_candidates_from_wikidata_claims(included_qids, name_by_qid))

    enriched_candidates = enrich_relation_candidates(relation_candidates) if relation_candidates else []

    entity_records: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    hint_records: dict[tuple[str, str | None, str | None, str | None, str | None], dict[str, Any]] = {}

    for record in enriched_candidates:
        target_entity = record.get("target_entity") or {}
        entity_key = (str(target_entity.get("wikidata_id") or "") or None, str(target_entity.get("name") or "") or None)
        if entity_key not in entity_records:
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

    relation_entities = sorted(
        entity_records.values(),
        key=lambda record: (str(record.get("wikidata_id") or ""), str(record.get("name") or "")),
    )
    relation_hints = sorted(
        hint_records.values(),
        key=lambda record: (
            str(record.get("source_wikidata_id") or ""),
            str(record.get("relationship_type") or ""),
            str(record.get("target_wikidata_id") or ""),
            str(record.get("target_label") or ""),
        ),
    )

    _write_jsonl_records(entities_path, relation_entities)
    _write_jsonl_records(hints_path, relation_hints)
    return {
        "status": "completed",
        "entities_path": entities_path,
        "hints_path": hints_path,
        "entity_count": len(relation_entities),
        "hint_count": len(relation_hints),
    }


def _load_index_candidates(xml_index_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(xml_index_path) as connection:
        object_rows = connection.execute(
            """
            SELECT object_type, object_id, name, wikidata_id, raw_tags_json
            FROM objects
            ORDER BY object_type, object_id
            """
        ).fetchall()
        alias_rows = connection.execute(
            """
            SELECT object_type, object_id, alias_value
            FROM object_aliases
            ORDER BY object_type, object_id, alias_key, alias_value
            """
        ).fetchall()

    aliases_by_object: dict[tuple[str, int], list[str]] = {}
    for object_type, object_id, alias_value in alias_rows:
        aliases_by_object.setdefault((str(object_type), int(object_id)), []).append(str(alias_value))

    candidates: list[dict[str, Any]] = []
    for object_type, object_id, name, wikidata_id, raw_tags_json in object_rows:
        raw_tags = json.loads(raw_tags_json)
        alternative_names = aliases_by_object.get((str(object_type), int(object_id)), [])
        if not name and not alternative_names and not wikidata_id:
            continue

        candidates.append(
            {
                "name": name,
                "wikidata_id": wikidata_id,
                "raw_tags": raw_tags,
                "alternative_names": alternative_names,
                "entity_types": _infer_entity_types(str(object_type), name, raw_tags),
                "summary": None,
                "_ohm_object_type": str(object_type),
                "_ohm_object_id": int(object_id),
            }
        )

    return candidates


def _infer_entity_types(object_type: str, name: Any, raw_tags: dict[str, Any]) -> list[str]:
    normalized_name = str(name or "").strip().casefold()
    if "battle" in normalized_name:
        return ["battle"]
    if "war" in normalized_name:
        return ["war"]
    if "period" in normalized_name:
        return ["historical_period"]
    if raw_tags.get("type") == "boundary" or raw_tags.get("boundary") == "administrative":
        return ["political_entity"]
    if raw_tags.get("historic") in {"city", "town", "settlement"}:
        return ["city"]
    if object_type == "relation":
        return ["political_entity"]
    return ["place"]


def _is_relation_backed_polity(candidate: dict[str, Any]) -> bool:
    raw_tags = candidate.get("raw_tags") or {}
    return bool(
        candidate.get("_ohm_object_type") == "relation"
        and isinstance(raw_tags, dict)
        and (raw_tags.get("type") == "boundary" or raw_tags.get("boundary") == "administrative")
    )


def _border_record_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": candidate.get("name"),
        "entity_type": "political_entity",
        "entity_group": "POLITY",
        "wikidata_id": candidate.get("wikidata_id"),
        "_ohm_relation_id": str(candidate.get("_ohm_object_id")),
        "_geometry_periods": [],
    }


def _relation_candidates_for_included_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw_tags = record.get("raw_tags") or {}
    wikidata_id = raw_tags.get("wikidata")
    if not isinstance(raw_tags, dict) or not isinstance(wikidata_id, str) or not wikidata_id.strip():
        return []

    source_record = {
        "relation_id": record.get("_ohm_object_id"),
        "tags": raw_tags,
        "stages": [],
    }
    return extract_relation_candidates(source_record)


def _relation_candidates_from_entity_hints(record: dict[str, Any]) -> list[dict[str, Any]]:
    source_wikidata_id = _string_or_none(record.get("wikidata_id"))
    if source_wikidata_id is None:
        return []

    source_name = _string_or_none(record.get("name"))
    source_object_id = record.get("attributes", {}).get("ohm_object_id")
    relation_id = str(source_object_id) if source_object_id is not None else ""

    hints = record.get("_relationship_hints")
    if not isinstance(hints, list):
        return []

    candidates: list[dict[str, Any]] = []
    for hint in hints:
        if not isinstance(hint, dict):
            continue

        relationship_type = _string_or_none(hint.get("relationship_type"))
        target_wikidata_id = _string_or_none(hint.get("target_wikidata_id"))
        if relationship_type is None or target_wikidata_id is None:
            continue

        candidates.append(
            {
                "source_ohm_relation_id": relation_id,
                "source_wikidata_id": source_wikidata_id,
                "source_name": source_name,
                "relationship_type": relationship_type,
                "inverse_relationship_type": None,
                "target_wikidata_id": target_wikidata_id,
                "target_label": _string_or_none(hint.get("target_label")),
                "source_tag_key": _source_tag_key_for_relationship(relationship_type),
                "temporal_start": _string_or_none(hint.get("temporal_start")),
                "temporal_end": _string_or_none(hint.get("temporal_end")),
                "source": _string_or_none(hint.get("source")),
            }
        )

    return candidates


def _source_tag_key_for_relationship(relationship_type: str) -> str | None:
    mapping = {
        "preceded_by": "preceded_by",
        "succeeded_by": "succeeded_by",
        "resulted_from": "start_event",
        "caused": "end_event",
    }
    return mapping.get(relationship_type)


def _name_lookup_by_qid(*record_sets: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}

    for records in record_sets:
        for record in records:
            qid = _string_or_none(record.get("wikidata_id"))
            name = _string_or_none(record.get("name"))
            if qid is None or name is None:
                continue
            lookup[qid] = name

    return lookup


def _relation_candidates_from_wikidata_claims(
    source_qids: list[str],
    name_by_qid: dict[str, str],
) -> list[dict[str, Any]]:
    if not source_qids:
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source_qid, property_id, target_qid in _fetch_wikidata_claim_edges(source_qids):
        relationship_type = get_relationship_type(property_id)
        if relationship_type is None:
            continue

        dedupe_key = (source_qid, relationship_type, target_qid)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        candidates.append(
            {
                "source_ohm_relation_id": source_qid,
                "source_wikidata_id": source_qid,
                "source_name": name_by_qid.get(source_qid),
                "relationship_type": relationship_type,
                "inverse_relationship_type": None,
                "target_wikidata_id": target_qid,
                "target_label": name_by_qid.get(target_qid),
                "source_tag_key": None,
                "temporal_start": None,
                "temporal_end": None,
                "source": f"wikidata:{property_id}",
            }
        )

    return candidates


def _fetch_wikidata_claim_edges(source_qids: list[str]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    batch_size = 40
    property_set = set(_WIKIDATA_RELATION_PROPERTIES)

    for index in range(0, len(source_qids), batch_size):
        batch = source_qids[index : index + batch_size]

        try:
            response = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "claims",
                    "format": "json",
                },
                timeout=45,
                headers={"User-Agent": "history-mapped-Pipeline/1.0 (https://history-mapped.example)"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue

        entities = payload.get("entities", {})
        if not isinstance(entities, dict):
            continue

        for source_qid, entity in entities.items():
            if not isinstance(entity, dict):
                continue

            claims = entity.get("claims", {})
            if not isinstance(claims, dict):
                continue

            for property_id, statements in claims.items():
                if property_id not in property_set or not isinstance(statements, list):
                    continue

                for statement in statements:
                    if not isinstance(statement, dict):
                        continue

                    mainsnak = statement.get("mainsnak", {})
                    if not isinstance(mainsnak, dict):
                        continue

                    datavalue = mainsnak.get("datavalue", {})
                    if not isinstance(datavalue, dict):
                        continue

                    value = datavalue.get("value", {})
                    if not isinstance(value, dict):
                        continue

                    target_qid = value.get("id")
                    if not isinstance(target_qid, str) or not target_qid.startswith("Q"):
                        continue
                    if source_qid == target_qid:
                        continue

                    edges.append((source_qid, property_id, target_qid))

    return edges


def _string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def _write_jsonl_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


@click.group()
def cli() -> None:
    """OHM historical collection workflow."""


@cli.command("build-xml-index")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="XML source file to stream into the SQLite index.",
)
@click.option(
    "--index-path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="SQLite index output path.",
)
@click.option("--force", is_flag=True, help="Rebuild an incompatible existing XML index.")
def build_xml_index_command(input_path: Path, index_path: Path, force: bool) -> None:
    result = build_index(input_path, index_path=index_path, force=force)
    console.print(f"Build XML index {result['status']}: {result['index_path']}")


@cli.command("egypt-build")
@click.option(
    "--xml-index-path",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="Previously built OHM XML SQLite index.",
)
@click.option(
    "--ohm-index-path",
    required=False,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Optional OHM border SQLite index.",
)
@click.option("--run-id", required=True, help="Deterministic collection run id.")
@click.option(
    "--output-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Optional explicit output directory override.",
)
@click.option("--resume", is_flag=True, help="Reuse compatible completed collection artifacts.")
@click.option("--force", is_flag=True, help="Overwrite stale collection artifacts.")
def egypt_build_command(
    xml_index_path: Path,
    ohm_index_path: Path | None,
    run_id: str,
    output_root: Path | None,
    resume: bool,
    force: bool,
) -> None:
    result = run_egypt_build(
        xml_index_path=xml_index_path,
        ohm_index_path=ohm_index_path,
        run_id=run_id,
        output_root=output_root,
        resume=resume,
        force=force,
        candidate_enricher=enrich_candidate,
    )
    console.print(f"Egypt build {result['status']}: {result['manifest_path']}")


@cli.command("egypt-relations-run")
@click.option("--run-id", required=True, help="Deterministic collection run id.")
@click.option(
    "--output-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Optional explicit output directory override.",
)
@click.option("--resume", is_flag=True, help="Reuse compatible relation artifacts.")
@click.option("--force", is_flag=True, help="Overwrite stale relation artifacts.")
def egypt_relations_run_command(
    run_id: str,
    output_root: Path | None,
    resume: bool,
    force: bool,
) -> None:
    result = run_egypt_relations(
        run_id=run_id,
        output_root=output_root,
        resume=resume,
        force=force,
    )
    console.print(
        f"Egypt relations {result['status']}: {result['entities_path']} | {result['hints_path']}"
    )


@cli.command("egypt-wikidata-build")
@click.option("--run-id", required=True, help="Deterministic collection run id.")
@click.option(
    "--output-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Optional explicit output directory override.",
)
@click.option(
    "--seed-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Path to custom seed JSON file.",
)
@click.option("--no-expansion", is_flag=True, help="Run exact-seed-only mode.")
@click.option("--resume", is_flag=True, help="Reuse compatible completed collection artifacts.")
@click.option("--force", is_flag=True, help="Overwrite stale collection artifacts.")
def egypt_wikidata_build_command(
    run_id: str,
    output_root: Path | None,
    seed_file: Path | None,
    no_expansion: bool,
    resume: bool,
    force: bool,
) -> None:
    artifact_dir = collection_artifact_dir(run_id, base_dir=output_root)

    if resume and not force and (artifact_dir / "manifest.json").exists():
        console.print(f"Run {run_id} already exists. Use --force to rebuild.")
        return

    seeds = load_seed_set(path=seed_file)
    console.print(f"Loaded {len(seeds)} seed(s).")

    records = fetch_seed_entities(seeds)
    console.print(f"Fetched {len(records)} seed entity/ies.")

    excluded: list[dict[str, Any]] = []

    if not no_expansion:
        # Collect expansion QIDs from claims of included seeds
        expansion_qids: list[str] = []
        for record in records:
            hints = record.get("_relationship_hints", [])
            for hint in hints:
                target_qid = hint.get("target_wikidata_id")
                if target_qid and target_qid.startswith("Q"):
                    expansion_qids.append(target_qid)
        # Deduplicate
        expansion_qids = list(dict.fromkeys(expansion_qids))
        expanded = apply_bounded_expansion(records, expansion_qids)
        console.print(f"Expanded to {len(expanded)} additional entity/ies.")
        records.extend(expanded)

    build_egypt_collection_artifacts(artifact_dir, records, seeds, excluded)
    console.print(f"Wrote {len(records)} entity/ies to {artifact_dir}.")


@cli.command("egypt-resolve-targets")
@click.option("--batch-id", default=None, help="Resolve targets only for this batch; omit for all unresolved.")
@click.option("--run-id", required=True, help="Deterministic output run id.")
@click.option(
    "--output-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Optional explicit output directory override.",
)
@click.option(
    "--targets-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Text file with one QID per line (alternative to DB query).",
)
@click.option("--limit", type=int, default=500, show_default=True, help="Max targets to resolve.")
@click.option("--no-egypt-filter", is_flag=True, help="Skip Egypt domain filter.")
@click.option("--resume", is_flag=True, help="Reuse compatible completed collection artifacts.")
@click.option("--force", is_flag=True, help="Overwrite stale collection artifacts.")
def egypt_resolve_targets_command(
    batch_id: str | None,
    run_id: str,
    output_root: Path | None,
    targets_file: Path | None,
    limit: int,
    no_egypt_filter: bool,
    resume: bool,
    force: bool,
) -> None:
    artifact_dir = collection_artifact_dir(run_id, base_dir=output_root)

    if resume and not force and (artifact_dir / "manifest.json").exists():
        console.print(f"Run {run_id} already exists. Use --force to rebuild.")
        return

    result = resolve_pending_targets(
        batch_id=batch_id,
        limit=limit,
        egypt_only=not no_egypt_filter,
        targets_file=targets_file,
    )

    if result["status"] == "empty":
        console.print("No unresolved targets found.")
        return

    console.print(f"Resolved {result['entity_count']} entities from {result['fetched_count']} fetched.")
    if result["skipped_egypt"] > 0:
        console.print(f"  Skipped {result['skipped_egypt']} non-Egypt entities.")
    if result["skipped_map"] > 0:
        console.print(f"  Skipped {result['skipped_map']} unmappable entities.")

    write_resolved_entities(
        artifact_dir,
        result["records"],
        batch_id=batch_id,
    )
    console.print(f"Wrote {result['entity_count']} entities to {artifact_dir}.")


if __name__ == "__main__":
    cli()