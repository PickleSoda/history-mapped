from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.db import search_entity_by_name, search_entity_by_wikidata_id, DbUnavailable
from pipeline.agent.tools.disambiguation import (
    CONTEMPORANEOUS_RELATION_TYPES,
    NAMESAKE_AMBIGUOUS,
    Span,
    names_compatible,
    pick_namesake,
    row_span,
    span_of_dates,
    temporally_incompatible,
    union_spans,
)

logger = get_logger(__name__)


def _exact_name_matches(matches: list[dict], label: str, entity_type: str | None) -> list[dict]:
    """Every match whose name equals ``label`` case-insensitively (and whose type
    equals ``entity_type`` when given), in DB order; substring-only hits dropped."""
    want = (label or "").strip().lower()
    if not want:
        return []
    exact = []
    for match in matches or []:
        if (match.get("name") or "").strip().lower() != want:
            continue
        if entity_type and match.get("entity_type") and match["entity_type"] != entity_type:
            continue
        exact.append(match)
    return exact


def _exact_name_match(matches: list[dict], label: str, entity_type: str | None) -> dict | None:
    """First of _exact_name_matches, or ``None``."""
    exact = _exact_name_matches(matches, label, entity_type)
    return exact[0] if exact else None


def _reference_span(candidate, state: AgentRunState) -> Span | None:
    """The year span to judge the candidate's identity by.

    Its own dates; else (a third of campaign persons are undated) the union of
    the dates of this run's contemporaneous relations naming it ('Philip II rules
    Spain 1556-1598'); else its source event's dates. A wide union only makes
    more rows compatible (→ ambiguous → new entity), never a wrong pick.
    """
    own = span_of_dates(candidate.start_date, candidate.end_date)
    if own is not None:
        return own
    label = (candidate.label or "").strip().lower()
    spans = []
    for relation in state.get("candidate_relations") or []:
        if getattr(relation, "relationship_type", None) not in CONTEMPORANEOUS_RELATION_TYPES:
            continue
        ends = {(relation.source_label or "").strip().lower(), (relation.target_label or "").strip().lower()}
        if label in ends:
            spans.append(span_of_dates(relation.start_date, relation.end_date))
    from_relations = union_spans(spans)
    if from_relations is not None:
        return from_relations
    source_event = (candidate.source_event or "").strip().lower()
    if source_event:
        for event in state.get("parsed_events") or []:
            if (getattr(event, "label", "") or "").strip().lower() == source_event:
                return span_of_dates(event.start_date, event.end_date)
    return None


def db_lookup(state: AgentRunState) -> AgentRunState:
    # Refresh mode re-resolves EVERY entity through the full pipeline (Wikidata
    # type/QID, OHM geo, dates, summary) and force-updates the existing rows in
    # place (commit_writer passes --force). So here we deliberately do NOT mark
    # matches as existing — that flag short-circuits resolution and excludes them
    # from the diff. The import's own findExisting still collapses to the right row
    # (by QID / OHM id / name+type+era), preserving entity_id and its relations.
    refresh = state.get("refresh", False)
    enriched: list[EnrichedCandidate] = []
    namesakes = 0
    for candidate in state["candidate_entities"]:
        logger.info("DB lookup: %s (type=%s)%s", candidate.label, candidate.entity_type,
                    " [refresh]" if refresh else "")
        existing = None
        namesake_flag = None
        span = _reference_span(candidate, state)
        if not refresh:
            try:
                # search_entity_by_name is a substring (ILIKE %label%) search, so
                # "Franks" also returns "Kingdom of the Franks". Only an exact
                # case-insensitive name match (same type) counts as "already
                # exists" — otherwise the candidate is wrongly dropped from the
                # diff and every relation/chronicle link to it misses.
                matches = search_entity_by_name(candidate.label, entity_type=candidate.entity_type)
                # Temporal guard: same-name rows can be namesakes ('Philip II' of
                # Macedon vs of Spain). A date-incompatible row is never "the
                # same"; among several the compatible one wins; none / several
                # dated namesakes → a new entity, committed as needs_review.
                named = _exact_name_matches(matches, candidate.label, candidate.entity_type)
                existing, verdict = pick_namesake(named, span, entity_type=candidate.entity_type)
                if existing is None and verdict == NAMESAKE_AMBIGUOUS:
                    namesake_flag = NAMESAKE_AMBIGUOUS
                if candidate.wikidata_id and not existing:
                    # Name-guarded like resolve_entity_ids: a wrong pre-assigned
                    # QID must not make another entity's row "already exist" —
                    # nor one of another era (a namesake's QID).
                    qid_matches = [
                        m for m in search_entity_by_wikidata_id(candidate.wikidata_id)
                        if names_compatible(candidate.label, m.get("name") or "")
                    ]
                    compatible = [
                        m for m in qid_matches
                        if not temporally_incompatible(m.get("entity_type") or candidate.entity_type,
                                                       span, row_span(m))
                    ]
                    if compatible:
                        existing, namesake_flag = compatible[0], None
                    elif qid_matches:
                        namesake_flag = NAMESAKE_AMBIGUOUS
            except DbUnavailable as e:
                logger.warning("DB unavailable during lookup: %s", e)
                existing = None
                namesake_flag = None
        if namesake_flag:
            namesakes += 1
            logger.info("DB lookup: %s matches same-name row(s) of another era (span %s) — %s; "
                        "creating a new entity for review", candidate.label, span, namesake_flag)
        enriched.append(
            EnrichedCandidate(
                candidate=candidate,
                wikidata_match={"existing_entity": existing} if existing else None,
                existing_entity=existing is not None,
                namesake_flag=namesake_flag,
                identity_span=list(span) if span is not None else None,
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
            output_summary=(f"{existing_count}/{len(enriched)} candidates already exist in DB"
                            + (f"; {namesakes} namesake-ambiguous" if namesakes else "")),
        )
    )
    return state
