from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.ohm import (
    search_ohm_by_wikidata_id,
    search_ohm_by_name,
    resolve_ohm_geometry,
)


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    ohm_index_path = cfg.ohm_index_path
    for enriched in state["enriched_entities"]:
        match = None
        qid = enriched.wikidata_match.get("qid") if enriched.wikidata_match else None
        if qid:
            match = search_ohm_by_wikidata_id(qid, ohm_index_path)
        if not match:
            match = search_ohm_by_name(enriched.candidate.label, ohm_index_path)
        if match:
            enriched.ohm_match = match[0]
            geo = resolve_ohm_geometry(
                ohm_index_path,
                enriched.ohm_match["object_type"],
                enriched.ohm_match["object_id"],
            )
            if geo:
                enriched.geometry = geo
                enriched.system_confidence += 0.2
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="resolve_ohm",
            action="ohm_resolved",
            output_summary=f"Resolved {sum(1 for e in state['enriched_entities'] if e.ohm_match)} geometries",
        )
    )
    return state
