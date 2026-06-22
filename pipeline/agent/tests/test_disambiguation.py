"""Tests for era-aware Wikidata disambiguation helpers."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline.agent.tools.disambiguation import (
    era_year,
    context_era,
    rerank_by_era,
    rerank_by_type,
    type_matches,
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


def test_type_matches():
    assert type_matches("person", ["Q5"]) is True
    assert type_matches("person", ["Q11446"]) is False  # ship
    assert type_matches("city", ["Q15661340"]) is True  # ancient city
    assert type_matches("trade_route", []) is False
    assert type_matches("unknown_type", ["Q5"]) is False  # no expectations


def test_rerank_by_type_demotes_non_human_for_person():
    # The Amerigo Vespucci case: the ship matches the label exactly (high base
    # score) but is not a human; the explorer has a low base score but is Q5.
    candidates = [
        {"qid": "Q467886", "label": "Amerigo Vespucci", "score": 0.6},   # tall ship
        {"qid": "Q47674", "label": "Américo Vespucio", "score": 0.05},   # explorer
    ]
    meta = {
        "Q467886": {"p31": ["Q1581130"], "sitelinks": 6},
        "Q47674": {"p31": ["Q5"], "sitelinks": 114},
    }
    ranked = rerank_by_type(candidates, "person", meta)
    assert ranked[0]["qid"] == "Q47674"  # explorer wins


def test_rerank_by_type_blocklists_taxon():
    # The Actium case: an insect genus must not win for a place.
    candidates = [
        {"qid": "Q14881034", "label": "Actium", "score": 0.6},  # genus of insects
        {"qid": "Q6343", "label": "Carthage", "score": 0.5},    # a real ancient city
    ]
    meta = {
        "Q14881034": {"p31": ["Q16521"], "sitelinks": 3},        # taxon → blocked
        "Q6343": {"p31": ["Q15661340"], "sitelinks": 120},       # ancient city
    }
    ranked = rerank_by_type(candidates, "city", meta)
    assert ranked[0]["qid"] == "Q6343"


def test_rerank_by_type_popularity_breaks_ties():
    # Same kind, same base score → the more-linked (famous) one wins.
    candidates = [
        {"qid": "Q_obscure", "label": "Carthage", "score": 0.5},
        {"qid": "Q_famous", "label": "Carthage", "score": 0.5},
    ]
    meta = {
        "Q_obscure": {"p31": ["Q515"], "sitelinks": 5},
        "Q_famous": {"p31": ["Q515"], "sitelinks": 150},
    }
    ranked = rerank_by_type(candidates, "city", meta)
    assert ranked[0]["qid"] == "Q_famous"


def test_rerank_by_type_skips_candidates_without_meta():
    candidates = [{"qid": "Q1", "score": 0.5}, {"qid": "Q2", "score": 0.4}]
    ranked = rerank_by_type(candidates, "person", {})  # no meta at all
    assert [c["qid"] for c in ranked] == ["Q1", "Q2"]  # order preserved, no crash
