from __future__ import annotations

import re
from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry, ChronicleEntryEntity
from pipeline.agent.schemas.validation import AuditEvent
from pipeline.agent.log_config import get_logger

logger = get_logger(__name__)

_RELATIONSHIP_TYPE_PRIORITY = [
    "participated_in",
    "fought_at",
    "caused",
    "resulted_from",
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
    candidates = []

    for rel in candidate_relations:
        src_match = rel.source_label.lower() in mentioned
        tgt_match = rel.target_label.lower() in mentioned
        # Require BOTH entities to be mentioned in the event
        if src_match and tgt_match:
            priority = (
                _RELATIONSHIP_TYPE_PRIORITY.index(rel.relationship_type)
                if rel.relationship_type in _RELATIONSHIP_TYPE_PRIORITY
                else 999
            )
            candidates.append((priority, rel))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    best = candidates[0][1]
    rel_key = f"{best.source_label}|{best.relationship_type}|{best.target_label}"

    # Real DB relationship_id (a UUID), resolved by resolve_entity_ids querying
    # the relationships table by source/target/type. If the relation did not
    # persist (e.g. an entity was missing) the key is absent — leave the entry
    # orphaned (None) rather than emitting a synthetic "src|type|tgt" string,
    # which is not a UUID and raised SQLSTATE 22P02 on chronicle import.
    return relation_id_map.get(rel_key)


def _collect_secondary_entities(event, primary_rel_id, enriched_entities, entity_id_map):
    """Collect entities mentioned in the event, resolved to DB IDs."""
    mentioned = set(e.lower() for e in event.mentioned_entities)
    return [
        ChronicleEntryEntity(
            entity_id=entity_id_map.get(e.candidate.label, e.candidate.label),
            role="participant",
        )
        for e in enriched_entities
        if e.candidate.label.lower() in mentioned
    ]


def chronicle_builder(state: AgentRunState) -> AgentRunState:
    """Build a Chronicle from parsed events and committed data."""
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

    title = events[0].label if events[0].label else "Untitled Chronicle"
    slug = _generate_slug(title)

    entries = []
    orphan_count = 0

    for i, event in enumerate(events):
        primary_rel_id = _find_primary_relationship(
            event,
            state["candidate_relations"],
            state["committed"],
            state["relation_id_map"],
        )

        if primary_rel_id is None:
            orphan_count += 1

        secondary = _collect_secondary_entities(
            event,
            primary_rel_id,
            state["enriched_entities"],
            state["entity_id_map"],
        )

        entries.append(
            ChronicleEntry(
                sequence_order=i,
                primary_relationship_id=primary_rel_id,
                narrative_text=event.description or "",
                source_evidence=f"event:{i}",
                secondary_entities=secondary,
            )
        )

    chronicle = Chronicle(
        title=title,
        slug=slug,
        source_type="video_transcript",
        source_reference=state["raw_input"][:200],
        metadata={
            "event_count": len(events),
            "orphan_entry_count": orphan_count,
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
            output_summary=f"Built chronicle with {len(entries)} entries ({orphan_count} orphans)",
        )
    )
    return state
