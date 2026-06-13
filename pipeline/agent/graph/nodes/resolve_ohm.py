from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.log_config import get_logger
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.disambiguation import context_era, era_year
from pipeline.agent.tools.ohm_polity_resolver import resolve_polity

logger = get_logger(__name__)

# Countries & polities only: OHM is authoritative for identity — adopt OHM's
# canonical name + id (the transcript's name becomes an alias).
#
# Scope is deliberately limited to polities. Bare city names (Rome, Gaza,
# Babylon) collide with modern same-named towns in OHM Nominatim and resolve to
# the wrong place (Rome OH, Gaza IA) without an era/identity anchor — worse than
# no geometry. Era-aware place geocoding is a separate follow-up.
_POLITY_TYPES = {"political_entity", "dynasty"}


def _adopt_ohm_name(candidate: CandidateEntity, ohm_name: str | None) -> None:
    """Adopt OHM's canonical name, preserving the transcript's name as an alias."""
    original = candidate.label
    canonical = (ohm_name or "").strip()
    if canonical and canonical.lower() != original.lower():
        if original and original not in candidate.aliases:
            candidate.aliases.append(original)
        candidate.label = canonical


def resolve_ohm(state: AgentRunState) -> AgentRunState:
    """Resolve polities/places to OpenHistoricalMap via live Nominatim.

    Polities adopt OHM's canonical name + id (OHM-first identity); places take
    geometry only. Each match is attached as a `_geo_resolution` manifest for the
    Laravel geo-ref importer. (Replaces the old Egypt-only local index, which
    placed e.g. the Byzantine Empire at Nile-delta coordinates.)
    """
    context_era_year = context_era(state["parsed_events"])
    entities = state["enriched_entities"]
    logger.info("OHM resolution: %d entities (context era=%s)", len(entities), context_era_year)

    resolved = 0
    for i, enriched in enumerate(entities):
        if enriched.candidate.entity_type not in _POLITY_TYPES:
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

        if not result:
            continue

        enriched.geo_resolution = result["manifest"]
        enriched.ohm_match = {
            "object_type": result["external_type"],
            "object_id": result["external_id"],
        }
        _adopt_ohm_name(enriched.candidate, result.get("name"))
        if not enriched.wikidata_match and result.get("wikidata_id"):
            enriched.wikidata_match = {"qid": result["wikidata_id"]}
        resolved += 1

        logger.info(
            "  [%d/%d] %s -> OHM %s/%s (score=%.2f, identity-adopted)",
            i + 1, len(entities), enriched.candidate.label,
            result["external_type"], result["external_id"], result.get("match_score", 0.0),
        )

    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="resolve_ohm",
            action="ohm_resolved",
            output_summary=f"OHM-resolved {resolved}/{len(entities)} polity/place entities",
        )
    )
    return state
