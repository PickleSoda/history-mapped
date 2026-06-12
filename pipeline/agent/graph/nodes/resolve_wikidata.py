from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.wikidata import search_wikidata_by_name, enrich_wikidata_entities, _rank_candidates

logger = get_logger(__name__)


def resolve_wikidata(state: AgentRunState) -> AgentRunState:
    entity_count = len(state["enriched_entities"])
    logger.info("Wikidata resolution: %d entities", entity_count)
    for i, enriched in enumerate(state["enriched_entities"]):
        logger.info("  [%d/%d] %s (type=%s)", i + 1, entity_count, enriched.candidate.label, enriched.candidate.entity_type)

        if enriched.candidate.wikidata_id:
            qid = enriched.candidate.wikidata_id
            full = enrich_wikidata_entities([qid])
            enriched.wikidata_match = full.get(qid, {})
            enriched.wikidata_match["qid"] = qid
            enriched.system_confidence += 0.3 if enriched.wikidata_match.get("description") else 0.1
            logger.info("    → pre-assigned QID=%s label=%s", qid, enriched.wikidata_match.get("label", ""))
            continue

        # Search Wikidata with smart candidate ranking
        search_names = [enriched.candidate.label]
        # For single-word city/place names, try "Ancient" prefix as fallback
        if enriched.candidate.entity_type in ("city", "place", "political_entity") and len(enriched.candidate.label.split()) <= 2:
            search_names.append(f"Ancient {enriched.candidate.label}")

        best_match = None
        for search_name in search_names:
            limit = 10 if search_name == enriched.candidate.label else 50
            results = search_wikidata_by_name(search_name, limit=limit)
            if not results:
                continue

            ranked = _rank_candidates(results, enriched.candidate.label, enriched.candidate.entity_type)
            logger.info("    → search='%s' top: %s", search_name,
                        [(c["qid"], c["label"], c.get("score", 0)) for c in ranked[:3]])

            if ranked and ranked[0].get("score", 0) >= 0.4:
                best_match = ranked[0]
                break
            if ranked:
                best_match = ranked[0]
                logger.info("    → best score=%.2f, will try next search", best_match.get("score", 0))

        if best_match and best_match.get("score", 0) >= 0.3:
            qid = best_match["qid"]
            full = enrich_wikidata_entities([qid])
            enriched.wikidata_match = full.get(qid, {})
            enriched.wikidata_match["qid"] = qid
            if enriched.candidate.label.lower() == best_match["label"].lower():
                enriched.system_confidence += 0.3
            if enriched.wikidata_match.get("description"):
                enriched.system_confidence += 0.1
            # Pass dates from wikidata to the candidate if missing
            wd_start = enriched.wikidata_match.get("start_date")
            wd_end = enriched.wikidata_match.get("end_date")
            if wd_start and not enriched.candidate.start_date:
                enriched.candidate.start_date = wd_start
            if wd_end and not enriched.candidate.end_date:
                enriched.candidate.end_date = wd_end
            logger.info("    → selected QID=%s label=%s score=%.2f",
                        qid, best_match["label"], best_match.get("score", 0))
        else:
            logger.info("    → no good match (best=%.2f)", best_match.get("score", 0) if best_match else 0)
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="resolve_wikidata",
            action="wikidata_resolved",
            output_summary=f"Resolved {sum(1 for e in state['enriched_entities'] if e.wikidata_match)} entities",
        )
    )
    return state
