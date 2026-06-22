from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.wikidata import (
    search_wikidata_by_name, enrich_wikidata_entities, fetch_entity_meta, _rank_candidates,
)
from pipeline.agent.tools.disambiguation import (
    context_era, era_year, rerank_by_era, rerank_by_type, is_ambiguous,
)

logger = get_logger(__name__)

# Cities, monuments and institutions persist across eras, so their Wikidata
# inception (often deep-BCE) is a poor era signal. Era-reranking actively harms
# them: the real city (penalised for a founding date far from the transcript era)
# is demoted below a dateless modern namesake that the penalty can't touch — e.g.
# Jerusalem resolved to a stray Q10540001 instead of Q1218, then failed OHM and
# the coordinate fallback, landing no geo at all. Only era-rerank bounded-lifetime
# entities (persons, dynasties, polities, events).
_PERSISTENT_PLACE_TYPES = {
    "city", "infrastructure_monument", "extraction_infra", "educational_institution",
}


def _sign_corrected(llm_date: str | None, wd_date: str | None) -> str | None:
    """Return the Wikidata date when it is the same magnitude as the LLM date but
    opposite sign — i.e. a CE/BCE confusion the extractor makes despite the prompt
    (e.g. "750 CE" vs Wikidata's "-0750"). Returns None when no sign flip applies,
    so the caller keeps the LLM value. Only a pure sign flip is corrected; a
    genuinely different year (birth vs reign-start) is left alone.
    """
    llm_year = era_year(llm_date)
    wd_year = era_year(wd_date)
    if llm_year is None or wd_year is None:
        return None
    if llm_year != wd_year and abs(llm_year) == abs(wd_year):
        return wd_date
    return None


def resolve_wikidata(state: AgentRunState) -> AgentRunState:
    entity_count = len(state["enriched_entities"])
    # Transcript-wide era, used as a fallback when an entity has no date of its own.
    context_era_year = context_era(state["parsed_events"])
    logger.info("Wikidata resolution: %d entities (context era=%s)", entity_count, context_era_year)
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

        # Skip if db_lookup already found an existing entity in the DB
        if enriched.existing_entity:
            logger.info("    → existing entity in DB, skipping Wikidata lookup")
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
            # Type + popularity rerank (ALWAYS): fetch P31/sitelinks/dates for ALL
            # candidates in one batched call, then prefer the candidate whose
            # Wikidata kind matches the entity — a person resolves to a human, not
            # a same-named ship, statuette, cognomen, or insect genus. We fetch the
            # whole candidate set (not just the top few) because the correct subject
            # often has a non-matching label (e.g. the explorer "Américo Vespucio"
            # vs the search term "Amerigo Vespucci") and so sorts LOW on base score;
            # the type+popularity boost is exactly what rescues it. Type errors
            # aren't gated by score-closeness, so this runs unconditionally (unlike
            # the era tie-break below). The fetched dates are reused for era rerank.
            meta_by_qid = fetch_entity_meta([c["qid"] for c in ranked])
            rerank_by_type(ranked, enriched.candidate.entity_type, meta_by_qid)
            # Era-aware tie-break: when the top candidates are still close (e.g.
            # "Philip II of Macedon" vs "Philip II of Spain"), prefer the one
            # nearest the entity's era — reusing meta dates, no extra fetch. Skipped
            # for persistent places whose inception date misleads it.
            if is_ambiguous(ranked) and enriched.candidate.entity_type not in _PERSISTENT_PLACE_TYPES:
                target_era = (
                    era_year(enriched.candidate.start_date)
                    or era_year(enriched.candidate.end_date)
                    or context_era_year
                )
                if target_era is not None:
                    rerank_by_era(ranked, target_era, meta_by_qid)
                    logger.info("    → era rerank (era=%s) top: %s", target_era,
                                [(c["qid"], c["label"], c.get("score", 0)) for c in ranked[:3]])
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
            # Correct CE/BCE sign flips against Wikidata (authoritative). The
            # extractor intermittently mis-signs a year; trust Wikidata's sign
            # when the magnitude matches.
            corrected_start = _sign_corrected(enriched.candidate.start_date, wd_start)
            if corrected_start:
                logger.info("    → corrected start_date sign %s → %s (wikidata)",
                            enriched.candidate.start_date, corrected_start)
                enriched.candidate.start_date = corrected_start
            corrected_end = _sign_corrected(enriched.candidate.end_date, wd_end)
            if corrected_end:
                logger.info("    → corrected end_date sign %s → %s (wikidata)",
                            enriched.candidate.end_date, corrected_end)
                enriched.candidate.end_date = corrected_end
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
