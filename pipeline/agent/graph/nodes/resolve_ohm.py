from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.tools.ohm import (
    search_ohm_by_wikidata_id,
    search_ohm_by_name,
    resolve_ohm_geometry,
)

logger = get_logger(__name__)


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    ohm_index_path = Path(cfg.ohm_index_path).resolve()
    logger.info("OHM resolution: index=%s", ohm_index_path)
    # Skip if index doesn't exist
    if not ohm_index_path.exists():
        logger.info("OHM index not found at %s, skipping", ohm_index_path)
        state["audit_log"].append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                node="resolve_ohm",
                action="ohm_index_missing",
                output_summary=f"OHM index not found at {ohm_index_path}, skipping geometry resolution",
            )
        )
        return state
    entity_count = len(state["enriched_entities"])
    logger.info("OHM resolution: %d entities", entity_count)
    for i, enriched in enumerate(state["enriched_entities"]):
        logger.info("  [%d/%d] %s — searching OHM", i + 1, entity_count, enriched.candidate.label)
        match = None
        qid = enriched.wikidata_match.get("qid") if enriched.wikidata_match else None
        if qid:
            logger.info("    by QID: %s", qid)
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
