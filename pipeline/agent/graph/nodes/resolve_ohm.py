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

# Polities: OHM is authoritative for IDENTITY — adopt OHM's canonical name + id
# (the transcript's name becomes an alias).
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

# Bare city/place names (Rome, Gaza, Babylon) collide with modern same-named
# towns in OHM Nominatim (Rome OH, Gaza IA) without an identity anchor, so they
# are deliberately excluded here — era-aware place geocoding is a follow-up.
_GEO_TYPES = _POLITY_TYPES | _EVENT_TYPES

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


def _adopt_ohm_name(candidate: CandidateEntity, ohm_name: str | None) -> None:
    """Adopt OHM's canonical name, preserving the transcript's name as an alias.

    Skips non-Latin-script canonicals (e.g. OHM's Old-Persian/cuneiform 𐎧𐏁𐏂 for
    the Achaemenids) — those make poor display names; we still take OHM's id +
    geometry, just keep the readable transcript name.
    """
    original = candidate.label
    canonical = (ohm_name or "").strip()
    ascii_letters = sum(1 for ch in canonical if ch.isascii() and ch.isalpha())
    if ascii_letters < 2:
        return
    if canonical and canonical.lower() != original.lower():
        if original and original not in candidate.aliases:
            candidate.aliases.append(original)
        candidate.label = canonical


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    """Resolve polities + events to OpenHistoricalMap via live Nominatim.

    Polities adopt OHM's canonical name + id (OHM-first identity); events take
    geometry only (keep their own name). When OHM has no feature, fall back to
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
            # Identity adoption is polities-only; events keep their own name.
            if is_polity:
                _adopt_ohm_name(enriched.candidate, result.get("name"))
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
                f"OHM-resolved {resolved} (polities+events); "
                f"{fallback_points} approximate-point fallbacks (of {len(entities)} entities)"
            ),
        )
    )
    return state
