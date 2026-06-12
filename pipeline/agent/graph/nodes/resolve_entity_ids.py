from __future__ import annotations

from datetime import datetime, timezone

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.log_config import get_logger
from pipeline.agent.tools.db import search_entity_by_name, search_entity_by_wikidata_id, search_relationship_by_labels, DbUnavailable

logger = get_logger(__name__)


def resolve_entity_ids(state: AgentRunState) -> AgentRunState:
    """Query DB for committed entity and relation IDs after import.

    Populates entity_id_map (label → DB entity_id) and relation_id_map
    ("src|type|tgt" → DB relationship_id) for chronicle_builder to consume.
    """
    entity_id_map: dict[str, str] = {}
    relation_id_map: dict[str, str] = {}

    for commit in state["committed"]:
        if commit.change_type == "entity":
            # Read natural keys as written by commit_writer (Task 3)
            name = commit.record.get("name", "").strip()
            entity_type = commit.record.get("entity_type", "").strip()
            wikidata_id = commit.record.get("wikidata_id")
            if wikidata_id:
                # Prefer wikidata_id lookup for accuracy
                try:
                    matches = search_entity_by_wikidata_id(wikidata_id)
                    if matches:
                        entity_id_map[name] = matches[0]["entity_id"]
                        continue
                except DbUnavailable as e:
                    logger.warning("DB unavailable during wikidata lookup: %s", e)
                    # Continue to name-based lookup
            if name:
                try:
                    matches = search_entity_by_name(name, entity_type if entity_type else None)
                    for match in matches:
                        if match.get("name", "").lower() == name.lower():
                            entity_id_map[name] = match["entity_id"]
                            break
                except DbUnavailable as e:
                    logger.warning("DB unavailable during name lookup: %s", e)
        elif commit.change_type == "relation":
            src = commit.record.get("source_label", "").strip()
            tgt = commit.record.get("target_label", "").strip()
            rtype = commit.record.get("relationship_type", "").strip()
            if src and tgt and rtype:
                rel_key = f"{src}|{rtype}|{tgt}"
                try:
                    matches = search_relationship_by_labels(src, tgt, rtype)
                    for match in matches:
                        relation_id_map[rel_key] = match["relationship_id"]
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