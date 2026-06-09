from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.db import search_entity_by_name, search_entity_by_wikidata_id


def db_lookup(state: AgentRunState) -> AgentRunState:
    enriched: list[EnrichedCandidate] = []
    for candidate in state["candidate_entities"]:
        matches = search_entity_by_name(candidate.label, entity_type=candidate.entity_type)
        existing = matches[0] if matches else None
        if candidate.wikidata_id and not existing:
            qid_matches = search_entity_by_wikidata_id(candidate.wikidata_id)
            existing = qid_matches[0] if qid_matches else None
        enriched.append(
            EnrichedCandidate(
                candidate=candidate,
                wikidata_match={"existing_entity": existing} if existing else None,
            )
        )
    state["enriched_entities"] = enriched
    existing_count = sum(
        1 for e in enriched if e.wikidata_match and e.wikidata_match.get("existing_entity")
    )
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="db_lookup",
            action="db_lookup_complete",
            output_summary=f"{existing_count}/{len(enriched)} candidates already exist in DB",
        )
    )
    return state
