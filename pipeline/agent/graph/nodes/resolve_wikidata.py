from __future__ import annotations

from datetime import datetime, timezone

from requests.exceptions import RequestException

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.logging import get_logger
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.tools.wikidata import search_wikidata_by_name, enrich_wikidata_entities

logger = get_logger(__name__)


def resolve_wikidata(state: AgentRunState) -> AgentRunState:
    entity_count = len(state["enriched_entities"])
    logger.info("Wikidata resolution: %d entities", entity_count)
    for i, enriched in enumerate(state["enriched_entities"]):
        logger.info("  [%d/%d] %s (type=%s)", i + 1, entity_count, enriched.candidate.label, enriched.candidate.entity_type)
        try:
            if enriched.candidate.wikidata_id:
                qid = enriched.candidate.wikidata_id
            else:
                results = search_wikidata_by_name(enriched.candidate.label)
                if not results:
                    continue
                qid = results[0].get("qid")
                if not qid:
                    continue
            full = enrich_wikidata_entities([qid])
            enriched.wikidata_match = full.get(qid, {})
            enriched.wikidata_match["qid"] = qid
            if enriched.wikidata_match.get("label", "").lower() == enriched.candidate.label.lower():
                enriched.system_confidence += 0.3
            if enriched.wikidata_match.get("description"):
                enriched.system_confidence += 0.1
        except RequestException as exc:
            state["errors"].append(PipelineError(
                node="resolve_wikidata",
                error_type="network_timeout",
                message=str(exc),
                context={"entity": enriched.candidate.label},
            ))
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="resolve_wikidata",
            action="wikidata_resolved",
            output_summary=f"Resolved {sum(1 for e in state['enriched_entities'] if e.wikidata_match)} entities",
        )
    )
    return state
