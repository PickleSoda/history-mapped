from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.date_utils import lifespan_problem
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.wikidata import (
    search_wikidata_by_name, enrich_wikidata_entities, fetch_entity_meta, _rank_candidates,
    storable_wikidata_dates,
)
from pipeline.agent.tools.disambiguation import (
    BOUNDED_LIFETIME_TYPES, candidate_name_ok, context_era, era_year, rerank_by_era,
    rerank_by_type, is_ambiguous, screen_candidates,
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


# A person's Wikidata birth/death must agree this closely with a date the
# transcript gives for the same bound; otherwise the QID is a namesake (Lewis
# Powell b. 1576 for the 1865 conspirator, Lysias the orator for the Seleucid
# regent) and its other bound would be glued onto this person's lifespan.
WD_DATE_AGREEMENT_YEARS = 30
# An undated person's Wikidata lifespan must come within this of the dates the
# run gives them (relations, source event — EnrichedCandidate.identity_span).
WD_IDENTITY_SLACK_YEARS = 60


def _wikidata_fill(enriched) -> tuple[str | None, str | None, str | None]:
    """(start, end, refusal) — the Wikidata dates that may fill the candidate's gaps.

    storable_wikidata_dates drops coarse-precision bounds (a century is not a
    birth year) and impossible Wikidata lifespans. For a person the match must
    also be the same person: its dates agree with the transcript's own bound
    (WD_DATE_AGREEMENT_YEARS) or, for an undated person, fall near the run's
    identity span; and the filled lifespan must be possible (lifespan_problem).
    Any failure → no Wikidata date at all, with the reason.
    """
    match = enriched.wikidata_match or {}
    entity_type = enriched.candidate.entity_type
    start, end = storable_wikidata_dates(match, entity_type)
    if not start and not end:
        if match.get("start_date") or match.get("end_date"):
            return None, None, "coarse precision or impossible Wikidata lifespan"
        return None, None, None
    if entity_type != "person":
        return start, end, None
    own_start, own_end = enriched.candidate.start_date, enriched.candidate.end_date
    for own, wd, side in ((own_start, start, "start"), (own_end, end, "end")):
        own_y, wd_y = era_year(own), era_year(wd)
        # Sign-insensitive: a mirrored year is the extractor's sign slip, which
        # the caller corrects from Wikidata (_sign_corrected), not a namesake.
        if own_y is not None and wd_y is not None \
                and min(abs(own_y - wd_y), abs(-own_y - wd_y)) > WD_DATE_AGREEMENT_YEARS:
            return None, None, f"Wikidata {side} {wd} disagrees with the transcript's {own} (namesake QID?)"
    if own_start is None and own_end is None and enriched.identity_span:
        lo, hi = min(enriched.identity_span), max(enriched.identity_span)
        wd_lo = era_year(start) if start else era_year(end)
        wd_hi = era_year(end) if end else era_year(start)
        if wd_hi < lo - WD_IDENTITY_SLACK_YEARS or wd_lo > hi + WD_IDENTITY_SLACK_YEARS:
            return None, None, f"Wikidata lifespan {start}..{end} is far from the run's dates {lo}..{hi} (namesake QID?)"
    filled_start = _sign_corrected(own_start, start) or own_start or start
    filled_end = _sign_corrected(own_end, end) or own_end or end
    problem = lifespan_problem(entity_type, era_year(filled_start), era_year(filled_end))
    if problem:
        return None, None, problem
    return start, end, None


def resolve_wikidata(state: AgentRunState) -> AgentRunState:
    entity_count = len(state["enriched_entities"])
    # Transcript-wide era, used as a fallback when an entity has no date of its own.
    context_era_year = context_era(state["parsed_events"])
    logger.info("Wikidata resolution: %d entities (context era=%s)", entity_count, context_era_year)
    for i, enriched in enumerate(state["enriched_entities"]):
        logger.info("  [%d/%d] %s (type=%s)", i + 1, entity_count, enriched.candidate.label, enriched.candidate.entity_type)

        item_names = [enriched.candidate.label, *(enriched.candidate.aliases or [])]

        if enriched.candidate.wikidata_id:
            qid = enriched.candidate.wikidata_id
            record = enrich_wikidata_entities([qid]).get(qid, {})
            # A pre-assigned QID is name-guarded like a searched one: an LLM- or
            # handoff-supplied QID for the wrong item (World War II's for "World
            # War I") must not become this entity's identity. Unverifiable (no
            # label fetched) keeps the old behaviour.
            ok, why = (candidate_name_ok(item_names, [record.get("label", ""), *record.get("aliases", [])])
                       if record.get("label") else (True, "unverified"))
            if ok:
                enriched.wikidata_match = record
                enriched.wikidata_match["qid"] = qid
                enriched.system_confidence += 0.3 if enriched.wikidata_match.get("description") else 0.1
                logger.info("    → pre-assigned QID=%s label=%s", qid, enriched.wikidata_match.get("label", ""))
                continue
            logger.warning("    → pre-assigned QID=%s label=%s REJECTED (name guard: %s); re-searching",
                           qid, record.get("label", ""), why)

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
            own_era = era_year(enriched.candidate.start_date) or era_year(enriched.candidate.end_date)
            target_era = own_era if own_era is not None else context_era_year
            if is_ambiguous(ranked) and enriched.candidate.entity_type not in _PERSISTENT_PLACE_TYPES:
                if target_era is not None:
                    rerank_by_era(ranked, target_era, meta_by_qid)
                    logger.info("    → era rerank (era=%s) top: %s", target_era,
                                [(c["qid"], c["label"], c.get("score", 0)) for c in ranked[:3]])
            # Name guard: drop candidates whose names disagree with the item's
            # (prefix hits 'Qi'→'Qing dynasty', regnal 'Abbas II'→'Abbas I',
            # 'World War I'→'World War II') before picking the best — so the
            # right namesake further down the ranking can still win. Era veto
            # only for lifetime-bounded kinds; a transcript-median era (no own
            # date) gets a wider tolerance.
            bounded = enriched.candidate.entity_type in BOUNDED_LIFETIME_TYPES
            ranked, rejected = screen_candidates(
                ranked, enriched.candidate.label, enriched.candidate.aliases, meta_by_qid,
                target_era=target_era if bounded else None,
                era_tolerance=400 if own_era is not None else 600,
            )
            if rejected:
                logger.info("    → name guard rejected: %s",
                            [(c["qid"], c.get("label", ""), why) for c, why in rejected[:5]])
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
            # Pass dates from wikidata to the candidate if missing — only dates
            # that are storable (precision, lifespan) and that fit what the
            # transcript already says about this entity (_wikidata_fill).
            wd_start, wd_end, refused = _wikidata_fill(enriched)
            if refused:
                logger.info("    → Wikidata dates %s..%s not used: %s",
                            enriched.wikidata_match.get("start_date"),
                            enriched.wikidata_match.get("end_date"), refused)
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
