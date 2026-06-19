from __future__ import annotations

import re
from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.disambiguation import context_era, era_year
from pipeline.agent.tools.ohm_polity_resolver import resolve_polity, build_wikidata_point_manifest

logger = get_logger(__name__)

# Polities: adopt OHM's id (authoritative for geometry/dedup), but keep the
# transcript's readable name and record OHM's canonical form as an alias.
_POLITY_TYPES = {"political_entity", "dynasty"}

# Events (wars, battles, sieges, …): GEOMETRY only — keep the event's name, but
# always try to put a point down (a war/battle must be locatable on the map).
# OHM Nominatim first, then the Wikidata-coordinate fallback.
_EVENT_TYPES = {
    "event_war",
    "event_battle",
    "event_treaty",
    "event_rebellion",
    "event_natural_disaster",
    "event_tech_adoption",
    "event_legal_reform",
    "migration",
    "epidemic_disease",
}

# Places (cities, monuments, …): GEOMETRY only — keep the place's name, put a
# point down. Bare names (Rome, Gaza, Babylon) collide with modern same-named
# towns in OHM Nominatim (Rome OH, Gaza IA), so resolution is anchored by the
# entity's Wikidata qid (a qid match is decisive in `relevance()`) plus era —
# the same anchors that already disambiguate polities. The Wikidata-coordinate
# fallback applies when OHM has no feature.
_PLACE_TYPES = {
    "city",
    "infrastructure_monument",
    "extraction_infra",
    "educational_institution",
}

_GEO_TYPES = _POLITY_TYPES | _PLACE_TYPES | _EVENT_TYPES

# Coalitions/alliances are not single places — they are sets of member states, so
# they must NOT get one OHM border or point (the members carry the geography; see
# the extraction prompt, which links members with part_of). This is a deterministic
# backstop for when the LLM mis-types one as a political_entity instead of a
# diplomatic_relationship. "Union" is deliberately absent (Soviet Union etc. are
# real bordered states).
_COALITION_RE = re.compile(
    r"\b(allies|allied powers|alliance|coalition|league|entente|axis|"
    r"central powers|triple alliance|triple entente|holy league|grand alliance)\b",
    re.IGNORECASE,
)


def _is_coalition(name: str) -> bool:
    return bool(_COALITION_RE.search(name or ""))


def _record_ohm_alias(candidate: CandidateEntity, ohm_name: str | None) -> None:
    """Record OHM's canonical name as an alias, keeping the transcript's readable
    name as the display label.

    We still adopt OHM's id + geometry (the valuable part), but NOT its name: OHM's
    canonical is often a less-recognisable Latin/native-script form (its 'Carthāgō'
    or 'Imperium Romanum Orientale' vs the common 'Carthage'/'Byzantine Empire').
    Renaming to it both degraded display names and produced near-duplicate entities
    (the same place under two spellings) that string-dedup missed. Keeping the
    transcript name keeps labels consistent and human-friendly. Non-Latin-script
    canonicals (e.g. cuneiform 𐎧𐏁𐏂) are skipped entirely.
    """
    canonical = (ohm_name or "").strip()
    ascii_letters = sum(1 for ch in canonical if ch.isascii() and ch.isalpha())
    if ascii_letters < 2:
        return
    if canonical.lower() == candidate.label.lower():
        return
    if canonical not in candidate.aliases:
        candidate.aliases.append(canonical)


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    """Resolve polities + events to OpenHistoricalMap via live Nominatim.

    Polities adopt OHM's id (+ OHM's name as an alias, keeping the readable
    display name); events take geometry only. When OHM has no feature, fall back to
    the entity's Wikidata coordinate so a point is still produced — events
    especially (a war/battle must be locatable). Each match is attached as a
    `_geo_resolution` manifest for the Laravel geo-ref importer. (Replaces the
    old Egypt-only local index, which placed the Byzantine Empire in the Nile
    delta.)
    """
    context_era_year = context_era(state["parsed_events"])
    entities = state["enriched_entities"]
    logger.info("OHM resolution: %d entities (context era=%s)", len(entities), context_era_year)

    resolved = 0
    fallback_points = 0
    for i, enriched in enumerate(entities):
        entity_type = enriched.candidate.entity_type
        if entity_type not in _GEO_TYPES:
            continue

        is_polity = entity_type in _POLITY_TYPES

        # Coalitions/alliances get no single geo-ref — their member states do.
        if is_polity and _is_coalition(enriched.candidate.label):
            logger.info(
                "  [%d/%d] skip geo-ref for coalition '%s' (members carry geography)",
                i + 1, len(entities), enriched.candidate.label,
            )
            continue

        era = (
            era_year(enriched.candidate.start_date)
            or era_year(enriched.candidate.end_date)
            or context_era_year
        )
        qid = enriched.wikidata_match.get("qid") if enriched.wikidata_match else None

        try:
            result = resolve_polity(enriched.candidate.label, era, entity_wikidata=qid)
        except Exception as exc:  # never let a lookup error sink the node
            logger.warning("OHM resolve failed for %s: %s", enriched.candidate.label, exc)
            result = None

        if result:
            enriched.geo_resolution = result["manifest"]
            enriched.ohm_match = {
                "object_type": result["external_type"],
                "object_id": result["external_id"],
            }
            # Polities record OHM's canonical name as an alias (display name kept);
            # events keep their own name and add no alias.
            if is_polity:
                _record_ohm_alias(enriched.candidate, result.get("name"))
                if not enriched.wikidata_match and result.get("wikidata_id"):
                    enriched.wikidata_match = {"qid": result["wikidata_id"]}
            resolved += 1
            logger.info(
                "  [%d/%d] %s -> OHM %s/%s (score=%.2f)",
                i + 1, len(entities), enriched.candidate.label,
                result["external_type"], result["external_id"], result.get("match_score", 0.0),
            )
            continue

        # No OHM feature — fall back to an approximate point from the entity's
        # Wikidata coordinate so it still lands on the map. This is what makes
        # events (Sack of Rome, Franco-Prussian War) and OHM-less polities
        # (Persian Empire, Nabataean Kingdom) always get a point when possible.
        coords = enriched.wikidata_match.get("coordinates") if enriched.wikidata_match else None
        fallback = build_wikidata_point_manifest(qid, coords)
        if fallback:
            enriched.geo_resolution = fallback
            fallback_points += 1
            logger.info(
                "  [%d/%d] %s -> approximate point (wikidata %s, no OHM feature)",
                i + 1, len(entities), enriched.candidate.label, qid,
            )

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="resolve_ohm",
            action="ohm_resolved",
            output_summary=(
                f"OHM-resolved {resolved} (polities+places+events); "
                f"{fallback_points} approximate-point fallbacks (of {len(entities)} entities)"
            ),
        )
    )
    return state
