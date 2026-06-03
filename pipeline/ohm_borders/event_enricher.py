"""Enrich event references with Wikidata matches."""

from typing import Any, Callable

from pipeline.ohm_borders.enricher import batch_enrich_qids


def search_event_by_title(title: str) -> dict[str, Any] | None:
    """Exact-title search against Wikidata. Returns single unambiguous match or None."""
    # Placeholder — actual implementation calls Wikidata search API
    # and returns {"qid": "Q...", "label": title} or None
    raise NotImplementedError("Wikidata exact-title search not yet implemented")


def batch_fetch_wikidata(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch Wikidata metadata for explicit QIDs. Wrapper for batch_enrich_qids."""
    return batch_enrich_qids(qids)


def enrich_event_refs(
    refs: list[dict[str, Any]],
    search_fn: Callable[[str], dict[str, Any] | None] | None = None,
) -> list[dict[str, Any]]:
    """Enrich event references with Wikidata matches."""
    search_fn = search_fn or search_event_by_title

    # Collect unique explicit QIDs
    explicit_qids = {r["event_wikidata_id"] for r in refs if r.get("event_wikidata_id")}
    qid_index: dict[str, dict[str, Any]] = {}

    if explicit_qids:
        qid_index = batch_fetch_wikidata(list(explicit_qids))

    enriched: list[dict[str, Any]] = []

    for ref in refs:
        result = dict(ref)
        qid = ref.get("event_wikidata_id")

        if qid and qid in qid_index:
            result["resolved_wikidata_id"] = qid
            result["match_source"] = "explicit_qid"
            result["match_confidence"] = "high"
            result["search_evidence"] = None
        else:
            search_result = search_fn(ref["event_label"])
            if search_result:
                result["resolved_wikidata_id"] = search_result["qid"]
                result["match_source"] = "exact_title_search"
                result["match_confidence"] = "medium"
                result["search_evidence"] = search_result
            else:
                result["resolved_wikidata_id"] = None
                result["match_source"] = "unresolved"
                result["match_confidence"] = None
                result["search_evidence"] = None

        enriched.append(result)

    return enriched