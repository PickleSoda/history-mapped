"""OHM ref audit: which name-only OHM links are wrong, and what deactivating them touches."""

from pathlib import Path

from pipeline.audit_ohm_refs import (
    CachedOverpass,
    classify,
    clean_aliases,
    name_match,
    plan_actions,
    qid_dates_disagree,
    replacement_ref,
    rollback_sql,
    year_gap,
)

WARSAW = (21.01, 52.23)
POLAND_ND = (-97.21, 48.15)  # the "Poland" node the name-only linker picked
LA_ROCHELLE = (-1.15, 46.16)


def entity(**kw) -> dict:
    return {"entity_id": "e1", "name": "X", "entity_type": "city", "wikidata_id": "Q1",
            "start_year": None, "end_year": None, **kw}


def node(lon: float, lat: float, **tags) -> dict:
    return {"type": "node", "id": 1, "lon": lon, "lat": lat, "tags": tags}


def judge(e: dict, el: dict, names=None, geo=None, *, same=(), tags=None, trusted=True) -> dict:
    tags = tags or {}
    return classify(e, el, {}, names or [e["name"]], geo or {},
                    same_item=lambda q: q in same,
                    tag_names=lambda q: tags.get(q, ("missing", [])),
                    qid_trusted=trusted)


# ── names ────────────────────────────────────────────────────────────────────
def test_name_match_levels() -> None:
    assert name_match(["Köln", "Cologne"], ["Cologne"]) == "exact"
    assert name_match(["Siege of La Rochelle"], ["La Rochelle"]) == "partial"
    assert name_match(["Johnstown"], ["Town of Johnstown"]) == "partial"
    assert name_match(["Augsburg"], ["Freie Reichsstadt Augsburg"]) == "extended"
    assert name_match(["Ganja"], ["Ganja River"]) == "none"
    assert name_match(["Nghe An"], ["Nghe An Province"]) == "none"
    assert name_match(["Coele-Syria"], ["Provincia Coele Syria"], polity=True) == "extended"
    assert name_match(["Fifth French Republic"], ["Fifth Street"]) == "none"
    assert name_match(["X"], []) == "unnamed"


def test_the_alias_a_link_was_made_by_cannot_vouch_for_it() -> None:
    aliases = ["Fifth Street", "Ve République"]
    assert clean_aliases(aliases, "Fifth Street, Baton Rouge, La Florida, United States") == ["Ve République"]
    assert clean_aliases(aliases, None) == aliases


def test_year_gap_reads_ohm_dates_and_ignores_inverted_ones() -> None:
    assert year_gap(entity(start_year=1977), {"start_date": "1338", "end_date": "1899"}) == 78
    assert year_gap(entity(start_year=1000), {"start_date": "1200"}) == 0  # open end
    assert year_gap(entity(entity_type="event_battle", start_year=1627), {"start_date": "1700"}) == 73
    assert year_gap(entity(start_year=-438, end_year=370), {"start_date": "0480", "end_date": "0107"}) is None
    assert year_gap(entity(), {"start_date": "1800"}) is None


# ── verdicts ─────────────────────────────────────────────────────────────────
def test_another_items_tag_is_wrong_unless_it_redirects_to_the_entitys() -> None:
    e = entity(name="Iona", wikidata_id="Q1514630")
    el = node(-6.4, 56.33, name="Iona", wikidata="Q2230576")
    v = judge(e, el, geo={"p625": [(-120.0, 47.0)]}, tags={"Q2230576": ("ok", ["Iona"])})
    assert v["verdict"] == "WRONG" and v["reasons"] == ["other_qid_tag"]
    assert judge(e, el, same={"Q2230576"})["verdict"] == "OK"


def test_another_item_with_the_entitys_name_at_its_place_is_unsure() -> None:
    e = entity(name="Alcalá de Henares", wikidata_id="Q24012786")
    el = node(-3.364, 40.482, name="Alcalá de Henares", wikidata="Q46940")
    v = judge(e, el, geo={"p625": [(-3.366, 40.484)]}, tags={"Q46940": ("ok", ["Alcalá de Henares"])})
    assert v["verdict"] == "UNSURE" and "tag_item_shares_name_and_place" in v["reasons"]


def test_evidence_from_a_doubtful_qid_cannot_condemn_alone() -> None:
    e = entity(name="Rundetårn", entity_type="infrastructure_monument")
    tagged = node(12.576, 55.681, name="Rundetårn", wikidata="Q1140534")
    assert judge(e, tagged, tags={"Q1140534": ("ok", ["Rundetaarn"])}, trusted=False)["verdict"] == "UNSURE"
    untagged = node(12.576, 55.681, name="Rundetårn")
    v = judge(e, untagged, geo={"p625": [(-3.0, 40.0)]}, trusted=False)
    assert v["verdict"] == "UNSURE" and "entity_qid_suspect" in v["reasons"]


def test_poland_in_north_dakota_is_wrong() -> None:
    e = entity(name="Poland", entity_type="political_entity", wikidata_id="Q36", start_year=966)
    v = judge(e, node(*POLAND_ND, name="Poland", place="hamlet"), geo={"p625": [(19.4, 52.1)], "capitals": [WARSAW]})
    assert v["verdict"] == "WRONG" and v["reasons"] == ["far_from_capital_and_p625>1000km"]


def test_untagged_point_far_from_the_entitys_own_site_is_wrong() -> None:
    e = entity(name="La Rochelle")
    v = judge(e, node(5.0, 45.0, name="La Rochelle"), geo={"p625": [LA_ROCHELLE]})
    assert v["verdict"] == "WRONG" and v["reasons"] == ["far_from_p625>50km"]


def test_untagged_point_with_the_name_at_the_site_is_ok() -> None:
    e = entity(name="Cape Town", start_year=1652)
    v = judge(e, node(18.409, -33.933, name="Cape Town", start_date="1652"), geo={"p625": [(18.424, -33.925)]})
    assert v["verdict"] == "OK" and v["reasons"] == ["name+p625"]
    v = judge(e, node(18.6, -33.9, name="Cape Town"), geo={"p625": [(18.424, -33.925)]})
    assert v["verdict"] == "UNSURE"  # 16 km: the same name, but not quite the site


def test_a_road_with_another_name_is_wrong_even_at_the_site() -> None:
    v = judge(entity(name="Fort Detroit"), node(-83.04, 42.33, name="Fort Street East", highway="primary"),
              geo={"p625": [(-83.045, 42.33)]})
    assert v["verdict"] == "WRONG" and "name_mismatch" in v["reasons"]


def test_a_river_is_another_thing_unless_the_entity_is_one() -> None:
    river = {"type": "relation", "id": 1, "tags": {"name": "Prüm", "waterway": "river"},
             "bounds": {"minlon": 6.33, "minlat": 49.82, "maxlon": 6.48, "maxlat": 50.31}, "members": []}
    v = judge(entity(name="Prüm"), river, geo={"p625": [(6.424, 50.208)]})
    assert v["verdict"] == "WRONG" and "feature_is_waterway" in v["reasons"]
    river["tags"]["name"] = "Orange River"
    assert judge(entity(name="Orange River"), river, geo={"p625": [(6.424, 50.208)]})["verdict"] != "WRONG"


def test_polity_ok_needs_overlapping_dates_and_its_capital_in_the_bbox() -> None:
    e = entity(name="Gazaria", entity_type="political_entity", start_year=1266, end_year=1475)
    rel = {"type": "relation", "id": 1, "members": [],
           "tags": {"name": "Gazaria", "start_date": "1266", "end_date": "1475"},
           "bounds": {"minlon": 33.3, "minlat": 44.35, "maxlon": 36.7, "maxlat": 45.5}}
    geo = {"p625": [(35.37, 45.03)], "capitals": [(35.38, 45.05)]}
    assert judge(e, rel, geo=geo)["verdict"] == "OK"
    rel["tags"]["start_date"], rel["tags"]["end_date"] = "1476", "1500"
    assert judge(e, rel, geo=geo)["reasons"] == ["dates_adjacent"]  # within slack: not wrong, not ok
    rel["tags"]["start_date"], rel["tags"]["end_date"] = "1540", "1554"
    assert judge(e, rel, geo=geo)["verdict"] == "WRONG"


def test_same_place_in_another_era_is_unsure() -> None:
    e = entity(name="Phayao", start_year=1977)
    v = judge(e, node(99.9, 19.17, name="Phayao", start_date="1338", end_date="1899"), geo={"p625": [(99.9, 19.19)]})
    assert v["verdict"] == "UNSURE" and "same_place_other_era" in v["reasons"]


def test_a_qid_whose_dates_contradict_the_entity_where_the_feature_agrees_is_doubtful() -> None:
    trinidad_co = {"dates": {"P571": [1876, 9]}}
    assert qid_dates_disagree(entity(start_year=1514), trinidad_co, {"start_date": "1514-12-23"})
    assert not qid_dates_disagree(entity(start_year=1870), trinidad_co, {"start_date": "1514"})


# ── fetching and acting ──────────────────────────────────────────────────────
def test_overpass_cache_asks_only_for_unseen_ids_and_remembers_missing_ones(tmp_path: Path) -> None:
    asked: list[str] = []

    def live(query: str) -> list[dict]:
        asked.append(query)
        return [{"type": "node", "id": 1, "lon": 0.0, "lat": 0.0}]

    cached = CachedOverpass(tmp_path, live=live, pause=0)
    assert [el["id"] for el in cached("[out:json][timeout:240];node(id:1,2);out;")] == [1]
    assert [el["id"] for el in CachedOverpass(tmp_path, live=live, pause=0)("[out:json][timeout:240];node(id:2,1);out;")] == [1]
    assert asked == ["[out:json][timeout:240];node(id:1,2);out;"]


def test_replacement_primary_is_a_qid_consistent_ref_backing_the_map() -> None:
    refs = [{"geo_ref_id": "wrong", "provider": "ohm", "tag_qid": None, "external_id": "9", "match_role": "primary",
             "geometry_period_id": None},
            {"geo_ref_id": "other", "provider": "ohm", "tag_qid": "Q2", "external_id": "8", "match_role": "candidate",
             "geometry_period_id": "p0"},
            {"geo_ref_id": "wd", "provider": "wikidata", "tag_qid": None, "external_id": "Q1", "match_role": "fallback",
             "geometry_period_id": "p1"},
            {"geo_ref_id": "tagged", "provider": "ohm", "tag_qid": "Q1", "external_id": "7", "match_role": "candidate",
             "geometry_period_id": None}]
    assert replacement_ref(refs, "Q1", {"wrong"}) == "wd"
    refs[3]["geometry_period_id"] = "p2"
    assert replacement_ref(refs, "Q1", {"wrong"}) == "tagged"
    assert replacement_ref(refs[:2], "Q1", {"wrong"}) is None


def test_plan_holds_refs_with_geometry_and_rollback_is_guarded(tmp_path: Path) -> None:
    def row(gid: str, verdict: str, period: str = "") -> dict:
        return {"geo_ref_id": gid, "entity_id": "e1", "qid": "Q1", "verdict": verdict, "reasons": "name_mismatch",
                "geometry_period": period, "is_primary_geo_ref": gid == "a", "effects": "", "_polygon_periods": 0,
                "_active_refs": [{"geo_ref_id": g, "provider": "ohm", "tag_qid": None, "external_id": "1",
                                  "match_role": "primary", "geometry_period_id": None} for g in ("a", "b", "c")],
                "_ref": {"source_meta": {"lat": "1"}, "updated_at": "2026-10-03 14:05:32"}}
    rows = [row("a", "WRONG"), row("b", "WRONG", "territory/POLYGON 1200..1300"), row("c", "OK")]
    plan_actions(rows)
    assert [r["action"] for r in rows] == ["deactivate", "held:geometry_period", "none"]
    assert rows[0]["new_primary_geo_ref"] == "NULL"
    assert rows[0]["effects"] == ""  # b and c stay active, so the entity keeps an OHM link
    sql = rollback_sql(rows, tmp_path / "backup.dump")
    assert "WHERE geo_ref_id = 'a' AND NOT is_active AND source_meta->>'deactivated_by' = 'ohm_ref_audit_20261101'" in sql
    assert "SET primary_geo_ref_id = 'a' WHERE entity_id = 'e1' AND primary_geo_ref_id IS NOT DISTINCT FROM NULL" in sql
    assert "'b'" not in sql
