"""Map-point audit: which existing points are wrong, and what replaces them."""

from pipeline.audit_points import (
    OhmIndex,
    Point,
    assess,
    find_issues,
    is_area,
    km_outside_bbox,
    norm_lon,
    origin,
    plan,
    rollback_sql,
    wd_point,
)
from pipeline.backfill_geo import OHM_TIER, WIKIDATA_TIER

LONDON = (-0.1275, 51.507222)
PARIS = (2.352222, 48.856667)
FRANCE = (2.0, 47.0)
NO_OHM = OhmIndex({}, {}, {})


def rec(lonlat=None, p31=(), links=None, label="X") -> dict:
    out = {"status": "ok", "label": label, "p31": list(p31), "links": links or {}}
    out["coord"] = [lonlat[1], lonlat[0]] if lonlat else None
    return out


def ref(ext: str, source: str, active: bool = True) -> dict:
    return {"geo_ref_id": f"g-{ext}", "external_id": ext, "is_active": active, "source": source,
            "geometry_period_id": None}


def point(lonlat=LONDON, **kw) -> Point:
    base = dict(kind="period", entity_id="e1", name="X", type="person", group="POLITY", qid="Q1",
                lon=lonlat[0], lat=lonlat[1], gp_id="gp1", created_by="pipeline:campaign_x",
                start=1800, end=1850)
    base.update(kw)
    return Point(**base)


WD = {
    "Q84": rec(LONDON, ["Q515"], label="London"),
    "Q90": rec(PARIS, ["Q515"], label="Paris"),
    "Q142": rec(FRANCE, ["Q6256", "Q3624078"], label="France"),
}


def test_geometry_helpers() -> None:
    assert norm_lon(184.87476) == -175.12524 or abs(norm_lon(184.87476) + 175.12524) < 1e-9
    assert wd_point(rec((10.0, 20.0))) == (10.0, 20.0)
    assert wd_point(None) is None
    bounds = {"minlon": 0.0, "minlat": 0.0, "maxlon": 10.0, "maxlat": 10.0}
    assert km_outside_bbox((5.0, 5.0), bounds) == 0.0
    assert 1100 < km_outside_bbox((20.0, 5.0), bounds) < 1120
    assert is_area(WD["Q142"]) and not is_area(WD["Q84"])


def test_a_birthplace_point_is_borrowed() -> None:
    wd = {**WD, "Q1": rec(None, links={"P19": ["Q84"]})}
    p = point(wd_refs=[ref("Q84", "wikidata_place_of_association")])
    assert origin(p, wd) == ("borrowed", "Q84", "P19")


def test_own_p625_and_backfill_points_are_the_entitys_own() -> None:
    wd = {**WD, "Q1": rec(LONDON)}
    assert origin(point(wd_refs=[ref("Q84", "wikidata_place_of_association")]), wd)[0] == "own_p625"
    assert origin(point(created_by=OHM_TIER), WD)[0] == "ohm_own"
    assert origin(point(created_by=WIKIDATA_TIER), WD)[0] == "own_p625"
    assert origin(point(created_by="derive:located_at"), WD)[0] == "derived"


def test_a_chronicle_centroid_is_recognised_under_the_own_or_an_old_qid() -> None:
    wd = {**WD, "Q1": rec(None)}
    assert origin(point((-12.27, 45.09), wd_refs=[ref("Q1", "chronicle_centroid")]), wd)[0] == "centroid"
    assert origin(point((-12.27, 45.09), qid=None, wd_refs=[ref("Q9", "chronicle_centroid")]), wd)[0] == "centroid"


def test_the_p625_of_a_qid_the_entity_no_longer_carries_is_stale() -> None:
    wd = {**WD, "Q1": rec(None), "Q9": rec(PARIS)}
    assert origin(point(PARIS, wd_refs=[ref("Q9", "wikidata_p625")]), wd) == ("stale_qid", "Q9", "P625")


def test_clustered_borrowed_person_point_is_deleted() -> None:
    wd = {**WD, "Q1": rec(None, links={"P19": ["Q84"]})}
    p = point(wd_refs=[ref("Q84", "wikidata_place_of_association")], cluster_n=130)
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "delete" and "birthplace" in v.reason


def test_an_event_located_in_a_city_is_kept() -> None:
    wd = {**WD, "Q1": rec(None, links={"P276": ["Q84"]})}
    p = point(type="event_treaty", group="EVENT", wd_refs=[ref("Q84", "wikidata_place_of_association")],
              cluster_n=130)
    assert assess(p, wd, NO_OHM, set(), set()).action == "keep"


def test_an_event_located_in_a_country_sits_on_a_centroid_and_goes() -> None:
    wd = {**WD, "Q1": rec(None, links={"P276": ["Q142"]})}
    p = point(FRANCE, type="event_rebellion", group="EVENT",
              wd_refs=[ref("Q142", "wikidata_place_of_association")], cluster_n=50)
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "delete" and "centroid" in v.reason


def test_a_qidless_polity_on_a_borrowed_country_point_goes() -> None:
    # Funan, whose QID was cleared, sat on France's centroid.
    p = point(FRANCE, type="political_entity", qid=None, wd_refs=[ref("Q142", "wikidata_place_of_association")],
              cluster_n=50)
    v = assess(p, WD, NO_OHM, set(), set())
    assert v.action == "delete"


def test_a_point_type_far_from_its_own_p625_is_replaced_by_it() -> None:
    wd = {**WD, "Q1": rec(PARIS)}
    p = point(LONDON, type="event_battle", group="EVENT")
    issues = find_issues(p, origin(p, wd)[0], wd, NO_OHM)
    assert issues and issues[0].startswith("far_from_p625")
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "replace" and v.new["tier"] == WIKIDATA_TIER
    assert (round(v.new["lon"], 4), round(v.new["lat"], 4)) == (round(PARIS[0], 4), round(PARIS[1], 4))
    assert (v.new["start"], v.new["end"], v.new["years_from"]) == (1800, 1850, "existing")


def test_a_clustered_centroid_with_an_own_site_is_replaced() -> None:
    wd = {**WD, "Q1": rec(PARIS)}
    p = point((-12.27, 45.09), type="infrastructure_monument", group="PLACE",
              wd_refs=[ref("Q1", "chronicle_centroid")], cluster_n=66)
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "replace" and v.new["extid"] == "Q1"


def test_a_polity_p625_never_places_it() -> None:
    # A centroid polity with its own P625 but no OHM point: deleted, not moved to the P625.
    wd = {**WD, "Q1": rec(PARIS)}
    p = point((-12.27, 45.09), type="political_entity", wd_refs=[ref("Q1", "chronicle_centroid")], cluster_n=66)
    assert assess(p, wd, NO_OHM, set(), set()).action == "delete"


def test_a_polity_far_outside_its_ohm_relation_moves_to_its_label_node() -> None:
    wd = {**WD, "Q1": rec(None)}
    rel = {"type": "relation", "id": 5, "tags": {"wikidata": "Q1", "name": "Funan"},
           "members": [{"type": "node", "ref": 9, "role": "label"}],
           "bounds": {"minlon": 100.0, "minlat": 10.0, "maxlon": 106.0, "maxlat": 14.0}}
    ohm = OhmIndex({"e1": [{"geo_ref_id": "r5", "external_type": "relation", "external_id": "5",
                            "match_role": "primary", "temporal_start_year": 100, "temporal_end_year": 600}]},
                   {("relation", 5): rel}, {9: (104.9, 11.5)})
    p = point(FRANCE, type="political_entity", name="Funan")
    v = assess(p, wd, ohm, set(), set())
    assert any(i.startswith("outside_ohm") for i in v.issues)
    assert v.action == "replace" and v.new["tier"] == OHM_TIER and v.new["kind"] == "label"
    # A feature that only carries the QID by mistake (no shared name, no own coordinate) is not taken.
    rel["tags"]["name"] = "Sisak"
    assert assess(p, wd, ohm, set(), set()).action == "delete"


def test_a_feature_across_the_antimeridian() -> None:
    from pipeline.audit_points import bbox_centre

    fiji = {"minlat": -21.8, "minlon": 174.6, "maxlat": -15.7, "maxlon": -178.2}
    assert km_outside_bbox((178.0, -18.0), fiji) == 0.0
    assert km_outside_bbox((-1.8, -18.7), fiji) > 15000
    lon, lat = bbox_centre(fiji)
    assert abs(lon - 178.2) < 0.01 and abs(lat + 18.75) < 0.01
    # backfill_geo put the Kingdom of Fiji at the raw average, (-1.8, -18.7), in the Atlantic.
    wd = {**WD, "Q1": rec(None)}
    rel = {"type": "relation", "id": 5, "tags": {"wikidata": "Q1", "name": "Matanitu o Viti", "name:en": "Kingdom of Fiji"},
           "members": [],
           "bounds": fiji}
    ohm = OhmIndex({"e1": [{"geo_ref_id": "r5", "external_type": "relation", "external_id": "5",
                            "match_role": "primary", "temporal_start_year": 1871, "temporal_end_year": 1874}]},
                   {("relation", 5): rel}, {})
    p = point((-1.80004, -18.72612), type="political_entity", name="Kingdom of Fiji", created_by=OHM_TIER)
    v = assess(p, {**wd, "Q1": rec(None, label="Kingdom of Fiji")}, ohm, set(), set())
    assert v.action == "replace" and abs(v.new["lon"] - 178.2) < 0.01


def test_excluded_and_story_entities_are_not_written() -> None:
    wd = {**WD, "Q1": rec(None, links={"P19": ["Q84"]})}
    p = point(wd_refs=[ref("Q84", "wikidata_place_of_association")], cluster_n=130)
    assert assess(p, wd, NO_OHM, {"e1"}, set()).action == "skip_excluded"
    assert assess(point(entity_id="a05afb75-x", wd_refs=p.wd_refs, cluster_n=130), wd, NO_OHM, set(),
                  set()).action == "skip_excluded"
    assert assess(p, wd, NO_OHM, set(), {"Q1"}).action == "list"


def test_an_admin_only_point_is_only_cleared() -> None:
    wd = {**WD, "Q1": rec(PARIS)}
    p = point((-12.27, 45.09), kind="location", gp_id=None, type="city", group="PLACE",
              wd_refs=[ref("Q1", "chronicle_centroid")], cluster_n=66)
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "null_location" and v.new is None


def test_unknown_origin_in_a_cluster_is_listed_not_changed() -> None:
    wd = {**WD, "Q1": rec(None)}
    assert assess(point(cluster_n=40), wd, NO_OHM, set(), set()).action == "list"


def test_a_derived_copy_of_a_removed_point_goes_too() -> None:
    wd = {**WD, "Q1": rec(None, links={"P19": ["Q84"]})}
    target = point(entity_id="t1", wd_refs=[ref("Q84", "wikidata_place_of_association")], cluster_n=6)
    copy = point(entity_id="e2", qid=None, gp_id="gp2", type="event_battle", group="EVENT",
                 created_by="derive:located_at", target_id="t1", cluster_n=6)
    kept = point(entity_id="e3", qid=None, gp_id="gp3", type="event_battle", group="EVENT",
                 created_by="derive:located_at", target_id="t9", cluster_n=6)
    good_target = point(entity_id="t9", qid="Q84", gp_id="gp9", type="city", group="PLACE")
    stale = point(PARIS, entity_id="e4", qid=None, gp_id="gp4", type="event_battle", group="EVENT",
                  created_by="derive:located_at", target_id="t9")
    out = {p.entity_id: v for p, v in plan([target, copy, kept, good_target, stale], wd, NO_OHM, set(), set())}
    assert out["t1"].action == "delete"
    assert out["e2"].action == "delete" and out["e2"].issues[-1].startswith("derived_from_bad_point")
    assert out["e3"].action == "keep"
    assert out["e4"].action == "delete" and out["e4"].issues == ["stale_copy"]


def test_a_derived_place_whose_p625_contradicts_its_target_is_listed() -> None:
    # West Park, an imperial garden in Beijing, carries the QID of West Park, Florida.
    beijing, florida = (116.39, 39.91), (-80.2, 25.98)
    wd = {**WD, "Q1": rec(florida), "Q956": rec(beijing, ["Q515"], label="Beijing")}
    p = point(beijing, type="infrastructure_monument", group="PLACE", created_by="derive:located_at",
              target_id="t1", target_qid="Q956")
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "list" and "located_at target" in v.reason
    wd["Q1"] = rec((116.38, 39.93))  # its own site, a few km off: nothing to fix
    assert assess(p, wd, NO_OHM, set(), set()) is None


def test_rollback_reinserts_the_old_period_before_detaching_and_deleting_the_new() -> None:
    old = {"geometry_period_id": "old", "entity_id": "e1", "period_type": "territory", "start_year": "1800",
           "end_year": None, "geom": "0101", "territory_geom": None, "description": "it's", "provenance_mode":
           "ohm_import", "relationship_id": None, "source_event_id": None, "created_by": "pipeline:x",
           "created_at": None, "updated_at": None, "confidence": "medium"}
    new = {**old, "geometry_period_id": "new", "geom": "0202", "created_by": WIKIDATA_TIER}
    ref_before = {"geo_ref_id": "r1", "entity_id": "e1", "external_id": "Q1", "temporal_start": None,
                  "temporal_end": None, "temporal_start_year": None, "temporal_end_year": None,
                  "external_tags": None, "source_meta": '{"source": "chronicle_centroid"}', "match_score": "0.2",
                  "is_active": "true", "created_at": None, "updated_at": None, "provider": "wikidata",
                  "external_type": "qid", "match_role": "fallback", "retrieval_method": "rest",
                  "geometry_period_id": None}
    ref_after = {**ref_before, "source_meta": '{"source": "wikidata_p625"}', "match_score": "0.9",
                 "geometry_period_id": "new"}
    loc = {"location_id": "l1", "entity_id": "e1", "location_name": "X", "geom": "0101", "territory_geom": None,
           "location_method": "wikidata", "location_confidence": None, "is_primary": "true", "notes": None,
           "created_at": None, "updated_at": None}
    before = {"periods": {"old": old}, "refs": {"r1": ref_before}, "locations": {"l1": loc},
              "primary_geo_ref_id": None}
    after = {"periods": {"new": new}, "refs": {"r1": ref_after}, "locations": {"l1": {**loc, "geom": "0202"}},
             "primary_geo_ref_id": "r1"}
    sql = rollback_sql("e1", before, after)
    text = "\n".join(sql)
    ins = next(i for i, s in enumerate(sql) if s.startswith("INSERT INTO geometry_periods"))
    upd = next(i for i, s in enumerate(sql) if s.startswith("UPDATE entity_geo_refs"))
    dele = next(i for i, s in enumerate(sql) if s.startswith("DELETE FROM geometry_periods"))
    assert ins < upd < dele
    assert "'it''s'" in text and "'0101'::geometry" in text
    assert "geometry_period_id = NULL" in sql[upd] and "IS NOT DISTINCT FROM 'new'" in sql[upd]
    assert "UPDATE entities SET primary_geo_ref_id = NULL" in text
    assert "UPDATE entity_locations SET geom = '0101'::geometry" in text
    assert "geom = '0202'::geometry" in sql[dele]


def test_an_admin_location_left_on_a_centroid_follows_the_own_map_point() -> None:
    from pipeline.audit_points import assess_location_mismatch

    wd = {**WD, "Q1": rec(None)}
    ohm_point = (15.19, -6.16)
    p = point(ohm_point, type="political_entity", created_by=OHM_TIER, loc_pt=(2.688, 11.268),
              loc_method="wikidata", loc_id="l1")
    v = assess_location_mismatch(p, {}, wd, set())
    assert v.action == "sync_location" and (v.new["lon"], v.new["lat"]) == ohm_point
    # A human-set location, or one on the entity's own P625, is left alone.
    assert assess_location_mismatch(point(ohm_point, created_by=OHM_TIER, loc_pt=(2.688, 11.268),
                                          loc_method="human_assigned"), {}, wd, set()) is None
    wd_own = {**WD, "Q1": rec((2.688, 11.268))}
    assert assess_location_mismatch(p, {}, wd_own, set()) is None
    # A campaign point of unknown origin is not trusted to overwrite anything.
    assert assess_location_mismatch(point(ohm_point, loc_pt=(2.688, 11.268), loc_method="wikidata"),
                                    {}, wd, set()) is None


def test_a_city_that_is_also_a_territory_is_a_site() -> None:
    assert not is_area(rec(LONDON, ["Q515", "Q1048835"]))           # London
    assert not is_area(rec((139.7, 35.7), ["Q50337", "Q174844"]))    # Tokyo, a prefecture too
    assert is_area(rec((35.0, 39.0), ["Q34763"]))                    # Anatolia, a peninsula
    assert is_area(rec((112.5, -7.7), ["Q5098"]))                    # East Java, a province


def test_an_object_in_a_museum_is_not_placed_at_the_museum() -> None:
    museum = (-0.127, 51.519)
    wd = {**WD, "Q1": rec(None, links={"P276": ["Q6373"]}),
          "Q6373": rec(museum, ["Q33506", "Q207694"], label="British Museum")}
    p = point(museum, type="infrastructure_monument", group="PLACE", name="Rosetta Stone",
              wd_refs=[ref("Q6373", "wikidata_place_of_association")], cluster_n=10)
    v = assess(p, wd, NO_OHM, set(), set())
    assert v.action == "delete" and "museum" in v.reason
