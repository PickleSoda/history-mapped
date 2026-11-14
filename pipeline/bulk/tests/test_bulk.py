from collections import Counter

import pytest

from pipeline.bulk.build import build, gate, impact_from_sitelinks
from pipeline.bulk.fetch import point, rdf_year, start_precision
from pipeline.bulk.spec import Slice, Window, all_slices


def spec(**kw):
    base = {"id": "test-slice", "entity_type": "event_battle", "where": "?item wdt:P31 wd:Q178561 ."}
    return Slice.from_dict({**base, **kw})


def raw(**kw):
    base = {
        "qid": "Q1", "label": "Battle of Somewhere", "description": "battle", "aliases": [],
        "coords": {"lon": 10.0, "lat": 45.0}, "wikipedia_title": "Battle of Somewhere",
        "sitelinks": 12, "p31": ["Q178561"], "properties": {}, "point_in_time": "1066",
    }
    return {**base, **kw}


@pytest.mark.parametrize("dt,year", [
    ("1066-10-14T00:00:00Z", 1066),
    ("+1066-10-14T00:00:00Z", 1066),
    ("-0489-09-12T00:00:00Z", -490),  # astronomical -489 is 490 BCE
    ("0000-01-01T00:00:00Z", -1),
    ("-2999-01-01T00:00:00Z", -3000),
    (None, None),
    ("garbage", None),
])
def test_rdf_year_reads_bce_correctly(dt, year):
    assert rdf_year(dt) == year


def test_point_ignores_other_globes_and_junk():
    assert point("Point(12.5 41.9)") == {"lon": 12.5, "lat": 41.9}
    assert point("<http://www.wikidata.org/entity/Q405> Point(1 2)") is None
    assert point("Point(500 2)") is None
    assert point(None) is None


def test_impact_ranks_bulk_rows_below_curated_median():
    assert impact_from_sitelinks(0) == 30
    assert impact_from_sitelinks(3) == 45
    assert impact_from_sitelinks(30) == 66
    assert impact_from_sitelinks(100000) == 80


def test_window_halves_and_clause():
    w = Window("P585", 1000, 1100)
    assert "YEAR(?hm_d) >= 1000 && YEAR(?hm_d) < 1100" in w.clause()
    assert [(h.start, h.end) for h in w.halves()] == [(1000, 1050), (1050, 1100)]
    assert Window("P585", 5, 6).halves() is None


def test_qid_query_adds_bar_and_enwiki():
    s = spec(min_sitelinks=3, shards={"years": {"prop": "P585", "from": 1000, "to": 1200, "step": 100}})
    shards = s.initial_shards()
    assert [sh.label for sh in shards] == ["P585:1000..1100", "P585:1100..1200"]
    q = s.qid_query(shards[0])
    assert "FILTER(?hm_sl >= 3)" in q and "en.wikipedia.org" in q and q.startswith("SELECT DISTINCT ?item ?hm_sl")


@pytest.mark.parametrize("bad", [
    {"id": "Bad Id"},
    {"entity_type": "ref_body_of_water"},
    {"where": "?x wdt:P31 wd:Q1 ."},
    {"where": "SELECT ?item WHERE { ?item wdt:P31 wd:Q1 }"},
    {"exclude_p31": ["P31"]},
    {"require": ["sitelinks"]},
    {"shards": {"months": {}}},
    {"surprise": 1},
])
def test_spec_rejects_bad_slices(bad):
    with pytest.raises((ValueError, TypeError)):
        spec(**bad)


def test_gate_reasons():
    s = spec(exclude_p31=["Q13406463"], require=["dates", "coords"], year_max=2000)
    rec = {"name": "X", "temporal_start": "1066", "geojson": {}}
    assert gate(raw(p31=["Q13406463"]), rec, s) == "excluded-class"
    assert gate(raw(), {"name": "X"}, s) == "no-dates"
    assert gate(raw(), {"name": "X", "temporal_start": "1066"}, s) == "no-coords"
    assert gate(raw(), {"name": "X", "temporal_start": "1066", "temporal_end": "1000", "geojson": {"a": 1}}, s) == "end-before-start"
    assert gate(raw(), {"name": "X", "temporal_start": "2010", "geojson": {"a": 1}}, s) == "after-year-max"
    assert gate(raw(), {"name": "X", "temporal_start": "3000", "geojson": {"a": 1}}, s) == "impossible-year"
    assert gate(raw(), {"name": "X", "temporal_start": "1066", "geojson": {"a": 1}}, s) is None


def test_build_maps_tags_and_never_borrows_a_point():
    s = spec()
    no_point = raw(qid="Q2", coords=None, properties={"P17": [{"qid": "Q38", "label": "Italy", "uri": "x"}]},
                   _date_prec={"point_in_time": 7})
    kept, dropped = build([raw(), no_point, raw(qid="Q3", label="")], s)
    assert dropped == Counter({"unmappable": 1})
    first, second = kept
    assert first["geojson"]["coordinates"] == [10.0, 45.0]
    assert first["attributes"]["_bulk"] == {"slice": "test-slice", "sitelinks": 12}
    assert first["impact_score"] == impact_from_sitelinks(12)
    assert "geojson" not in second  # the country's point is never borrowed
    assert second["date_confidence"] == "low"  # century precision
    assert start_precision(no_point) == 7
    assert not any(h["source"] == "wikidata:P17" for h in second.get("_relationship_hints", []))
    assert second["location_name"] == "Italy"  # still named by its country


def test_committed_slices_validate():
    for s in all_slices():
        assert s.id and s.entity_type
