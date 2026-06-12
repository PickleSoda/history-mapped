from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from pipeline.agent.config import AgentConfig
from pipeline.agent.date_utils import normalize_historical_date
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.log_config import get_logger
from pipeline.agent.tools.app_api import build_artisan_command, run_artisan_command

logger = get_logger(__name__)

# Maps entity_type → entity_group for Laravel EntityGroup enum
ENTITY_TYPE_TO_GROUP: dict[str, str] = {
    # POLITY
    "political_entity": "POLITY",
    "dynasty": "POLITY",
    "person": "POLITY",
    "military_unit": "POLITY",
    "diplomatic_relationship": "POLITY",
    "social_class": "POLITY",
    # PLACE
    "city": "PLACE",
    "infrastructure_monument": "PLACE",
    "extraction_infra": "PLACE",
    "educational_institution": "PLACE",
    # EVENT
    "event_war": "EVENT",
    "event_battle": "EVENT",
    "event_treaty": "EVENT",
    "event_rebellion": "EVENT",
    "event_natural_disaster": "EVENT",
    "event_tech_adoption": "EVENT",
    "event_legal_reform": "EVENT",
    "migration": "EVENT",
    "epidemic_disease": "EVENT",
    # ECONOMY
    "trade_route": "ECONOMY",
    "natural_resource": "ECONOMY",
    "currency_monetary_system": "ECONOMY",
    # CULTURE
    "cultural_work": "CULTURE",
    "intellectual_movement": "CULTURE",
    "archaeological_culture": "CULTURE",
    "language": "CULTURE",
    "religious_text": "CULTURE",
    "legal_code": "CULTURE",
    "religious_movement": "CULTURE",
    "technology": "CULTURE",
}


def _entity_type_to_group(entity_type: str) -> str:
    return ENTITY_TYPE_TO_GROUP.get(entity_type, "POLITY")


def _extract_geojson(geometry: Any) -> dict[str, Any] | None:
    """Return a bare GeoJSON geometry suitable for PostGIS ST_GeomFromGeoJSON.

    resolve_ohm stores the point resolver's wrapper object
    ({"status": ..., "geometry_source": ..., "point": {GeoJSON}}) on
    ``enriched.geometry``. Laravel feeds the ``geojson`` field straight into a
    PostGIS geometry column, which rejects the wrapper ("unknown GeoJSON type").
    Unwrap to the inner geometry; tolerate an already-bare geometry too.
    """
    if not isinstance(geometry, dict):
        return None
    point = geometry.get("point")
    if isinstance(point, dict) and point.get("type") and "coordinates" in point:
        return point
    if geometry.get("type") and "coordinates" in geometry:
        return geometry
    return None


def _entity_to_jsonl_record(enriched) -> dict[str, Any]:
    return {
        "name": enriched.candidate.label,
        "entity_type": enriched.candidate.entity_type,
        "entity_group": _entity_type_to_group(enriched.candidate.entity_type),
        "summary": enriched.summary or "",
        "wikidata_id": enriched.wikidata_match.get("qid") if enriched.wikidata_match else None,
        "temporal_start": normalize_historical_date(enriched.candidate.start_date),
        "temporal_end": normalize_historical_date(enriched.candidate.end_date),
        "alternative_names": enriched.candidate.aliases,
        "geojson": _extract_geojson(enriched.geometry),
        "source_citations": {"created_by": "historical-agent-pipeline", "confidence": enriched.final_confidence},
    }


def _relation_to_jsonl_record(relation) -> dict[str, Any]:
    """Name-keyed relation record consumed by `php artisan pipeline:import-relations`."""
    return {
        "source_name": relation.source_label,
        "target_name": relation.target_label,
        "relationship_type": relation.relationship_type,
        "start_date": normalize_historical_date(relation.start_date),
        "end_date": normalize_historical_date(relation.end_date),
        "description": relation.description,
        "source_citations": {"created_by": "historical-agent-pipeline"},
    }


def commit_writer(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]
    output_root.mkdir(parents=True, exist_ok=True)
    diff = state["proposed_diff"]
    if diff is None:
        return state

    # Use container-visible path for artisan commands
    container_path = cfg.container_output_dir

    entity_records = [_entity_to_jsonl_record(e) for e in diff.create_entities]
    entity_path = output_root / "entities_to_create.jsonl"
    with entity_path.open("w", encoding="utf-8") as f:
        for record in entity_records:
            f.write(json.dumps(record, default=str) + "\n")

    # Name-keyed relations: the agent rarely has a Wikidata QID for both ends,
    # so we resolve relations by entity name (see pipeline:import-relations).
    relation_records = [_relation_to_jsonl_record(r) for r in diff.create_relations]
    relations_path = output_root / "relations.jsonl"
    with relations_path.open("w", encoding="utf-8") as f:
        for record in relation_records:
            f.write(json.dumps(record, default=str) + "\n")

    if entity_records:
        # Use container-visible absolute path
        container_entity_path = f"{container_path}/{state['run_id']}/entities_to_create.jsonl"
        cmd = build_artisan_command("pipeline:import", container_entity_path, sync=True, batch_id=state["run_id"])
        logger.info("Docker import entities (%d records): %s", len(entity_records), " ".join(cmd))
        result = run_artisan_command(cmd)
        logger.info("Docker import entities result: returncode=%d stdout=%s stderr=%s",
                    result["returncode"], result["stdout"][:200], result["stderr"][:200])

        # Gate on returncode - only record committed if successful
        if result["returncode"] == 0:
            for entity in diff.create_entities:
                state["committed"].append(CommittedChange(
                    change_type="entity",
                    record={
                        "path": str(entity_path),
                        "count": len(entity_records),
                        "name": entity.candidate.label,
                        "entity_type": entity.candidate.entity_type,
                        "wikidata_id": entity.wikidata_match.get("qid") if entity.wikidata_match else None,
                    },
                    committed_at=datetime.now(timezone.utc).isoformat(),
                    batch_id=state["run_id"],
                ))
        else:
            state["errors"].append(PipelineError(
                node="commit_writer",
                error_type="import_failed",
                message=f"Entity import failed with returncode {result['returncode']}",
                context={"stderr": result["stderr"][:500]},
            ))

    if relation_records:
        container_relations_path = f"{container_path}/{state['run_id']}/relations.jsonl"
        # NB: no sync=True — pipeline:import-relations runs inline and has no --sync flag.
        cmd = build_artisan_command("pipeline:import-relations", container_relations_path, batch_id=state["run_id"])
        logger.info("Docker import relations (%d records): %s", len(relation_records), " ".join(cmd))
        result = run_artisan_command(cmd)
        logger.info("Docker import relations result: returncode=%d stdout=%s stderr=%s",
                    result["returncode"], result["stdout"][:200], result["stderr"][:200])

        # Gate on returncode - only record committed if the import did not fault.
        # Real relationship_id values are resolved from the DB by resolve_entity_ids
        # (querying by source/target/type), so we deliberately do NOT fabricate a
        # synthetic "src|type|tgt" id here — that string used to leak into the
        # chronicle's primary_relationship_id (a uuid column) and raise 22P02.
        if result["returncode"] == 0:
            for rel in diff.create_relations:
                state["committed"].append(CommittedChange(
                    change_type="relation",
                    record={
                        "source_label": rel.source_label,
                        "target_label": rel.target_label,
                        "relationship_type": rel.relationship_type,
                        "path": str(relations_path),
                        "count": len(relation_records),
                    },
                    committed_at=datetime.now(timezone.utc).isoformat(),
                    batch_id=state["run_id"],
                ))
        else:
            state["errors"].append(PipelineError(
                node="commit_writer",
                error_type="import_failed",
                message=f"Relation import failed with returncode {result['returncode']}",
                context={"stderr": result["stderr"][:500]},
            ))

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="commit_writer",
        action="committed",
        output_summary=f"Wrote {len(entity_records)} entities, {len(relation_records)} relations",
    ))
    return state
