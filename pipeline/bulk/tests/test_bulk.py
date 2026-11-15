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
    no_point = raw(qid="Q2", coords=None, properties={"P17": [{"qid": "Q38", "label": "Italy", "uri": "x"}],
                                                    "P39": [{"qid": "Q61982", "label": "daimyo", "uri": "x"}]},
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
    assert not any(h["source"] in ("wikidata:P17", "wikidata:P39") for h in second.get("_relationship_hints", []))
    assert second["location_name"] == "Italy"  # still named by its country


def test_committed_slices_validate():
    for s in all_slices():
        assert s.id and s.entity_type


def test_part_files_keep_fetch_and_import_state_apart(tmp_path, monkeypatch):
    import pipeline.bulk.store as store_mod
    from pipeline.bulk.__main__ import pending_imports

    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    st = store_mod.SliceStore("test-slice")
    assert st.part_numbers() == [] and pending_imports(st) == []
    for n in (0, 1):
        st.write_part(n, [{"name": "x"}])
        st.write_json(st.meta_path(n), {"records": 1})
    st.write_json(st.import_path(0), {"summary": {"imported": 1}})
    assert st.part_numbers() == [0, 1]
    assert pending_imports(st) == [1]
    st.add_listed([("Q2", 5), ("Q3", 1)], "all")
    st.add_listed([("Q2", 7)], "other")
    assert st.listed() == {"Q2": 7, "Q3": 1}


def test_queue_is_frozen_once_parts_exist(tmp_path, monkeypatch):
    import pipeline.bulk.store as store_mod
    from pipeline.bulk import __main__ as cli
    from pipeline.bulk.spec import Slice

    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    s = Slice(id="test-frozen", entity_type="event_battle", where="?item wdt:P31 wd:Q178561 .", description="t")
    st = store_mod.SliceStore(s.id)
    st.queue_path.write_text("Q1\t9\nQ2\t5\nQ3\t1\n")
    st.write_json(st.meta_path(0), {"records": 1})

    class Boom:
        def sparql(self, q):
            raise AssertionError("must not list again")

    monkeypatch.setattr(cli, "db_qids", lambda: {"Q1"})
    cli.step_qids(s, st, Boom())
    assert [q for q, _ in st.queue()] == ["Q1", "Q2", "Q3"]


def test_split_retry_halves_slow_batches_and_skips_a_hopeless_item(monkeypatch):
    from pipeline.bulk import fetch
    from pipeline.bulk.wdqs import QueryTimeout

    monkeypatch.setattr(fetch, "RETRY_PAUSE", 0)
    done: list[str] = []

    def call(batch):
        if len(batch) > 2 or "Q9" in batch:
            raise QueryTimeout("server timeout")
        done.extend(batch)

    fetch.split_retry(call, [f"Q{i}" for i in range(1, 11)], "test")
    assert sorted(done, key=lambda q: int(q[1:])) == [f"Q{i}" for i in range(1, 11) if i != 9]


def test_approved_reads_ids_and_ignores_comments(tmp_path, monkeypatch):
    import pipeline.bulk.store as store_mod

    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    assert store_mod.approved() == set()
    (tmp_path / "approved.txt").write_text("# wave 1\nslice-a\n\nslice-b  # late\n")
    assert store_mod.approved() == {"slice-a", "slice-b"}


def test_dates_required_only_for_listed_classes():
    s = spec(require_dates_p31=["Q2977"])
    assert gate(raw(p31=["Q2977"]), {"name": "X"}, s) == "no-dates"
    assert gate(raw(p31=["Q16970"]), {"name": "X"}, s) is None
    assert gate(raw(p31=["Q2977"]), {"name": "X", "temporal_start": "1250"}, s) is None


def test_hatnote_lead_falls_back_to_the_description():
    hat = raw(summary="Battle of Cellorigo may refer to either of two battles:", description="battle in 1067")
    kept, _ = build([hat], spec())
    assert "refer to" not in (kept[0].get("summary") or "")


def test_undated_rows_inside_the_exempt_box_are_kept():
    s = spec(require_dates_p31=["Q2977"], require_dates_except_bbox=[-25, 25, 60, 72])
    europe = {"name": "Ardfert Cathedral", "geojson": {"type": "Point", "coordinates": [-9.8, 52.3]}}
    americas = {"name": "Cathedral of Mercedes", "geojson": {"type": "Point", "coordinates": [-58.0, -34.6]}}
    assert gate(raw(p31=["Q2977"]), europe, s) is None
    assert gate(raw(p31=["Q2977"]), americas, s) == "no-dates"
    with pytest.raises(ValueError):
        spec(require_dates_except_bbox=[60, 25, -25, 72])


def person(**kw):
    base = raw(qid="Q9", label="Otto", description="duke", coords=None, wikipedia_title="Otto",
               p31=["Q5"], point_in_time=None)
    return {**base, **kw}


def test_people_drop_century_dates_but_keep_decades():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    century = person(birth_date="901", death_date="1047", _date_prec={"birth_date": 7, "death_date": 9},
                     properties={"P569": [{"qid": None, "label": "0901-01-01T00:00:00Z", "uri": "x"}]})
    decade = person(qid="Q10", birth_date="1870", death_date="1931", _date_prec={"birth_date": 8, "death_date": 9})
    exact = person(qid="Q11", birth_date="1870", death_date="1931", _date_prec={"birth_date": 9, "death_date": 9})
    kept, dropped = build([century, decade, exact], s)
    assert not dropped
    by_qid = {r["wikidata_id"]: r for r in kept}
    assert by_qid["Q9"].get("temporal_start") is None  # "10th century" is not the year 901
    assert by_qid["Q9"]["temporal_end"] == "1047"
    assert "birth_date" not in by_qid["Q9"].get("attributes", {})
    assert by_qid["Q10"]["temporal_start"] == "1870" and by_qid["Q10"]["date_confidence"] == "low"
    assert by_qid["Q11"].get("date_confidence") != "low"
    # with dates required, a person known only to the century is dropped
    only_century = person(qid="Q12", birth_date="-101", death_date="100", _date_prec={"birth_date": 7, "death_date": 7})
    _, dropped = build([only_century], spec(entity_type="person", where="?item wdt:P31 wd:Q5 .", require=["dates"]))
    assert dropped == Counter({"no-dates": 1})


def test_places_keep_century_dates_as_low_confidence_including_the_end():
    battle = raw(point_in_time=None, start_time="1101", end_time="1200",
                 _date_prec={"start_time": 9, "end_time": 7})
    kept, _ = build([battle], spec())
    assert kept[0]["temporal_start"] == "1101" and kept[0]["date_confidence"] == "low"


def test_people_with_contradictory_lifespans_stay_undated():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    legend = person(birth_date="1497", death_date="1623",  # a traditional birth year
                    properties={"P569": [{"qid": None, "label": "1497-01-01T00:00:00Z", "uri": "x"}]})
    reversed_ = person(qid="Q10", birth_date="1900", death_date="1850")
    long_lived = person(qid="Q11", birth_date="1890", death_date="2002")  # 112 years is real
    kept, dropped = build([legend, reversed_, long_lived], s)
    assert not dropped
    by_qid = {r["wikidata_id"]: r for r in kept}
    for q in ("Q9", "Q10"):
        assert by_qid[q].get("temporal_start") is None and by_qid[q].get("temporal_end") is None
        assert "birth_date" not in by_qid[q].get("attributes", {})
    assert by_qid["Q11"]["temporal_start"] == "1890" and by_qid["Q11"]["temporal_end"] == "2002"
    # with dates required, they are dropped as undated
    kept, dropped = build([legend], spec(entity_type="person", where="?item wdt:P31 wd:Q5 .", require=["dates"]))
    assert not kept and dropped == {"no-dates": 1}
    # a long-lived place or event keeps its span
    assert gate(raw(), {"name": "X", "temporal_start": "950", "temporal_end": "1067"}, spec()) is None

def test_a_coarse_date_gives_way_to_a_later_precise_one():
    from pipeline.bulk.fetch import fill_dates
    items = {"Q1": {}, "Q2": {}, "Q3": {}}
    fill_dates(items, {
        ("Q1", "P571"): (1801, 7), ("Q1", "P577"): (1862, 11),   # century inception, exact publication
        ("Q2", "P571"): (1850, 9), ("Q2", "P577"): (1862, 11),   # year inception wins
        ("Q3", "P571"): (1801, 7), ("Q3", "P577"): (1801, 7),    # both coarse: the first stays
    })
    assert items["Q1"]["inception"] == "1862" and items["Q1"]["_date_prec"]["inception"] == 11
    assert items["Q2"]["inception"] == "1850"
    assert items["Q3"]["inception"] == "1801" and items["Q3"]["_date_prec"]["inception"] == 7
