from __future__ import annotations
import json
from pathlib import Path
from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from datetime import datetime, timezone


def audit_logger(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    output_root = Path(cfg.output_dir) / state["run_id"]
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": state["run_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_preview": state["raw_input"][:200],
        "parsed_events_count": len(state["parsed_events"]),
        "candidate_entities_count": len(state["candidate_entities"]),
        "candidate_relations_count": len(state["candidate_relations"]),
        "enriched_entities_count": len(state["enriched_entities"]),
        "validation_results_count": len(state["validation_results"]),
        "committed_count": len(state["committed"]),
        "errors_count": len(state["errors"]),
        "audit_log": [a.model_dump() for a in state["audit_log"]],
        "errors": [e.model_dump() for e in state["errors"]],
    }
    manifest_path = output_root / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="audit_logger",
        action="manifest_written",
        output_summary=f"Manifest written to {manifest_path}",
    ))
    return state
