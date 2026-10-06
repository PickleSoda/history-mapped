"""Name-identity guard for Wikidata / OHM candidates (wrong-QID merges).

Known bad pairs come from the 2026-10-03 wave (relation endpoints merged by QID
into a differently named row); the true positives must keep resolving.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import pipeline.agent.tools.ohm_polity_resolver as ohm
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.tools.disambiguation import (
    candidate_name_ok,
    names_conflict,
    record_matches_row,
    screen_candidates,
)


# ── names_conflict ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("a, b, why", [
    ("World War I", "World War II", "markers"),
    ("Mithridates VI", "Mithridates V of Pontus", "markers"),
    ("Abbas II", "Abbas I of Persia", "markers"),
    ("Eighteenth Dynasty of Egypt", "Nineteenth Dynasty of Egypt", "markers"),
    ("Qi", "Qing dynasty", "near_miss"),
    ("Qin", "Qing dynasty", "near_miss"),
    ("Julian", "Queen Juliana", "near_miss"),
    ("Romagna", "Romania", "near_miss"),
    ("Battle of Gaza", "Battle of Gazala", "near_miss"),
    ("Prussia", "Russia", "near_miss"),
])
def test_names_conflict_flags_distinguishing_tokens(a, b, why):
    assert names_conflict(a, b) == why
    assert names_conflict(b, a) == why


@pytest.mark.parametrize("a, b", [
    ("Byzantine Empire", "Imperium Romanum Orientale"),  # wholly different: unrelated, not a conflict
    ("Ottomans", "Ottoman Empire"),                     # plural
    ("Assyria", "Assyrian Empire"),                     # demonym
    ("Rome", "Ancient Rome"),
    ("Eighteenth Dynasty of Egypt", "Eighteenth Dynasty of Egypt"),
    ("Philip II of France", "Philip II"),
    ("Malik-Shah", "Malik-Shah II"),                    # one-sided marker: not compatible, but no conflict
])
def test_names_conflict_leaves_same_or_unrelated_names(a, b):
    assert names_conflict(a, b) is None


def test_normalisation_drops_apostrophes_and_transliterates():
    from pipeline.agent.tools.disambiguation import names_compatible

    assert names_compatible("al-Ma'mun", "al-Maʾmun")
    assert names_compatible("Dai Viet", "Đại Việt")
    assert names_compatible("Bao Dai", "Bảo Đại")
    assert names_compatible("Soviet–Afghan War", "Soviet-Afghan War")


# ── candidate_name_ok (Wikidata) ────────────────────────────────────────────

@pytest.mark.parametrize("names, cand_names", [
    (["World War I"], ["World War II", "WWII", "Second World War", "WW2"]),
    (["Mithridates VI"], ["Mithridates V of Pontus", "Mithridates V Euergetes"]),
    (["Abbas II"], ["Abbas I of Persia", "Abbas the Great", "Shah Abbas I"]),
    (["Qi"], ["Qing dynasty", "Great Qing", "Qing Empire", "Manchu dynasty"]),
    (["Julian"], ["Juliana of the Netherlands", "Queen Juliana", "Juliana Louise Emma Marie Wilhelmina"]),
    (["Perdiccas"], ["Perdiccas I of Macedon"]),
])
def test_known_bad_pairs_are_rejected(names, cand_names):
    ok, why = candidate_name_ok(names, cand_names)
    assert not ok, why


@pytest.mark.parametrize("names, cand_names, search_match", [
    (["Eighteenth Dynasty of Egypt"], ["Eighteenth Dynasty of Egypt"], ""),
    (["Zhu Di"], ["Yongle Emperor", "Zhu Di", "Emperor Chengzu of Ming"], ""),   # via alias
    (["Rome"], ["Ancient Rome", "Roman civilization"], ""),
    (["Byzantine Empire"], ["Byzantine Empire", "Eastern Roman Empire"], ""),
    (["Coptos"], ["Qift"], "Coptos"),                                             # exact search hit (alias/other language)
    (["Mehmed the Conqueror"], ["Mehmed II", "Mehmed the Conqueror"], ""),
])
def test_true_positives_still_match(names, cand_names, search_match):
    ok, why = candidate_name_ok(names, cand_names, search_match=search_match)
    assert ok, why


def test_prefix_search_hit_is_not_an_exact_hit():
    # wbsearchentities' match.text for a prefix hit is the full matched label.
    ok, _ = candidate_name_ok(["Qi"], ["Qing dynasty"], search_match="Qing dynasty")
    assert not ok


def test_exact_hit_cannot_override_a_regnal_marker_conflict():
    ok, why = candidate_name_ok(["Abbas II"], ["Abbas I of Persia"], search_match="Abbas II")
    assert not ok and why == "markers"


# ── screen_candidates ───────────────────────────────────────────────────────

def test_screen_keeps_right_namesake_below_wrong_one():
    ranked = [
        {"qid": "Q_V", "label": "Mithridates V of Pontus", "score": 1.4},
        {"qid": "Q_VI", "label": "Mithridates VI of Pontus", "score": 1.3},
    ]
    kept, rejected = screen_candidates(ranked, "Mithridates VI", [], {})
    assert [c["qid"] for c in kept] == ["Q_VI"]
    assert rejected[0][1] == "markers"


def test_screen_vetoes_partial_name_from_another_era():
    # 'Julian' is a sub-phrase of 'Julian of Norwich' (compatible) but she lived
    # a millennium after the emperor the transcript means.
    ranked = [{"qid": "Q_NORWICH", "label": "Julian of Norwich", "score": 1.2}]
    meta = {"Q_NORWICH": {"label": "Julian of Norwich", "start_date": "1343", "end_date": "1416"}}
    kept, rejected = screen_candidates(ranked, "Julian", [], meta, target_era=361)
    assert kept == [] and rejected[0][1].startswith("far_era")
    # Same label: dates never veto (trust the name over a possibly wrong date).
    kept, _ = screen_candidates(
        [{"qid": "Q_J", "label": "Julian", "score": 1.0}],
        "Julian", [], {"Q_J": {"label": "Julian", "start_date": "1800"}}, target_era=361,
    )
    assert kept


def test_screen_rejects_blocked_p31():
    ranked = [{"qid": "Q_NAME", "label": "Julian", "score": 1.5}]
    meta = {"Q_NAME": {"label": "Julian", "p31": ["Q12308941"]}}  # male given name
    kept, rejected = screen_candidates(ranked, "Julian", [], meta)
    assert kept == [] and rejected[0][1] == "blocked_p31"


# ── resolve_wikidata node ───────────────────────────────────────────────────

def _state(candidate: CandidateEntity) -> dict:
    return {
        "run_id": "t", "raw_input": "", "parsed_events": [], "candidate_entities": [],
        "candidate_relations": [], "validation_results": [], "proposed_diff": None,
        "committed": [], "audit_log": [], "errors": [], "entity_id_map": {}, "relation_id_map": {},
        "enriched_entities": [EnrichedCandidate(candidate=candidate)],
    }


@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.fetch_entity_meta")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_node_picks_matching_regnal_number(mock_search, mock_meta, mock_enrich):
    mock_search.return_value = [
        {"qid": "Q_V", "label": "Mithridates V of Pontus", "description": "king", "match_text": "Mithridates V of Pontus"},
        {"qid": "Q_VI", "label": "Mithridates VI of Pontus", "description": "king", "match_text": "Mithridates VI of Pontus"},
    ]
    # Popularity would put V first; the guard must still pick VI.
    mock_meta.return_value = {
        "Q_V": {"label": "Mithridates V of Pontus", "p31": ["Q5"], "sitelinks": 400},
        "Q_VI": {"label": "Mithridates VI of Pontus", "p31": ["Q5"], "sitelinks": 5},
    }
    mock_enrich.side_effect = lambda qids: {q: {"label": "x", "description": "king"} for q in qids}
    state = resolve_wikidata(_state(CandidateEntity(label="Mithridates VI", entity_type="person")))
    assert state["enriched_entities"][0].wikidata_match["qid"] == "Q_VI"


@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.fetch_entity_meta")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_node_leaves_prefix_only_hit_unresolved(mock_search, mock_meta, mock_enrich):
    mock_search.return_value = [
        {"qid": "Q8733", "label": "Qing dynasty", "description": "Chinese dynasty", "match_text": "Qing dynasty"},
    ]
    mock_meta.return_value = {"Q8733": {"label": "Qing dynasty", "aliases": ["Great Qing"], "p31": ["Q164950"], "sitelinks": 150}}
    state = resolve_wikidata(_state(CandidateEntity(label="Qi", entity_type="political_entity")))
    assert not state["enriched_entities"][0].wikidata_match
    mock_enrich.assert_not_called()


@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.fetch_entity_meta")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_node_accepts_alias_match(mock_search, mock_meta, mock_enrich):
    mock_search.return_value = [
        {"qid": "Q9726", "label": "Yongle Emperor", "description": "Ming emperor",
         "aliases": ["Zhu Di"], "match_type": "alias", "match_text": "Zhu Di"},
    ]
    mock_meta.return_value = {"Q9726": {"label": "Yongle Emperor", "aliases": ["Zhu Di"], "p31": ["Q5"],
                                        "sitelinks": 90, "start_date": "1360", "end_date": "1424"}}
    mock_enrich.return_value = {"Q9726": {"label": "Yongle Emperor", "description": "Ming emperor"}}
    state = resolve_wikidata(_state(CandidateEntity(label="Zhu Di", entity_type="person", start_date="1402")))
    assert state["enriched_entities"][0].wikidata_match["qid"] == "Q9726"


@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.fetch_entity_meta")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_node_rejects_wrong_preassigned_qid_and_researches(mock_search, mock_meta, mock_enrich):
    mock_enrich.side_effect = lambda qids: {
        "Q362": {"label": "World War II", "aliases": ["WWII", "Second World War"], "description": "1939-1945 war"},
        "Q361": {"label": "World War I", "aliases": ["WWI", "First World War"], "description": "1914-1918 war"},
    }
    mock_search.return_value = [
        {"qid": "Q361", "label": "World War I", "description": "war", "match_text": "World War I"},
    ]
    mock_meta.return_value = {"Q361": {"label": "World War I", "p31": ["Q198"], "sitelinks": 200}}
    candidate = CandidateEntity(label="World War I", entity_type="event_war", wikidata_id="Q362")
    state = resolve_wikidata(_state(candidate))
    assert state["enriched_entities"][0].wikidata_match["qid"] == "Q361"


# ── OHM ─────────────────────────────────────────────────────────────────────

ROMAGNE = {
    "external_type": "relation", "external_id": "2851901",
    "display_name": "Romagne, Imperium Romanum", "match_label": "Romagne",
    "external_tags": {"start_date": "1861-03-17", "end_date": "1869", "wikidata": "Q244482"},
    "source_meta": {},
}


def test_ohm_rejects_feature_with_other_qid_and_unmatched_name():
    # 'Romania' (Q218) used to take the Romagne feature on era alone; the
    # shared OHM id then merged Romagna into the Romania row.
    assert ohm.relevance(ROMAGNE, "Romania", 1865, entity_wikidata="Q218") == 0.0
    assert ohm.best_candidate([ROMAGNE], "Romania", 1865, entity_wikidata="Q218") is None


def test_ohm_still_takes_foreign_spelling_without_conflicting_qid():
    assert ohm.best_candidate([ROMAGNE], "Romagna", 1865) is not None
    assert ohm.best_candidate([ROMAGNE], "Romagna", 1865, entity_wikidata="Q244482") is not None


def test_ohm_rejects_different_regnal_marker():
    second = {
        "external_type": "relation", "external_id": "1",
        "display_name": "Second French Empire", "match_label": "Second French Empire",
        "external_tags": {"start_date": "1852", "end_date": "1870"}, "source_meta": {},
    }
    assert ohm.relevance(second, "First French Empire", 1860) == 0.0


# ── record_matches_row (mirrors the PHP import guard) ───────────────────────

@pytest.mark.parametrize("name, alts, row, expected", [
    ("World War I", [], ["World War II", "Second World War"], False),
    ("Mithridates VI", [], ["Mithridates V of Pontus"], False),
    ("Qi", [], ["Qing dynasty", "Great Qing"], False),
    ("Julian", [], ["Queen Juliana"], False),
    ("Romagna", ["Romagne"], ["Romania", "Romagne"], False),        # OHM alias must not carry a near-miss
    ("Zhu Di", ["Yongle Emperor"], ["Yongle Emperor"], True),       # record alias carries it
    ("Zhu Di", [], ["Yongle Emperor", "Zhu Di"], True),             # row alias carries it
    ("Rome", [], ["Ancient Rome"], True),
    ("Eighteenth Dynasty of Egypt", [], ["Eighteenth Dynasty of Egypt"], True),
])
def test_record_matches_row(name, alts, row, expected):
    assert record_matches_row(name, alts, row) is expected
