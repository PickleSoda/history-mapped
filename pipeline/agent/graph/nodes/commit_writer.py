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


def _entity_to_jsonl_record(enriched) -> dict[str, Any]:
    return {
        "name": enriched.candidate.label,
        "entity_type": enriched.candidate.entity_type,
        "summary": enriched.summary or "",
        "wikidata_id": enriched.wikidata_match.get("qid") if enriched.wikidata_match else None,
        "start_date": enriched.candidate.start_date,
        "end_date": enriched.candidate.end_date,
        "alternative_names": enriched.candidate.aliases,
        "geometry": enriched.geometry,
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
        state["committed"].append(CommittedChange(
            change_type="relation",
            record={"path": str(relation_path), "count": len(relation_records), "result": result},
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
