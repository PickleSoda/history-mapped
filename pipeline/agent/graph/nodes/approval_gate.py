from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES, AgentConfig
from pipeline.agent.graph.nodes.validate import BASE_CONFIDENCE, GEO_SENSITIVE_TYPES
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.log_config import get_logger
from pipeline.campaign.paths import RUN_PREFIX
from datetime import datetime, timezone

logger = get_logger(__name__)

# VerificationStatus::NeedsReview (api/app/Enums/VerificationStatus.php).
UNVERIFIED_STATUS = "needs_review"
# ConfidenceLevel::Medium (api/app/Enums/ConfidenceLevel.php): passed the campaign
# review, but not the predicate's auto-commit threshold.
REVIEWED_RELATION_CONFIDENCE = "medium"


def is_campaign_handoff(state: AgentRunState) -> bool:
    """A reviewed campaign handoff: summaries_precomputed AND a campaign_ run id.

    Neither signal is enough alone: summaries_precomputed marks any offline
    (opencode) handoff, reviewed or not, and `--run-id campaign_x` can be given
    to a full-LLM run. Together they mean a handoff built by the campaign CLI,
    which the ingest loop feeds only after a PASS/FIXED review.
    """
    return bool(state.get("summaries_precomputed")) and str(state.get("run_id") or "").startswith(RUN_PREFIX)


def _shortfall_reasons(enriched: EnrichedCandidate, threshold: float) -> list[str]:
    """The Wikidata/geometry shortfalls that put a held entity under its threshold.

    These are validate's only confidence penalties; an entity held for any other
    reason gets an empty list and stays held.
    """
    reasons = []
    if not enriched.wikidata_match:
        reasons.append("no_wikidata_match")
    elif BASE_CONFIDENCE + enriched.system_confidence < threshold:
        reasons.append("low_wikidata_match")
    if enriched.candidate.entity_type in GEO_SENSITIVE_TYPES and not enriched.geometry:
        reasons.append("missing_geometry")
    return reasons


def approval_gate(state: AgentRunState) -> AgentRunState:
    cfg = AgentConfig()
    diff = state["proposed_diff"]
    if diff is None:
        state["errors"].append(PipelineError(
            node="approval_gate",
            error_type="missing_diff",
            message="No proposed diff available",
        ))
        return state
    # Campaign entities come from wiki-grounded, reviewed transcripts: a missing or
    # weak Wikidata match / missing geometry commits them as needs_review (to be
    # QID-matched or reviewed later) instead of holding them, which would leave
    # the run's relations to them dangling. Other runs keep the plain gate.
    campaign = is_campaign_handoff(state)
    auto_entities = []
    unverified_entities = []
    auto_relations = []
    flagged = []
    for enriched in diff.create_entities:
        policy = ENTITY_RISK_POLICIES.get(enriched.candidate.entity_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)
        if enriched.final_confidence >= threshold:
            auto_entities.append(enriched.candidate.label)
        else:
            reasons = _shortfall_reasons(enriched, threshold) if campaign else []
            if not reasons:
                flagged.append({"type": "entity", "label": enriched.candidate.label, "reason": f"confidence {enriched.final_confidence:.2f} < threshold {threshold}"})
                continue
            enriched.verification_status = UNVERIFIED_STATUS
            enriched.validation_flags = reasons
            auto_entities.append(enriched.candidate.label)
            unverified_entities.append(enriched.candidate.label)
        # db_lookup found same-name rows of another era (a namesake) and none /
        # several date-compatible: a new entity whose identity is in doubt is
        # never committed verified, whatever its confidence.
        namesake_flag = getattr(enriched, "namesake_flag", None)
        if namesake_flag:
            enriched.verification_status = UNVERIFIED_STATUS
            if namesake_flag not in enriched.validation_flags:
                enriched.validation_flags = [*enriched.validation_flags, namesake_flag]
            if enriched.candidate.label not in unverified_entities:
                unverified_entities.append(enriched.candidate.label)
    # Campaign relations: the reviewer audits each relation's type and direction,
    # so a relation that passed validation (create_relations holds only those) and
    # is under its predicate's threshold is committed at REVIEWED_RELATION_CONFIDENCE
    # instead of held. Other runs keep holding it.
    reviewed_relations = []
    for relation in diff.create_relations:
        relation.commit_confidence = None  # only this gate may set it
        rel_id = f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}"
        policy = RELATION_RISK_POLICIES.get(relation.relationship_type, {})
        threshold = policy.get("auto_commit_threshold", cfg.auto_commit_threshold)
        if relation.final_confidence >= threshold:
            auto_relations.append(rel_id)
        elif campaign:
            relation.commit_confidence = REVIEWED_RELATION_CONFIDENCE
            auto_relations.append(rel_id)
            reviewed_relations.append(rel_id)
        else:
            flagged.append({"type": "relation", "relation_id": rel_id, "reason": f"confidence {relation.final_confidence:.2f} < threshold {threshold}"})
    if unverified_entities:
        logger.info("Campaign run: committing %d entities as %s: %s",
                    len(unverified_entities), UNVERIFIED_STATUS, ", ".join(unverified_entities))
    if reviewed_relations:
        logger.info("Campaign run: committing %d below-threshold relations at confidence %s",
                    len(reviewed_relations), REVIEWED_RELATION_CONFIDENCE)
    diff.review_items = flagged
    diff.create_entities = [e for e in diff.create_entities if e.candidate.label in auto_entities]
    diff.create_relations = [r for r in diff.create_relations if f"{r.source_label}|{r.relationship_type}|{r.target_label}" in auto_relations]
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="approval_gate",
        action="approval_decision",
        output_summary=(f"Auto-commit: {len(auto_entities)} entities "
                        f"({len(unverified_entities)} as {UNVERIFIED_STATUS}), "
                        f"{len(auto_relations)} relations "
                        f"({len(reviewed_relations)} at {REVIEWED_RELATION_CONFIDENCE}); Flagged: {len(flagged)}"),
    ))
    return state
