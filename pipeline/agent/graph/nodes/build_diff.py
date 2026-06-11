from __future__ import annotations

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.logging import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)


def build_diff(state: AgentRunState) -> AgentRunState:
    create_entities = []
    create_relations = []
    review_items = []
    blocked_items = []
    validation_map = {v.candidate_id: v for v in state["validation_results"]}
    for enriched in state["enriched_entities"]:
        val = validation_map.get(enriched.candidate.label)
        if not val or not val.passed:
            blocked_items.append({"type": "entity", "label": enriched.candidate.label, "reason": val.errors if val else ["No validation result"]})
            continue
        existing = enriched.wikidata_match and enriched.wikidata_match.get("existing_entity")
        if existing:
            continue
        create_entities.append(enriched)
    for relation in state["candidate_relations"]:
        rel_id = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
        val = validation_map.get(rel_id)
        if not val or not val.passed:
            blocked_items.append({"type": "relation", "relation_id": rel_id, "reason": val.errors if val else ["No validation result"]})
            continue
        create_relations.append(relation)
    diff = ProposedDiff(
        run_id=state["run_id"],
        summary={
            "entities_to_create": len(create_entities),
            "relations_to_create": len(create_relations),
            "entities_reused": len(state["enriched_entities"]) - len(create_entities) - len([b for b in blocked_items if b["type"] == "entity"]),
            "requires_review": len(review_items),
            "blocked": len(blocked_items),
        },
        create_entities=create_entities,
        create_relations=create_relations,
        review_items=review_items,
        blocked_items=blocked_items,
    )
    state["proposed_diff"] = diff
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="build_diff",
        action="diff_built",
        output_summary=f"Create {len(create_entities)} entities, {len(create_relations)} relations; {len(blocked_items)} blocked",
    ))
    return state
