from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.log_config import get_logger
from pipeline.agent.tools.disambiguation import (
    names_compatible,
    pick_namesake,
    row_span,
    temporally_incompatible,
    year_span,
)
from pipeline.agent.tools.db import (
    DbUnavailable,
    search_entity_by_name,
    search_entity_by_wikidata_id,
    search_relationship_by_entity_ids,
    search_relationship_by_labels,
)

logger = get_logger(__name__)


def resolve_entity_ids(state: AgentRunState) -> AgentRunState:
    """Query DB for committed entity and relation IDs after import.

    Populates entity_id_map (label → DB entity_id) and relation_id_map
    ("src|type|tgt" → DB relationship_id) for chronicle_builder to consume.
    """
    entity_id_map: dict[str, str] = {}
    relation_id_map: dict[str, str] = {}

    # Pre-seed with db_lookup's existing matches: they are not re-imported (so
    # never appear in `committed`), yet relations and chronicle entries name them.
    # Their entity_id is already known — link by id, not by label.
    for enriched in state.get("enriched_entities") or []:
        existing = (enriched.wikidata_match or {}).get("existing_entity") if enriched.existing_entity else None
        if existing and existing.get("entity_id"):
            entity_id_map[enriched.candidate.label] = str(existing["entity_id"])

    for commit in state["committed"]:
        if commit.change_type == "entity":
            # Read natural keys as written by commit_writer (Task 3)
            name = commit.record.get("name", "").strip()
            entity_type = commit.record.get("entity_type", "").strip()
            wikidata_id = commit.record.get("wikidata_id")
            # The record's dates (or db_lookup's derived span): tells the row
            # just imported from a same-name namesake of another era.
            identity_span = commit.record.get("identity_span") or None
            span = year_span(*identity_span[:2]) if identity_span and len(identity_span) >= 2 else None
            if wikidata_id:
                # Prefer wikidata_id lookup — but only when the QID row's name is
                # compatible with the label: pipeline QIDs are sometimes wrong
                # ("World War I" carried World War II's QID), and the chronicle
                # must not link the narrative to the wrong entity. A mismatch
                # (or a row of another era) falls through to the name lookup.
                try:
                    matches = [
                        m for m in search_entity_by_wikidata_id(wikidata_id)
                        if names_compatible(name, m.get("name") or "")
                        and not temporally_incompatible(m.get("entity_type") or entity_type or None,
                                                        span, row_span(m))
                    ]
                    if matches:
                        # psycopg returns uuid columns as uuid.UUID; the chronicle
                        # schema expects plain strings, so coerce here at the source.
                        entity_id_map[name] = str(matches[0]["entity_id"])
                        continue
                except DbUnavailable as e:
                    logger.warning("DB unavailable during wikidata lookup: %s", e)
                    # Continue to name-based lookup
            if name:
                try:
                    matches = search_entity_by_name(name, entity_type if entity_type else None)
                    named = [m for m in matches if (m.get("name") or "").lower() == name.lower()]
                    # Same-name rows may be namesakes ('Philip II' of Macedon vs
                    # of Spain): the date-compatible one, or none when ambiguous
                    # (the chronicle then falls back to the label).
                    match, _verdict = pick_namesake(named, span, entity_type=entity_type or None)
                    if match is not None:
                        entity_id_map[name] = str(match["entity_id"])
                except DbUnavailable as e:
                    logger.warning("DB unavailable during name lookup: %s", e)
        elif commit.change_type == "relation":
            src = commit.record.get("source_label", "").strip()
            tgt = commit.record.get("target_label", "").strip()
            rtype = commit.record.get("relationship_type", "").strip()
            if src and tgt and rtype:
                rel_key = f"{src}|{rtype}|{tgt}"
                try:
                    # Identity first: an endpoint row may carry a different name
                    # than the label (QID merge), so a label join would miss it.
                    matches = []
                    if src in entity_id_map and tgt in entity_id_map:
                        matches = search_relationship_by_entity_ids(
                            entity_id_map[src], entity_id_map[tgt], rtype
                        )
                    if not matches:
                        matches = search_relationship_by_labels(src, tgt, rtype)
                    for match in matches:
                        relation_id_map[rel_key] = str(match["relationship_id"])
                        break
                except DbUnavailable as e:
                    logger.warning("DB unavailable during relation lookup: %s", e)

    state["entity_id_map"] = entity_id_map
    state["relation_id_map"] = relation_id_map

    state["audit_log"].append(AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        node="resolve_entity_ids",
        action="ids_resolved",
        output_summary=f"Resolved {len(entity_id_map)} entity IDs, {len(relation_id_map)} relation IDs",
    ))
    return state