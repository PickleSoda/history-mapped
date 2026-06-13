"""Tests for OHM-first polity resolution (live API + cache mocked)."""
from __future__ import annotations

import pipeline.agent.tools.ohm_polity_resolver as r

# Two period-specific OHM features for the same polity, as ohm_client normalizes them.
BYZANTINE = [
    {
        "external_type": "relation", "external_id": "2882342",
        "display_name": "Imperium Romanum Orientale", "match_label": "Imperium Romanum Orientale",
        "external_tags": {"start_date": "0752", "end_date": "0798", "wikidata": "Q12544"},
        "source_meta": {"lat": "41.0", "lon": "29.0"},
    },
    {
        "external_type": "relation", "external_id": "2850428",
        "display_name": "late Byzantium", "match_label": "Imperium Romanum Orientale",
        "external_tags": {"start_date": "1354", "end_date": "1453", "wikidata": "Q12544"},
        "source_meta": {"lat": "41.0", "lon": "29.0"},
    },
]


def test_relevance_wikidata_match_is_decisive():
    assert r.relevance(BYZANTINE[0], "anything", None, entity_wikidata="Q12544") == 1.0


def test_relevance_era_carries_a_name_mismatch():
    # "Byzantine Empire" shares no tokens with "Imperium Romanum Orientale";
    # era overlap (780 in 752-798) must still make it relevant.
    score = r.relevance(BYZANTINE[0], "Byzantine Empire", 780)
    assert score >= r._ACCEPT_THRESHOLD


def test_best_candidate_picks_era_closest():
    early = r.best_candidate(BYZANTINE, "Byzantine Empire", 780)
    assert early["external_id"] == "2882342"
    late = r.best_candidate(BYZANTINE, "Byzantine Empire", 1400)
    assert late["external_id"] == "2850428"


def test_best_candidate_rejects_irrelevant():
    junk = [{
        "external_type": "node", "external_id": "9", "display_name": "Somewhere",
        "match_label": "Somewhere", "external_tags": {}, "source_meta": {},
    }]
    assert r.best_candidate(junk, "Byzantine Empire", None) is None


def test_build_manifest_shape():
    m = r.build_manifest({**BYZANTINE[0], "match_score": 0.9}, "Byzantine Empire", 2)
    assert m["status"] == "matched"
    assert m["geo_ref"]["provider"] == "ohm"
    assert m["geo_ref"]["external_type"] == "relation"
    assert m["geo_ref"]["external_id"] == "2882342"
    assert m["geo_ref"]["retrieval_method"] == "nominatim"
    # A representative point (from Nominatim lat/lon), not the boundary polygon.
    assert m["geometry"] == {"type": "Point", "coordinates": [29.0, 41.0]}


def test_relevance_vetoes_wrong_era_namesake():
    # "Egypt" (ancient) vs an 1843 US village named Egypt — exact name, far era.
    village = {
        "external_type": "node", "external_id": "1", "match_label": "Egypt",
        "display_name": "Egypt, United States",
        "external_tags": {"start_date": "1843"}, "source_meta": {},
    }
    assert r.relevance(village, "Egypt", -1000) < r._ACCEPT_THRESHOLD


def test_resolve_polity_adopts_ohm_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "search_by_name", lambda name, loc=None: list(BYZANTINE))
    out = r.resolve_polity("Byzantine Empire", 780, cache_path=tmp_path / "c.sqlite")
    assert out["name"] == "Imperium Romanum Orientale"
    assert out["external_id"] == "2882342"
    assert out["wikidata_id"] == "Q12544"
    assert out["manifest"]["geo_ref"]["external_id"] == "2882342"


def test_resolve_polity_caches_after_first_call(tmp_path, monkeypatch):
    calls = {"n": 0}

    def counting(name, loc=None):
        calls["n"] += 1
        return list(BYZANTINE)

    monkeypatch.setattr(r, "search_by_name", counting)
    cache = tmp_path / "c.sqlite"
    r.resolve_polity("Byzantine Empire", 780, cache_path=cache)
    r.resolve_polity("Byzantine Empire", 1400, cache_path=cache)  # era differs, name cached
    assert calls["n"] == 1


def test_resolve_polity_no_candidates_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "search_by_name", lambda name, loc=None: [])
    assert r.resolve_polity("Nowhereland", 100, cache_path=tmp_path / "c.sqlite") is None


def test_parse_point_wkt():
    assert r.parse_point_wkt("Point(53 33)") == (53.0, 33.0)
    assert r.parse_point_wkt("Point(35.44 30.33)") == (35.44, 30.33)
    assert r.parse_point_wkt("POINT(-1.5 50)") == (-1.5, 50.0)
    assert r.parse_point_wkt(None) is None
    assert r.parse_point_wkt("not a point") is None


def test_build_wikidata_point_manifest():
    m = r.build_wikidata_point_manifest("Q83311", "Point(53 33)")
    assert m["status"] == "matched"
    assert m["geo_ref"]["provider"] == "wikidata"
    assert m["geo_ref"]["external_type"] == "qid"
    assert m["geo_ref"]["external_id"] == "Q83311"
    assert m["geo_ref"]["match_role"] == "fallback"
    assert m["provenance"]["resolver"] == "wikidata_coords"
    assert m["geometry"] == {"type": "Point", "coordinates": [53.0, 33.0]}
    # Needs both a qid and a coordinate.
    assert r.build_wikidata_point_manifest(None, "Point(1 2)") is None
    assert r.build_wikidata_point_manifest("Q1", None) is None
