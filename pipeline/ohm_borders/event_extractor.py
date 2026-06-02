"""Extract event references from OHM border parsed artifacts."""

from typing import Any

EVENT_TAG_KEYS = [
    ("start", "start_event", "start_event:wikidata"),
    ("end", "end_event", "end_event:wikidata"),
]


def extract_event_refs(polity: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract start/end event references from a parsed polity record."""
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    polity_id = str(polity.get("relation_id", ""))
    polity_name = polity.get("tags", {}).get("name", "")

    for stage in polity.get("stages", []):
        stage_id = str(stage.get("relation_id", ""))
        tags = stage.get("tags", {})
        event_date = tags.get("start_date") or tags.get("end_date") or None

        for role, label_key, qid_key in EVENT_TAG_KEYS:
            label = tags.get(label_key, "").strip()
            if not label:
                continue

            qid = tags.get(qid_key, "").strip() or None
            dedup_key = (label, qid)

            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            refs.append({
                "event_role": role,
                "event_label": label,
                "event_wikidata_id": qid,
                "polity_ohm_relation_id": polity_id,
                "stage_ohm_relation_id": stage_id,
                "polity_name": polity_name,
                "event_date": event_date,
                "source_tag_key": label_key,
                "source_tags": {k: v for k, v in tags.items() if k in (label_key, qid_key, "start_date", "end_date")},
            })

    return refs