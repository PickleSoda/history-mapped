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
    kept, dropped = build([raw(), no_point, raw(qid="Q3", label="", wikipedia_title=None)], s)
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


def test_person_lead_about_a_namesake_ship_or_family_falls_back():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    leads = [
        "USS Inch (DE-146) was an Edsall-class destroyer escort in service with the United States Navy.",
        "Z9 Wolfgang Zenker was a Type 1934A-class destroyer built for the Kriegsmarine.",
        "The Mason family of Virginia is a historically significant American political family.",
        "The Firebrace Baronetcy, of London, was a title in the Baronetage of England.",
    ]
    for lead in leads:
        kept, _ = build([person(summary=lead, description="American naval officer")], s)
        assert kept[0]["summary"] == "American naval officer", lead
    own = "The Venerable Bede was a monk whose family is unknown."
    kept, _ = build([person(summary=own)], s)
    assert kept[0]["summary"].startswith("The Venerable Bede")


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


@pytest.mark.parametrize("lead,want", [
    ("Max Waldau (1825 – 1855) was a German poet.", (1825, 1855)),
    ("William Maginn (10 July 1794 – 21 August 1842) was", (1794, 1842)),
    ("Ann (born c. 1843 in Paris; died 1893) was", (1843, 1893)),
    ("Hamuro (fl. 1203–1230) was a poet", (None, None)),
    ("Otto (reigned 1305–1307) was", (None, None)),
    ("Jane (1843 or 1844 – 1893) was", (None, None)),
    ("Kulthum (born 1957) is an Iranian writer", (1957, None)),
    ("Plain lead without a parenthesis, born 1800.", (None, None)),
])
def test_lead_lifespan(lead, want):
    from pipeline.bulk.build import lead_lifespan
    assert lead_lifespan(lead) == want


def _ts(y):
    return {"qid": None, "label": f"{y:04d}-01-01T00:00:00Z", "uri": "x"}


def test_the_lead_picks_among_several_wikidata_years():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    maginn = person(birth_date="1793", death_date="1842", summary="William Maginn (10 July 1794 – 21 August 1842) was an Irish journalist.",
                    properties={"P569": [_ts(1793), _ts(1794)], "P570": [_ts(1842)]})
    lone = person(qid="Q10", birth_date="1793", death_date="1842", summary="Someone (1790 – 1842) was",   # 1790 is not a Wikidata value
                  properties={"P569": [_ts(1793), _ts(1795)]})
    hijri = person(qid="Q11", birth_date="1377", summary="An Iranian writer.", properties={"P569": [_ts(1377), _ts(1957)]})
    hijri_lead = person(qid="Q12", birth_date="1377", summary="Kulthum (born 1957) is an Iranian writer.",
                        properties={"P569": [_ts(1377), _ts(1957)]})
    kept, dropped = build([maginn, lone, hijri, hijri_lead], spec(entity_type="person", where="?item wdt:P31 wd:Q5 .", year_max=1899))
    by = {r["wikidata_id"]: r for r in kept}
    assert by["Q9"]["temporal_start"] == "1794" and by["Q9"]["attributes"]["birth_date"].startswith("1794")
    assert by["Q10"]["temporal_start"] == "1793"          # the lead names no Wikidata value: unchanged
    assert by["Q11"].get("temporal_start") is None         # 580 years apart, no lead: undated
    assert "Q12" not in by and dropped["after-year-max"] == 1   # the lead says 1957: out of range


def test_release_gives_back_only_claims_dropped_for_the_bound(tmp_path, monkeypatch):
    import pipeline.bulk.store as store_mod
    from click.testing import CliRunner

    from pipeline.bulk import __main__ as cli

    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    s = spec(year_max=1950)
    st = store_mod.SliceStore(s.id)
    monkeypatch.setattr(cli, "_load", lambda _id: (s, st))
    raws = [raw(), raw(qid="Q2", point_in_time="1967"), raw(qid="Q3", label="")]
    kept, _ = build(raws, s)
    st.write_raw(0, raws)
    st.write_part(0, kept)
    st.write_json(st.meta_path(0), {"records": len(kept)})
    claims = tmp_path / "claims.tsv"
    claims.write_text("Q1\ttest-slice\nQ2\ttest-slice\nQ3\ttest-slice\nQ4\ttest-slice\nQ2\tother\n")
    dry = CliRunner().invoke(cli.cli, ["release", "test-slice"])
    assert dry.exit_code == 0, dry.output
    assert "Q2\ttest-slice" in claims.read_text()
    run = CliRunner().invoke(cli.cli, ["release", "test-slice", "--yes"])
    assert run.exit_code == 0, run.output
    # kept (Q1), unmappable (Q3) and unfetched (Q4) stay; another slice's line is untouched
    assert claims.read_text() == "Q1\ttest-slice\nQ3\ttest-slice\nQ4\ttest-slice\nQ2\tother\n"


def test_description_gate_drops_sportspeople_but_keeps_the_dual_careers():
    s = spec(entity_type="person", exclude_desc=r"\b(racing driver|football player|footballer)\b",
             keep_desc=r"\b(politician|engineer)\b")
    person = dict(p31=["Q5"], point_in_time=None, coords=None, birth_date="1910", death_date="1980")
    assert gate(raw(**person, description="Scottish racing driver"), {"name": "x", "temporal_start": "1910"}, s) == "excluded-description"
    assert gate(raw(**person, description="American football player and politician"), {"name": "x", "temporal_start": "1910"}, s) is None
    assert gate(raw(**person, description="British physicist"), {"name": "x", "temporal_start": "1910"}, s) is None
    with pytest.raises(ValueError):
        spec(exclude_desc="(unclosed")


def test_a_redirect_into_a_group_article_gives_no_lead():
    from pipeline.bulk import fetch

    class Wiki:
        def wikipedia(self, params):
            return {"query": {
                "redirects": [
                    {"from": "Paul Betz", "to": "Knight's Cross of the Iron Cross"},
                    {"from": "Jean Valjean (saint)", "to": "Martyrs of Lyon", "tofragment": "Jean"},
                    {"from": "Ibn Taymiyya", "to": "Ibn Taymiyyah"},
                ],
                "pages": [
                    {"title": "Knight's Cross of the Iron Cross", "extract": "The Knight's Cross was an award."},
                    {"title": "Martyrs of Lyon", "extract": "The Martyrs of Lyon were Christians."},
                    {"title": "Ibn Taymiyyah", "extract": "Ibn Taymiyyah was a Sunni scholar."},
                ],
            }}

    items = [{"wikipedia_title": t} for t in ("Paul Betz", "Jean Valjean (saint)", "Ibn Taymiyya")]
    fetch.fetch_extracts(Wiki(), items)
    assert [i.get("summary") for i in items] == [None, None, "Ibn Taymiyyah was a Sunni scholar."]


@pytest.mark.parametrize("lead", [
    "This article contains material translated from the Italian Wikipedia's version of this page.",
    "This page was created from the Dutch Wikipedia with the aid of automatic translation",
    "This is a list of German painters.",
    "This article lists the presidents of Honduras.",
])
def test_maintenance_notes_are_not_leads(lead):
    from pipeline.bulk.build import HATNOTE

    assert HATNOTE.search(lead)
    assert not HATNOTE.search("Thisbe was a Babylonian woman in a tale told by Ovid.")


def test_description_gate_keeps_a_titled_cricketer_by_his_label():
    s = spec(entity_type="person", exclude_desc=r"\bcricketer\b", keep_desc=r"\b(earl|politician)\b")
    peer = raw(p31=["Q5"], label="Henry Tufton, 11th Earl of Thanet", description="English cricketer (1775-1849)")
    assert gate(peer, {"name": "x", "temporal_start": "1775"}, s) is None
    assert gate(raw(p31=["Q5"], label="W. G. Grace", description="English amateur cricketer"), {"name": "x"}, s) == "excluded-description"


def test_require_p31_keeps_only_the_listed_classes():
    s = spec(entity_type="trade_route", require_p31=["Q194029"])
    assert gate(raw(p31=["Q194029", "Q34442"]), {"name": "Via Appia", "temporal_start": "-312"}, s) is None
    assert gate(raw(p31=["Q34442"]), {"name": "Arctic Ocean Highway", "temporal_start": "1066"}, s) == "not-required-class"


def test_first_mention_and_service_entry_fill_only_a_missing_inception():
    from pipeline.bulk.fetch import fill_dates

    items = {"Q1": {}, "Q2": {"inception": "1974", "_date_prec": {"inception": 9}}}
    fill_dates(items, {("Q1", "P1249"): (1250, 9), ("Q2", "P1249"): (1250, 9)})
    assert items["Q1"]["inception"] == "1250"
    assert items["Q2"]["inception"] == "1974"  # a town's own inception wins


def test_a_discovery_year_never_replaces_an_ancient_coarse_date():
    from pipeline.bulk.fetch import fill_dates

    bull = {"Q1": {}}
    fill_dates(bull, {("Q1", "P571"): (-2600, 6), ("Q1", "P575"): (1923, 11)})
    assert bull["Q1"]["inception"] == "-2600"
    novel = {"Q2": {}}
    fill_dates(novel, {("Q2", "P571"): (1801, 7), ("Q2", "P577"): (1840, 11)})
    assert novel["Q2"]["inception"] == "1840"


def test_a_held_part_lock_is_skipped_not_awaited(tmp_path):
    from pipeline.bulk.store import try_locked

    path = tmp_path / "part-0000.import.lock"
    with try_locked(path) as first:
        assert first
        with try_locked(path) as second:
            assert not second
    with try_locked(path) as again:
        assert again


def test_a_modern_lead_undates_a_person_wikidata_puts_in_antiquity():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .", require=["dates"])
    modern = person(qid="Q20", label="Kirker Butler", wikipedia_title="Kirker Butler", birth_date="14", summary="Kirker Butler (born October 14, 1977) is an American television writer.")
    old = person(birth_date="1450", death_date="1510",
                 summary="Otto (c. 1450 – 1510) was a duke; a statue of him was unveiled in 1905.")
    ancient = person(qid="Q21", label="Ur-Nammu", wikipedia_title="Ur-Nammu", birth_date="-2112", death_date="-2094",
                     summary="Ur-Nammu (died 2094 BC) was the founder of the Third Dynasty of Ur.")
    kept, dropped = build([modern, old, ancient], s)
    assert [k["name"] for k in kept] == ["Otto", "Ur-Nammu"] and dropped["no-dates"] == 1


def test_exclude_lead_drops_olympians_whose_description_says_only_sailor():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .",
             exclude_lead=r"who competed (?:in|at) the \d{4} (?:summer|winter) olympics", keep_desc=r"\bofficer\b")
    lead = "Knud Degn (11 May 1880 - 16 May 1965) was a Danish sailor who competed in the 1912 Summer Olympics."
    sailor = person(qid="Q30", label="Knud Degn", description="Danish sailor", summary=lead)
    officer = person(qid="Q31", label="Erik Wallerius", description="Swedish naval officer", summary=lead)
    kept, dropped = build([sailor, officer], s)
    assert [k["name"] for k in kept] == ["Erik Wallerius"] and dropped["excluded-description"] == 1


def test_an_item_without_an_english_label_is_named_by_its_article():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    mul_only = person(qid="Q15995833", label="", wikipedia_title="Stephen J. Wojtkowiak (politician)",
                      description="American politician", birth_date="1895", death_date="1945")
    kept, dropped = build([mul_only], s)
    assert kept[0]["name"] == "Stephen J. Wojtkowiak" and not dropped


def test_a_day_precise_lead_corrects_one_end_wikidata_has_far_off():
    s = spec(entity_type="person", where="?item wdt:P31 wd:Q5 .")
    lead = "Alice Muriel Williamson (8 October 1858 – 24 September 1933) was a British novelist."
    off = person(qid="Q40", label="Alice Muriel Williamson", birth_date="1869", death_date="1933", summary=lead,
                 _date_prec={"birth_date": 11, "death_date": 11})
    near = person(qid="Q41", label="Pearl Bergoff", birth_date="1876", death_date="1947",
                  summary="Pearl Bergoff (14 March 1875 – 15 April 1947) was an American strikebreaker.")
    namesake = person(qid="Q42", label="John White", birth_date="1820", death_date="1890",
                      summary="John White (2 May 1850 – 3 June 1931) was a judge.")
    vague = person(qid="Q43", label="Old Man", birth_date="1700", death_date="1780",
                   summary="Old Man (c. 1 May 1690 – 3 June 1780) was a farmer.")
    kept, _ = build([off, near, namesake, vague], s)
    by = {k["wikidata_id"]: (k.get("temporal_start"), k.get("temporal_end")) for k in kept}
    assert by["Q40"] == ("1858", "1933")
    assert by["Q41"] == ("1876", "1947")  # one year off: left alone
    assert by["Q42"] == ("1820", "1890")  # neither end agrees: maybe not this person
    assert by["Q43"] == ("1700", "1780")  # circa
