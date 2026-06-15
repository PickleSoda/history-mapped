from __future__ import annotations

import re
from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry, ChronicleEntryEntity
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.tools.disambiguation import era_year
from pipeline.agent.log_config import get_logger

logger = get_logger(__name__)

_RELATIONSHIP_TYPE_PRIORITY = [
    "victorious_at",
    "defeated_at",
    "participated_in",
    "fought_at",
    "founded",
    "succeeded_by",
    "assassinated_by",
    "caused",
    "resulted_from",
    "commanded",
    "rules",
    "governed_by",
    "allied_with",
    "at_war_with",
]


def _generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a title."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:80]


def _find_primary_relationship(event, candidate_relations, committed, relation_id_map):
    """Find the best-matching relationship for an event.
    
    Requires BOTH source and target entities to be mentioned in the event.
    Uses relation_id_map to return real DB IDs.
    """
    mentioned = set(e.lower() for e in event.mentioned_entities)

    def _priority(rel) -> int:
        return (
            _RELATIONSHIP_TYPE_PRIORITY.index(rel.relationship_type)
            if rel.relationship_type in _RELATIONSHIP_TYPE_PRIORITY
            else 999
        )

    both: list = []         # source AND target named in the event
    source_only: list = []  # only the source named — covers event-anchored
                            # relations (e.g. "Alexander victorious_at Battle of
                            # Issus") where the battle event isn't in the entry's
                            # mentioned_entities, which would otherwise orphan it.
    for rel in candidate_relations:
        src_match = rel.source_label.lower() in mentioned
        tgt_match = rel.target_label.lower() in mentioned
        if src_match and tgt_match:
            both.append(rel)
        elif src_match:
            source_only.append(rel)

    # Prefer fully-grounded relations; fall back to source-grounded ones. Walk in
    # priority order and return the first that resolved to a real DB UUID — never
    # a synthetic "src|type|tgt" string (that is not a UUID -> 22P02 on import).
    for rel in sorted(both, key=_priority) + sorted(source_only, key=_priority):
        rel_key = f"{rel.source_label}|{rel.relationship_type}|{rel.target_label}"
        db_id = relation_id_map.get(rel_key)
        if db_id:
            return db_id

    return None


def _entity_names(enriched) -> list[str]:
    names = [enriched.candidate.label, *(enriched.candidate.aliases or [])]
    return [n for n in names if isinstance(n, str) and n.strip()]


def _collect_secondary_entities(event, enriched_entities, entity_id_map):
    """Attach every entity the event mentions OR that appears by name in the
    narrative.

    Matching only event.mentioned_entities (a separate LLM call) missed entities
    that plainly appear in the entry text — "Cyrus II", "Justinian", "Qing
    Dynasty" — so we also match each entity's label/aliases (word-boundary)
    against the narrative. This is what gets existing entities onto their entries
    (and thus feeds the entry's derived year + location).
    """
    mentioned = {m.lower() for m in event.mentioned_entities}
    narrative = (event.description or "").lower()

    result = []
    seen: set[str] = set()
    for enriched in enriched_entities:
        label = enriched.candidate.label
        if label in seen:
            continue
        if any(
            name.lower() in mentioned
            or re.search(r"\b" + re.escape(name.lower()) + r"\b", narrative)
            for name in _entity_names(enriched)
        ):
            seen.add(label)
            result.append(
                ChronicleEntryEntity(
                    entity_id=entity_id_map.get(label, label),
                    role="participant",
                )
            )
    return result


def chronicle_builder(state: AgentRunState) -> AgentRunState:
    """Build a Chronicle from parsed events and committed data."""
    # Honor --no-create-chronicle: seed entities/relations only, skip the
    # chronicle. chronicle_writer no-ops when state["chronicle"] is None.
    if not state.get("create_chronicle", True):
        state["chronicle"] = None
        state["audit_log"].append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                node="chronicle_builder",
                action="skipped",
                output_summary="create_chronicle=False — entity/relation seeding only",
            )
        )
        return state

    events = state["parsed_events"]
    if not events:
        state["chronicle"] = None
        state["audit_log"].append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                node="chronicle_builder",
                action="no_events",
                output_summary="No parsed events to build chronicle from",
            )
        )
        return state

    # Prefer the transcript's own title. Falling back to the first event's label
    # mis-titles survey transcripts (e.g. a "Biggest Empires Throughout History"
    # transcript became "Rise of the New Kingdom of Egypt" — its first event —
    # so later entities like Adolf Hitler showed up under an Egypt chronicle).
    title = (state.get("title") or "").strip() or (events[0].label or "").strip() or "Untitled Chronicle"
    slug = _generate_slug(title)

    entries = []
    orphan_count = 0
    dropped_count = 0

    for i, event in enumerate(events):
        primary_rel_id = _find_primary_relationship(
            event,
            state["candidate_relations"],
            state["committed"],
            state["relation_id_map"],
        )

        secondary = _collect_secondary_entities(
            event,
            state["enriched_entities"],
            state["entity_id_map"],
        )

        # An entry with neither a resolved relationship nor any attached entity is
        # not anchored to anything — drop it rather than emit an irrelevant entry.
        if primary_rel_id is None and not secondary:
            dropped_count += 1
            continue

        if primary_rel_id is None:
            orphan_count += 1

        start_year = era_year(event.start_date)
        end_year = era_year(event.end_date) or start_year

        entries.append(
            ChronicleEntry(
                sequence_order=len(entries),
                primary_relationship_id=primary_rel_id,
                narrative_text=event.description or "",
                source_evidence=f"event:{i}",
                start_year=start_year,
                end_year=end_year,
                secondary_entities=secondary,
            )
        )

    # Chronicle temporal span = min/max across its entries.
    years = [e.start_year for e in entries if e.start_year is not None]
    years += [e.end_year for e in entries if e.end_year is not None]
    chronicle_start = min(years) if years else None
    chronicle_end = max(years) if years else None

    chronicle = Chronicle(
        title=title,
        slug=slug,
        source_type="video_transcript",
        source_reference=state["raw_input"][:200],
        start_year=chronicle_start,
        end_year=chronicle_end,
        metadata={
            "event_count": len(events),
            "orphan_entry_count": orphan_count,
            "dropped_entry_count": dropped_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        entries=entries,
    )

    state["chronicle"] = chronicle
    state["audit_log"].append(
        AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node="chronicle_builder",
            action="chronicle_built",
            output_summary=f"Built chronicle with {len(entries)} entries ({orphan_count} orphans, {dropped_count} dropped as unanchored)",
        )
    )
    return state
