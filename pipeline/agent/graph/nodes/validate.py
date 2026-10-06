from __future__ import annotations

from pipeline.agent.config import ENTITY_RISK_POLICIES, RELATION_RISK_POLICIES
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import ValidationResult, AuditEvent
from pipeline.agent.log_config import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)

ALLOWED_ENTITY_TYPES = set(ENTITY_RISK_POLICIES.keys()) | {
    "military_unit", "diplomatic_relationship", "social_class",
    "infrastructure_monument", "extraction_infra", "educational_institution",
    "event_rebellion", "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease",
    "natural_resource", "currency_monetary_system",
    "intellectual_movement", "religious_text", "legal_code", "religious_movement", "language", "technology",
}

ALLOWED_RELATION_TYPES = set(RELATION_RISK_POLICIES.keys()) | {
    "contains", "capital_of", "split_from", "merged_into",
    "vassal_of", "suzerain_of",
    "resided_in", "commanded", "founded", "authored", "commissioned",
    "married_to", "parent_of", "child_of", "sibling_of",
    "mentor_of", "student_of", "assassinated_by", "member_of_dynasty", "patron_of",
    "defeated_at", "victorious_at", "stationed_at", "recruited_from", "commanded_by",
    "connects", "produces", "extracts", "supplies", "controlled_by",
    "passes_through", "minted_by", "used_currency",
    "adheres_to", "official_religion_of", "persecuted_by",
    "influenced_by", "inspired", "schism_from", "translated_into",
    "located_at", "built_by", "destroyed_by", "restored_by",
    "contributed_to", "enabled", "prevented", "weakened", "strengthened",
    "invented", "adopted", "taught_at", "spread_to", "required_by", "replaced_by",
    "signed_by", "violated_by", "guaranteed_by", "mediated_by", "enforced_by",
}


# Entity confidence = BASE_CONFIDENCE + Wikidata bonuses (system_confidence)
# - MISSING_GEOMETRY_PENALTY for a geo-sensitive type without geometry.
# approval_gate reuses these to tell which shortfall held an entity.
BASE_CONFIDENCE = 0.95
MISSING_GEOMETRY_PENALTY = 0.05
GEO_SENSITIVE_TYPES = {"political_entity", "city", "infrastructure_monument", "event_battle", "trade_route"}

# Relation confidence: a valid relation scores BASE_CONFIDENCE, plus
# RELATION_CORROBORATION_BONUS when both ends carry a Wikidata QID (the resolved
# match, or the existing DB row's). Like the high-risk entity types (0.97), the
# high-risk predicates (rules/governed_by, 0.97) then auto-commit only with that
# external corroboration; at a flat 0.95 they could never auto-commit.
RELATION_CORROBORATION_BONUS = 0.02


def _endpoint_qid(enriched) -> str | None:
    match = enriched.wikidata_match or {}
    return match.get("qid") or (match.get("existing_entity") or {}).get("wikidata_id")


def validate(state: AgentRunState) -> AgentRunState:
    results = []
    for enriched in state["enriched_entities"]:
        errors = []
        warnings = []
        # Base confidence: combine fixed floor with external enrichment bonuses
        # system_confidence accumulates: +0.3 (Wikidata label), +0.1 (Wikidata desc), +0.2 (OHM geom)
        confidence = BASE_CONFIDENCE + enriched.system_confidence
        if enriched.candidate.entity_type not in ALLOWED_ENTITY_TYPES:
            errors.append(f"Invalid entity type: {enriched.candidate.entity_type}")
        policy = ENTITY_RISK_POLICIES.get(enriched.candidate.entity_type, {})
        if policy.get("requires_wikidata") and not enriched.wikidata_match:
            errors.append("Missing Wikidata ID")
            confidence -= 0.3
        if enriched.candidate.entity_type in GEO_SENSITIVE_TYPES and not enriched.geometry:
            warnings.append("Missing geometry for geography-sensitive entity")
            confidence -= MISSING_GEOMETRY_PENALTY
        confidence = max(0.0, min(1.0, confidence))
        enriched.final_confidence = confidence
        results.append(ValidationResult(
            candidate_id=enriched.candidate.label,
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        ))
    qids = {e.candidate.label: _endpoint_qid(e) for e in state["enriched_entities"]}
    for relation in state["candidate_relations"]:
        errors = []
        if relation.relationship_type not in ALLOWED_RELATION_TYPES:
            errors.append(f"Invalid relation type: {relation.relationship_type}")
        # Reject self-referencing relations (source == target)
        if relation.source_label.lower() == relation.target_label.lower():
            errors.append(f"Self-referencing relation: source and target are both '{relation.source_label}'")
            # Try to fix common cases: "died_in" with same source/target
            if relation.relationship_type in ("died_in", "born_in", "resided_in"):
                errors.append(f"'{relation.relationship_type}' should reference a place, not the person")
        entity_labels = {e.candidate.label for e in state["enriched_entities"]}
        if relation.source_label not in entity_labels:
            errors.append(f"Source entity not found: {relation.source_label}")
        if relation.target_label not in entity_labels:
            errors.append(f"Target entity not found: {relation.target_label}")
        if errors:
            relation.final_confidence = 0.3
        else:
            corroborated = all(qids.get(label) for label in (relation.source_label, relation.target_label))
            bonus = RELATION_CORROBORATION_BONUS if corroborated else 0.0
            relation.final_confidence = round(BASE_CONFIDENCE + bonus, 4)
        results.append(ValidationResult(
            candidate_id=f"{relation.source_label}|{relation.relationship_type}|{relation.target_label}",
            passed=len(errors) == 0,
            errors=errors,
        ))
    state["validation_results"] = results
    passed_count = sum(1 for r in results if r.passed)
    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="validate",
        action="validation_complete",
        output_summary=f"{passed_count}/{len(results)} candidates passed validation",
    ))
    return state
