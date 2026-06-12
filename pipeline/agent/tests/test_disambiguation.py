"""Tests for era-aware Wikidata disambiguation helpers."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline.agent.tools.disambiguation import (
    era_year,
    context_era,
    rerank_by_era,
    is_ambiguous,
)


def test_era_year_handles_bce_iso_and_plain():
    assert era_year("334 BCE") == -334
    assert era_year("-0334-01-01T00:00:00Z") == -334
    assert era_year("1453") == 1453
    assert era_year("1453-05-29") == 1453
    assert era_year(None) is None
    assert era_year("") is None


def test_context_era_is_median_event_year():
    events = [
        SimpleNamespace(start_date="334 BCE", end_date=None),
        SimpleNamespace(start_date="331 BCE", end_date=None),
        SimpleNamespace(start_date="323 BCE", end_date=None),
    ]
    assert context_era(events) == -331


def test_rerank_promotes_era_match_over_wrong_era():
    # The Philip II case: same label score, different eras.
    candidates = [
        {"qid": "Q34417", "label": "Philip II of Spain", "score": 0.5},
        {"qid": "Q34201", "label": "Philip II of Macedon", "score": 0.5},
    ]
    dates = {
        "Q34417": {"start_date": "+1527-01-01T00:00:00Z"},
        "Q34201": {"start_date": "-0382-01-01T00:00:00Z", "end_date": "-0336-01-01T00:00:00Z"},
    }
    ranked = rerank_by_era(candidates, target_era=-336, dates_by_qid=dates)
    assert ranked[0]["qid"] == "Q34201"  # Macedon wins
    assert ranked[0]["score"] > ranked[1]["score"]


def test_rerank_noop_without_target_era():
    candidates = [{"qid": "Q1", "score": 0.5}, {"qid": "Q2", "score": 0.4}]
    ranked = rerank_by_era(candidates, target_era=None, dates_by_qid={})
    assert [c["qid"] for c in ranked] == ["Q1", "Q2"]


def test_is_ambiguous():
    assert is_ambiguous([{"score": 0.5}, {"score": 0.45}]) is True
    assert is_ambiguous([{"score": 0.9}, {"score": 0.3}]) is False
    assert is_ambiguous([{"score": 0.5}]) is False
