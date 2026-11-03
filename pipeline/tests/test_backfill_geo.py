"""Geo backfill: which OHM feature (or Wikidata site) gives an entity its map point."""

from pipeline.backfill_geo import (
    OHM_TIER,
    WIKIDATA_TIER,
    km,
    ohm_point,
    period_years,
    pick_ohm,
    plan_points,
    point_years,
)

LIUZHOU = (109.41, 24.32)
NANNING = (108.37, 22.82)


def entity(**kw) -> dict:
    return {"entity_id": "e1", "name": "X", "entity_type": "city", "wikidata_id": "Q1",
            "start_year": 1000, "end_year": None, "primary_geo_ref_id": None,
            "has_wikidata_point": False, **kw}


def ref(external_type: str, external_id: int, role: str = "primary", start=1800, end=None) -> dict:
    return {"geo_ref_id": f"r{external_id}", "external_type": external_type, "external_id": str(external_id),
            "match_role": role, "temporal_start_year": start, "temporal_end_year": end}


def relation(rid: int, members=(), bounds=None, qid="Q1") -> dict:
    el = {"type": "relation", "id": rid, "tags": {"wikidata": qid},
          "members": [{"type": t, "ref": r, "role": role} for t, r, role in members]}
    if bounds:
        el["bounds"] = dict(zip(("minlon", "minlat", "maxlon", "maxlat"), bounds))
    return el


def test_node_and_way_positions() -> None:
    assert ohm_point({"type": "node", "lon": 2.0, "lat": 41.0}, {}) == (2.0, 41.0, "node")
    assert ohm_point({"type": "way", "center": {"lon": 3.0, "lat": 50.0}}, {}) == (3.0, 50.0, "way_centre")


def test_relation_prefers_admin_centre_then_label_then_a_compact_bbox() -> None:
    nodes = {7: (12.5, 41.9), 8: (10.0, 40.0)}
    both = relation(1, [("way", 5, "outer"), ("node", 8, "label"), ("node", 7, "admin_centre")], (5, 35, 20, 47))
    assert ohm_point(both, nodes) == (12.5, 41.9, "admin_centre")
    label = relation(1, [("node", 8, "label")], (5, 35, 20, 47))
    assert ohm_point(label, nodes) == (10.0, 40.0, "label")
    compact = relation(1, bounds=(27.0, -30.7, 29.5, -28.5))  # Basutoland-sized
    assert ohm_point(compact, nodes) == (28.25, -29.6, "bbox_centre")


def test_a_sprawling_relation_without_a_label_gives_no_point() -> None:
    empire = relation(1, bounds=(-180, -50, 180, 75))  # the British Empire's bbox centre is at sea
    assert ohm_point(empire, {}) is None


def test_only_a_feature_tagged_with_the_entitys_qid_is_accepted() -> None:
    elements = {("node", 1): {"type": "node", "id": 1, "lon": -97.2, "lat": 48.2, "tags": {}},
                ("node", 2): {"type": "node", "id": 2, "lon": 21.0, "lat": 52.2, "tags": {"wikidata": "Q99"}}}
    pick, reason = pick_ohm(entity(entity_type="political_entity"), [ref("node", 1), ref("node", 2)], elements, {}, None)
    assert pick is None and reason == "ohm:qid_mismatch"


def test_a_point_far_from_the_entitys_own_wikidata_site_is_rejected() -> None:
    elements = {("node", 1): {"type": "node", "id": 1, "lon": LIUZHOU[0], "lat": LIUZHOU[1], "tags": {"wikidata": "Q1"}}}
    assert km(LIUZHOU, NANNING) > 50
    pick, reason = pick_ohm(entity(), [ref("node", 1)], elements, {}, NANNING)
    assert pick is None and reason == "ohm:disagrees_with_wikidata"
    # A polity's Wikidata coordinate is a centroid, so it can't veto its capital.
    pick, _ = pick_ohm(entity(entity_type="political_entity"), [ref("node", 1)], elements, {}, NANNING)
    assert pick is not None


def test_best_ref_is_a_real_node_then_primary_then_longest() -> None:
    nodes = {9: (12.5, 41.9)}
    elements = {
        ("relation", 1): relation(1, bounds=(10, 40, 14, 44)),
        ("relation", 2): relation(2, [("node", 9, "admin_centre")], (10, 40, 14, 44)),
        ("relation", 3): relation(3, [("node", 9, "admin_centre")], (10, 40, 14, 44)),
    }
    refs = [ref("relation", 1), ref("relation", 2, "candidate", -500, -400), ref("relation", 3, "candidate", -500, -200)]
    pick, _ = pick_ohm(entity(entity_type="political_entity"), refs, elements, nodes, None)
    assert pick[0]["external_id"] == "3" and pick[1][2] == "admin_centre"


def test_years_come_from_the_entity_then_the_ref() -> None:
    assert period_years(entity(start_year=805, end_year=None), ref("node", 1, start=1800)) == (805, None)
    assert period_years(entity(start_year=None), ref("node", 1, start=1800, end=1900)) == (1800, 1900)
    assert period_years(entity(start_year=None), ref("node", 1, start=None)) is None
    assert period_years(entity(start_year=None)) is None


def test_plan_falls_back_to_wikidata_only_for_point_types() -> None:
    city = entity(entity_id="c", wikidata_id="Q1")
    polity = entity(entity_id="p", wikidata_id="Q2", entity_type="political_entity")
    placed_before = entity(entity_id="w", wikidata_id="Q3", has_wikidata_point=True)
    meta = {q: {"coordinates": "Point(2.0 41.0)"} for q in ("Q1", "Q2", "Q3")}
    planned, _, skipped, _ = plan_points([city, polity, placed_before], {}, {}, {}, meta)
    assert set(planned) == {"c"} and planned["c"]["tier"] == WIKIDATA_TIER
    assert skipped["area_type_without_ohm_point"] == 1


def test_an_ohm_point_replaces_this_scripts_earlier_wikidata_point() -> None:
    e = entity(entity_id="w", has_wikidata_point=True)
    elements = {("node", 1): {"type": "node", "id": 1, "lon": 2.0, "lat": 41.0, "tags": {"wikidata": "Q1"}}}
    meta = {"Q1": {"coordinates": "Point(2.01 41.01)"}}
    planned, _, _, _ = plan_points([e], {"w": [ref("node", 1)]}, elements, {}, meta)
    assert planned["w"]["tier"] == OHM_TIER and planned["w"]["extid"] == "node/1"


def test_the_attested_span_is_the_last_resort_and_is_marked() -> None:
    attested = entity(start_year=None, attested_start=1134, attested_end=1218)
    assert point_years(attested) == (1134, 1218, "attested")
    assert point_years(attested, ref("node", 1, start=1100)) == (1100, None, "ohm_ref")
    assert point_years(entity(start_year=805, attested_start=1134, attested_end=1218)) == (805, None, "entity")
    assert point_years(entity(start_year=None)) is None


def test_a_point_placed_on_attested_years_is_medium_confidence() -> None:
    e = entity(entity_id="a", start_year=None, attested_start=-25, attested_end=150)
    planned, _, _, _ = plan_points([e], {}, {}, {}, {"Q1": {"coordinates": "Point(34.2 26.2)"}})
    p = planned["a"]
    assert (p["start"], p["end"], p["years_from"], p["confidence"]) == (-25, 150, "attested", "medium")


def test_a_living_city_stays_on_the_map_from_its_first_attested_year() -> None:
    carcassonne = entity(entity_id="c", start_year=None, attested_start=1348, attested_end=1348)
    ruin = entity(entity_id="g", wikidata_id="Q2", start_year=None, attested_start=-1550, attested_end=-1550)
    meta = {"Q1": {"coordinates": "Point(2.35 43.21)", "populated": True},
            "Q2": {"coordinates": "Point(30.95 29.2)", "populated": False}}
    planned, _, _, _ = plan_points([carcassonne, ruin], {}, {}, {}, meta)
    assert (planned["c"]["start"], planned["c"]["end"]) == (1348, None)
    assert (planned["g"]["start"], planned["g"]["end"]) == (-1550, -1550)


def test_a_relation_across_the_antimeridian_gives_no_bbox_point() -> None:
    fiji = relation(1, bounds=(-179.9, -21.0, 179.9, -16.0))  # corners 25 km apart, centre in the Atlantic
    assert ohm_point(fiji, {}) is None
    labelled = relation(1, [("node", 5, "label")], bounds=(-179.9, -21.0, 179.9, -16.0))
    assert ohm_point(labelled, {5: (178.4, -18.1)}) == (178.4, -18.1, "label")
