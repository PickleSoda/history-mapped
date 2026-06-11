from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES, AgentConfig
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.logging import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)


def approval_gate(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    diff = state["proposed_diff"]
    if diff is None:
        state["errors"].append({
            "node": "approval_gate",
            "error_type": "missing_diff",
            "message": "No proposed diff available",
        })
        return state
    auto_entities = []
    auto_relations = []
    flagged = []
    for enriched in diff.create_entities:
        policy = ENTITY_RISK_POLICIES.get(enriched.candidate.entity_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)
        if enriched.final_confidence >= threshold:
            auto_entities.append(enriched.candidate.label)
        else:
            flagged.append({"type": "entity", "label": enriched.candidate.label, "reason": f"confidence {enriched.final_confidence:.2f} < threshold {threshold}"})
    for relation in diff.create_relations:
        policy = RELATION_RISK_POLICIES.get(relation.relationship_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)
        if relation.final_confidence >= threshold:
            auto_relations.append(f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}")
        else:
            flagged.append({"type": "relation", "relation_id": f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}", "reason": f"confidence {relation.final_confidence:.2f} < threshold {threshold}"})
    diff.review_items = flagged
    diff.create_entities = [e for e in diff.create_entities if e.candidate.label in auto_entities]
    diff.create_relations = [r for r in diff.create_relations if f"{r.source_label}|{r.relationship_type}|{r.target_label}" in auto_relations]
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="approval_gate",
        action="approval_decision",
        output_summary=f"Auto-commit: {len(auto_entities)} entities, {len(auto_relations)} relations; Flagged: {len(flagged)}",
    ))
    return state
