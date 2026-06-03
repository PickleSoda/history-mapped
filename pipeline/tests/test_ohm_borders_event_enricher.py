"""Tests for OHM border event enricher."""

from unittest.mock import MagicMock

import pytest

from pipeline.ohm_borders.event_enricher import enrich_event_refs


def test_prefers_explicit_qid(monkeypatch) -> None:
    refs = [{"event_label": "Treaty of Berlin", "event_wikidata_id": "Q1048169"}]

    def mock_sparql(qids):
        return {"Q1048169": {"qid": "Q1048169", "label": "Treaty of Berlin"}}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q1048169"
    assert enriched[0]["match_source"] == "explicit_qid"
    assert enriched[0]["match_confidence"] == "high"


def test_uses_exact_title_fallback_when_qid_missing(monkeypatch) -> None:
    refs = [{"event_label": "Treaty of Bucharest", "event_wikidata_id": None}]

    def mock_sparql(qids):
        return {}

    def mock_search(title):
        return {"qid": "Q500067", "label": title}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)
    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.search_event_by_title", mock_search)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] == "Q500067"
    assert enriched[0]["match_source"] == "exact_title_search"


def test_rejects_ambiguous_search(monkeypatch) -> None:
    refs = [{"event_label": "Revolution", "event_wikidata_id": None}]

    def mock_sparql(qids):
        return {}

    def mock_search(title):
        return None  # ambiguous / no match

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)
    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.search_event_by_title", mock_search)

    enriched = enrich_event_refs(refs)
    assert enriched[0]["resolved_wikidata_id"] is None
    assert enriched[0]["match_source"] == "unresolved"


def test_deduplicates_qids_before_fetch(monkeypatch) -> None:
    refs = [
        {"event_label": "A", "event_wikidata_id": "Q1"},
        {"event_label": "B", "event_wikidata_id": "Q1"},
    ]

    call_count = 0

    def mock_sparql(qids):
        nonlocal call_count
        call_count += 1
        return {"Q1": {"qid": "Q1", "label": "Shared"}}

    monkeypatch.setattr("pipeline.ohm_borders.event_enricher.batch_fetch_wikidata", mock_sparql)

    enrich_event_refs(refs)
    assert call_count == 1