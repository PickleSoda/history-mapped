from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from pipeline.agent.config import AgentConfig
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


def _entity_to_jsonl_record(enriched) -> dict[str, Any]:
    return {
        "name": enriched.candidate.label,
        "entity_type": enriched.candidate.entity_type,
        "entity_group": _entity_type_to_group(enriched.candidate.entity_type),
        "summary": enriched.summary or "",
        "wikidata_id": enriched.wikidata_match.get("qid") if enriched.wikidata_match else None,
        "temporal_start": enriched.candidate.start_date,
        "temporal_end": enriched.candidate.end_date,
        "alternative_names": enriched.candidate.aliases,
        "geojson": enriched.geometry,
        "source_citations": {"created_by": "historical-agent-pipeline", "confidence": enriched.final_confidence},
    }


def _relation_to_hint_record(relation) -> dict[str, Any]:
    """Convert a CandidateRelation to the hint schema for pipeline_relationship_hints table."""
    return {
        "source_wikidata_id": relation.source_wikidata_id,
        "source": relation.source_label,
        "relationship_type": relation.relationship_type,
        "target_wikidata_id": relation.target_wikidata_id,
        "target_label": relation.target_label,
        "temporal_start": relation.start_date,
        "temporal_end": relation.end_date,
        "confidence": "medium",
        "wikidata_property": None,
    }


def _relation_to_jsonl_record(relation) -> dict[str, Any]:
    return {
        "source_name": relation.source_label,
        "target_name": relation.target_label,
        "relationship_type": relation.relationship_type,
        "start_date": relation.start_date,
        "end_date": relation.end_date,
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

    relation_records = [_relation_to_hint_record(r) for r in diff.create_relations]
    # Write both entity hints and relation hints for the relationship-hint importer
    relation_entities_path = output_root / "ohm_relation_entities.jsonl"
    relation_hints_path = output_root / "ohm_relation_hints.jsonl"

    # For relations, we need to write entity hints for source entities
    # Extract unique source entities from relations
    source_entities = {}
    for rel in diff.create_relations:
        if rel.source_wikidata_id and rel.source_label not in source_entities:
            source_entities[rel.source_label] = rel.source_wikidata_id

    with relation_entities_path.open("w", encoding="utf-8") as f:
        for label, qid in source_entities.items():
            f.write(json.dumps({"name": label, "wikidata_id": qid, "entity_type": "person"}, default=str) + "\n")

    with relation_hints_path.open("w", encoding="utf-8") as f:
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
        # Use container-visible absolute path for the directory
        container_rel_dir = f"{container_path}/{state['run_id']}"
        cmd = build_artisan_command("pipeline:import-border-relations", container_rel_dir, sync=True, batch_id=state["run_id"])
        logger.info("Docker import relations (%d records): %s", len(relation_records), " ".join(cmd))
        result = run_artisan_command(cmd)
        logger.info("Docker import relations result: returncode=%d stdout=%s stderr=%s",
                    result["returncode"], result["stdout"][:200], result["stderr"][:200])

        # Gate on returncode - only record committed if successful
        if result["returncode"] == 0:
            for rel in diff.create_relations:
                state["committed"].append(CommittedChange(
                    change_type="relation",
                    record={
                        "source_label": rel.source_label,
                        "target_label": rel.target_label,
                        "relationship_type": rel.relationship_type,
                        "relationship_id": f"{rel.source_label}|{rel.relationship_type}|{rel.target_label}",
                        "path": str(relation_hints_path),
                        "count": len(relation_records),
                        "result": result,
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
