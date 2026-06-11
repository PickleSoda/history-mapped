from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.app_api import build_artisan_command, run_artisan_command

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
    entity_records = [_entity_to_jsonl_record(e) for e in diff.create_entities]
    entity_path = output_root / "entities_to_create.jsonl"
    with entity_path.open("w", encoding="utf-8") as f:
        for record in entity_records:
            f.write(json.dumps(record, default=str) + "\n")
    relation_records = [_relation_to_jsonl_record(r) for r in diff.create_relations]
    relation_path = output_root / "relations_to_create.jsonl"
    with relation_path.open("w", encoding="utf-8") as f:
        for record in relation_records:
            f.write(json.dumps(record, default=str) + "\n")
    if entity_records:
        cmd = build_artisan_command("pipeline:import", str(entity_path), sync=True, batch_id=state["run_id"])
        result = run_artisan_command(cmd)
        state["committed"].append(CommittedChange(
            change_type="entity",
            record={"path": str(entity_path), "count": len(entity_records), "result": result},
            committed_at=datetime.now(timezone.utc).isoformat(),
            batch_id=state["run_id"],
        ))
    if relation_records:
        rel_dir = output_root
        cmd = build_artisan_command("pipeline:import-borders", str(rel_dir), sync=True, batch_id=state["run_id"])
        result = run_artisan_command(cmd)
        # Store each relation with its details for chronicle_builder to find
        for rel in diff.create_relations:
            state["committed"].append(CommittedChange(
                change_type="relation",
                record={
                    "source_label": rel.source_label,
                    "target_label": rel.target_label,
                    "relationship_type": rel.relationship_type,
                    "relationship_id": f"{rel.source_label}|{rel.relationship_type}|{rel.target_label}",
                    "path": str(relation_path),
                    "count": len(relation_records),
                    "result": result,
                },
                committed_at=datetime.now(timezone.utc).isoformat(),
                batch_id=state["run_id"],
            ))
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="commit_writer",
        action="committed",
        output_summary=f"Wrote {len(entity_records)} entities, {len(relation_records)} relations",
    ))
    return state
