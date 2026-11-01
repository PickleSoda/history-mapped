"""Map-story authoring toolkit: geometry helpers, the validator, and the
committed sample stories (which must stay valid as the schema evolves)."""

import copy
import json
from pathlib import Path

import pytest

from pipeline.map_stories.geo import bearing, dest, distance, distance_to_line, local, offset, point_in_ring, rel
from pipeline.map_stories.validate import normalise, resolve_beats, resolve_features, resolve_steps, resolve_terrain_state, validate

REPO = Path(__file__).resolve().parents[2]
STORIES = sorted(p for p in (REPO / "api" / "resources" / "map-stories").glob("*.json") if not p.name.startswith("."))

C = (16.13, 41.3)


def test_offset_and_local_are_inverses() -> None:
    p = offset(C, east=1200, north=-800)
    east, north = local(p, C)
    assert east == pytest.approx(1200, abs=0.5)
    assert north == pytest.approx(-800, abs=0.5)


def test_dest_bearing_and_distance_agree() -> None:
    p = dest(C, 135, 2500)
    assert distance(C, p) == pytest.approx(2500, rel=1e-3)
    assert bearing(C, p) == pytest.approx(135, abs=0.1)


def test_rel_puts_the_right_flank_to_the_right_of_the_facing() -> None:
    # Facing north, the right flank is east.
    p = rel(C, 0, right=500)
    assert p[0] > C[0]
    assert p[1] == pytest.approx(C[1], abs=1e-6)


def _doc() -> dict:
    return {
        "schema": 1,
        "slug": "battle-of-test",
        "kind": "battle",
        "entity": {"name": "Battle of Test"},
        "title": "Battle of Test",
        "date_label": "216 BC",
        "year": -216,
        "intro": "x" * 300,
        "outcome": "One side won the day decisively.",
        "sources": [{"title": "A source"}],
        "sides": [
            {"id": "a", "name": "A", "color": "#b91c1c"},
            {"id": "b", "name": "B", "color": "#1d4ed8"},
        ],
        "units": [
            {"id": "foot", "side": "a", "kind": "infantry", "label": "Foot"},
            {"id": "horse", "side": "b", "kind": "cavalry", "label": "Horse"},
            {"id": "general", "side": "a", "kind": "commander", "label": "General"},
        ],
        "terrain": [],
        "steps": [
            {
                "id": f"s{i}",
                "title": f"Step {i}",
                "narrative": "y" * 200,
                "positions": {"foot": {"at": list(C), "width": 800, "depth": 40}, "horse": {"at": offset(C, 0, 900), "width": 300}, "general": {"with": "foot"}} if i == 0 else {},
            }
            for i in range(5)
        ],
    }


def test_a_minimal_story_is_valid() -> None:
    rep = validate(_doc())
    assert rep.errors == []


def test_unknown_references_are_errors() -> None:
    doc = _doc()
    doc["units"][0]["kind"] = "dragons"
    doc["steps"][1]["positions"] = {"ghost": {"at": list(C)}}
    doc["steps"][2]["moves"] = [{"unit": "foot", "type": "teleport", "path": [list(C), offset(C, 10, 10)]}]
    errors = " | ".join(validate(doc).errors)
    assert "'dragons' is not one of" in errors
    assert "positions.ghost: unknown unit" in errors
    assert "type: one of" in errors


def test_a_unit_jumping_without_an_arrow_is_flagged_but_a_pinned_marker_is_not() -> None:
    doc = _doc()
    doc["steps"][1]["positions"] = {"foot": {"at": offset(C, 3000, 0)}}
    warnings = " | ".join(validate(doc).warnings)
    assert "foot moves" in warnings
    assert "general moves" not in warnings


def test_placements_carry_forward_and_hidden_units_drop_out() -> None:
    doc = copy.deepcopy(_doc())
    doc["steps"][1]["positions"] = {"foot": {"state": "engaged"}, "horse": {"state": "hidden"}}
    frames = resolve_steps(doc)
    assert frames[1]["foot"]["at"] == list(C)
    assert frames[1]["foot"]["state"] == "engaged"
    assert "horse" not in frames[1]
    assert frames[1]["general"]["at"] == list(C)


@pytest.mark.parametrize("path", STORIES, ids=[p.stem for p in STORIES])
def test_committed_stories_are_valid(path: Path) -> None:
    rep = validate(json.loads(path.read_text()))
    assert rep.errors == []


# ── schema 2 ──────────────────────────────────────────────────────────────


def _v2() -> dict:
    doc = copy.deepcopy(_doc())
    doc["schema"] = 2
    return doc


def _errors(doc: dict) -> str:
    return " | ".join(validate(doc).errors)


def _warnings(doc: dict) -> str:
    return " | ".join(validate(doc).warnings)


def test_schema_1_2_and_3_are_accepted_but_not_4() -> None:
    assert validate(_doc()).errors == []
    assert validate(_v2()).errors == []
    doc = _v2()
    doc["schema"] = 3
    assert validate(doc).errors == [], "a v2 battle stays valid as schema 3"
    doc["schema"] = 4
    assert "schema: must be 1, 2 or 3" in _errors(doc)


def test_a_schema_1_document_using_a_v2_field_or_value_is_told_to_bump() -> None:
    doc = _doc()
    doc["steps"][0]["light"] = "dawn"
    doc["steps"][0]["positions"]["foot"]["lines"] = 3
    doc["units"][2]["kind"] = "standard"
    doc["steps"][1]["moves"] = [{"unit": "horse", "type": "ram", "path": [offset(C, 0, 900), offset(C, 0, 800)]}]
    errors = _errors(doc)
    assert "step 's0': light need schema 2 — set `schema: 2`" in errors
    assert "positions.foot: lines need schema 2" in errors
    assert "(general).kind: 'standard' needs schema 2" in errors
    assert "moves[0].type: 'ram' needs schema 2" in errors


# 1. off-stage placements and off-map arrows


def test_frame_false_units_and_continues_tails_are_left_out_of_the_spread_check() -> None:
    doc = _v2()
    doc["units"].append({"id": "relief", "side": "b", "kind": "cavalry", "label": "Relief army"})
    doc["steps"][1]["positions"] = {"relief": {"at": offset(C, 35_000, 0), "width": 800, "frame": False}}
    doc["steps"][2]["moves"] = [{"unit": "horse", "type": "retreat", "path": [offset(C, 0, 900), offset(C, 0, 1000)], "continues": {"toward": offset(C, 0, 60_000), "label": "to the capital"}}]
    rep = validate(doc)
    assert rep.errors == []
    assert "km from the story's centre" not in " | ".join(rep.warnings)

    doc["steps"][1]["positions"]["relief"]["frame"] = True
    assert "km from the story's centre" in _warnings(doc)


def test_bad_frame_and_continues_are_errors() -> None:
    doc = _v2()
    doc["steps"][1]["positions"] = {"foot": {"frame": "no"}}
    doc["steps"][2]["moves"] = [{"unit": "horse", "type": "retreat", "path": [offset(C, 0, 900), offset(C, 0, 1000)], "continues": {"label": "away"}}]
    errors = _errors(doc)
    assert "positions.foot.frame: true or false" in errors
    assert "moves[0].continues: {toward: [lon, lat], label?}" in errors


# 2. detach, split and merge


def _split_and_merge() -> dict:
    doc = _v2()
    doc["units"].append({"id": "wing", "side": "a", "kind": "infantry", "label": "Detached wing"})
    doc["steps"][1]["positions"] = {"wing": {"from": "foot", "at": offset(C, 400, 200), "width": 200}}
    doc["steps"][2]["positions"] = {"wing": {"into": "foot"}}
    return doc


def test_a_detached_unit_starts_from_its_parent_and_a_merged_one_leaves_the_field() -> None:
    doc = _split_and_merge()
    assert validate(doc).errors == []
    frames = resolve_steps(doc)
    assert frames[1]["wing"]["from"] == "foot"
    assert frames[2]["wing"]["at"] == list(C), "a merging unit ends on its target"
    assert "wing" not in frames[3], "and is off the field afterwards"
    assert "from" not in (resolve_steps(doc)[2]["wing"])


def test_a_detachment_far_from_its_parent_without_an_arrow_is_flagged() -> None:
    doc = _split_and_merge()
    doc["steps"][1]["positions"]["wing"]["at"] = offset(C, 3000, 0)
    assert "wing moves" in _warnings(doc)


def test_from_and_into_must_reference_units_on_the_field() -> None:
    doc = _split_and_merge()
    doc["steps"][1]["positions"]["horse"] = {"state": "hidden"}
    doc["steps"][2]["positions"]["wing"]["into"] = "horse"
    doc["units"].append({"id": "ghost", "side": "a", "kind": "infantry", "label": "Ghost"})
    doc["steps"][3]["positions"] = {"ghost": {"from": "wing", "at": list(C), "width": 100}, "foot": {"from": "general"}}
    errors = _errors(doc)
    assert "positions.wing.into: 'horse' is not on the field in this step" in errors
    assert "positions.ghost.from: 'wing' was not on the field in the previous step" in errors
    assert "positions.foot.from: foot is already on the field" in errors


# 3. beats


def _beats() -> dict:
    doc = _v2()
    doc["steps"][1]["beats"] = [
        {"label": "The horse feign flight", "positions": {"horse": {"at": offset(C, 0, 2000)}}, "moves": [{"unit": "horse", "type": "feint", "path": [offset(C, 0, 900), offset(C, 0, 2000)]}]},
        {"label": "…then wheel on the pursuers", "positions": {"horse": {"at": offset(C, 0, 700), "state": "engaged"}}, "moves": [{"unit": "horse", "type": "charge", "path": [offset(C, 0, 2000), offset(C, 0, 700)]}]},
    ]
    return doc


def test_resolve_beats_returns_the_frame_before_the_beats_then_one_per_beat() -> None:
    doc = _beats()
    assert validate(doc).errors == []
    frames = resolve_beats(doc, 1)
    assert [f["horse"]["at"] for f in frames] == [offset(C, 0, 900), offset(C, 0, 2000), offset(C, 0, 700)]
    assert resolve_steps(doc)[1] == frames[-1], "the step resolves to the frame after its last beat"
    assert resolve_steps(doc)[2]["horse"]["state"] == "engaged", "and that frame carries forward"
    assert len(resolve_beats(doc, 0)) == 1


def test_the_teleport_check_runs_per_beat() -> None:
    doc = _beats()
    doc["steps"][1]["beats"][1]["moves"] = []
    assert "step 's1' beat 2: horse moves" in _warnings(doc)


def test_beats_need_a_label_and_positions_or_moves_and_at_most_four() -> None:
    doc = _beats()
    doc["steps"][1]["beats"][0].pop("label")
    doc["steps"][1]["beats"].append({"label": "Nothing happens"})
    doc["steps"][2]["beats"] = [{"label": "b", "moves": [{"unit": "foot", "type": "advance", "path": [list(C), list(C)]}]}] * 5
    errors = _errors(doc)
    assert "beats[0].label: missing" in errors
    assert "beats[2]: needs `positions` or `moves`" in errors
    assert "step 's2'.beats: 5 beats (at most 4)" in errors


# 4. terrain state


def test_terrain_state_carries_forward_and_can_be_cleared() -> None:
    doc = _v2()
    doc["terrain"] = [{"id": "farm", "kind": "farm", "label": "Farm", "at": offset(C, 0, 400)}]
    doc["steps"][1]["terrain_state"] = {"farm": {"held_by": "a", "state": "held"}}
    doc["steps"][2]["terrain_state"] = {"farm": {"state": "burning"}}
    doc["steps"][3]["terrain_state"] = {"farm": {"held_by": None, "state": "destroyed"}}
    assert validate(doc).errors == []
    states = resolve_terrain_state(doc)
    assert states[0] == {}
    assert states[2]["farm"] == {"held_by": "a", "state": "burning"}
    assert states[4]["farm"] == {"state": "destroyed"}


def test_terrain_state_must_reference_terrain_and_sides() -> None:
    doc = _v2()
    doc["terrain"] = [{"id": "farm", "kind": "farm", "label": "Farm", "at": list(C)}]
    doc["steps"][1]["terrain_state"] = {"castle": {"held_by": "a"}, "farm": {"held_by": "z", "state": "ablaze"}}
    errors = _errors(doc)
    assert "terrain_state.castle: unknown terrain" in errors
    assert "terrain_state.farm.held_by: unknown side 'z'" in errors
    assert "terrain_state.farm.state: one of held" in errors


# 5. light, wind and sun


def test_light_wind_and_sun() -> None:
    doc = _v2()
    doc["steps"][0].update({"light": "dawn", "wind": {"from": 135, "strength": "strong", "label": "Volturnus"}, "sun": {"from": 90}})
    assert validate(doc).errors == []
    doc["steps"][1].update({"light": "noon", "wind": {"strength": "gale"}, "sun": {"from": "east"}})
    errors = _errors(doc)
    assert "step 's1'.light: one of night, dawn, day, dusk" in errors
    assert "step 's1'.wind: {from: degrees, strength?, label?}" in errors
    assert "step 's1'.sun: {from: degrees, label?}" in errors


# 6. formation detail, composite units, contingents, new kinds and states


def test_formation_detail_composite_units_and_contingents() -> None:
    doc = _v2()
    doc["sides"][0]["contingents"] = [{"id": "allies", "name": "Allies", "color": "#ea580c", "wikidata": "Q8680"}, {"id": "levy", "name": "Levy"}]
    doc["units"][0].update({"contingent": "allies", "strength_n": 9000, "ranks": [{"kind": "archers", "share": 0.3}, {"kind": "heavy_infantry", "share": 0.7}]})
    doc["units"].append({"id": "eagle", "side": "a", "kind": "standard", "label": "Eagle"})
    doc["steps"][0]["positions"]["foot"].update({"lines": 3, "lanes": 4, "subunits": 10, "strength_n": 8000})
    doc["steps"][0]["positions"]["eagle"] = {"with": "foot"}
    doc["steps"][3]["positions"] = {"eagle": {"at": offset(C, 0, 100), "state": "captured", "by": "b"}, "general": {"state": "killed"}}
    rep = validate(doc)
    assert rep.errors == []
    assert rep.warnings == []


def test_bad_formation_detail_contingents_and_states() -> None:
    doc = _v2()
    doc["sides"][0]["contingents"] = [{"id": "allies", "name": "Allies", "color": "orange", "wikidata": "8680"}]
    doc["units"][0].update({"contingent": "levy", "ranks": [{"kind": "archers", "share": 1.5}]})
    doc["steps"][0]["positions"]["foot"].update({"lines": 6, "subunits": 0})
    doc["steps"][2]["positions"] = {"foot": {"state": "captured"}}
    errors = _errors(doc)
    assert "contingents[0].color: #rrggbb" in errors
    assert "contingents[0].wikidata: a Q-id like Q8680" in errors
    assert "(foot).contingent: 'levy' is not a contingent of side 'a'" in errors
    assert "(foot).ranks[0]: {kind: a unit kind, share: 0–1}" in errors
    assert "positions.foot.lines: a whole number 1–5" in errors
    assert "positions.foot.subunits: a whole number 1–24" in errors
    assert "positions.foot.state: 'captured' needs `by: <side id>`" in errors


def test_a_state_that_does_not_fit_the_kind_is_a_warning() -> None:
    doc = _v2()
    doc["steps"][2]["positions"] = {"foot": {"state": "sunk"}, "general": {"state": "wounded"}}
    rep = validate(doc)
    assert rep.errors == []
    assert "positions.foot.state: 'sunk' is for warship, ship, transport, fleet, merchant_ship, not infantry" in " | ".join(rep.warnings)
    assert "general.state" not in " | ".join(rep.warnings)


def test_a_placement_key_the_atlas_ignores_is_a_warning() -> None:
    doc = _v2()
    doc["steps"][2]["positions"] = {"foot": {"kind": "heavy_cavalry", "conjectural": True}}
    rep = validate(doc)
    assert rep.errors == []
    assert "positions.foot: unknown key(s) kind (the atlas ignores them)" in " | ".join(rep.warnings)


# 7. naval


def _naval() -> dict:
    doc = _v2()
    doc["kind"] = "naval_battle"
    doc["terrain"] = [
        {"id": "strait", "kind": "sea", "label": "Strait", "area": [offset(C, -3000, -3000), offset(C, 3000, -3000), offset(C, 3000, 3000), offset(C, -3000, 3000)]},
        {"id": "islet", "kind": "island", "label": "Islet", "area": [offset(C, 1000, 1000), offset(C, 1600, 1000), offset(C, 1600, 1600), offset(C, 1000, 1600)]},
        {"id": "shore", "kind": "coast", "label": "Shore", "line": [offset(C, -3000, 3000), offset(C, 3000, 3000)]},
    ]
    doc["units"][0]["kind"] = "warship"
    doc["units"][1]["kind"] = "warship"
    doc["units"].append({"id": "hoplites", "side": "a", "kind": "heavy_infantry", "label": "Hoplites"})
    doc["steps"][0]["positions"]["hoplites"] = {"at": offset(C, 1300, 1300), "width": 200}
    doc["steps"][1]["positions"] = {"horse": {"at": offset(C, 0, 600)}}
    doc["steps"][1]["moves"] = [
        {"unit": "horse", "type": "ram", "path": [offset(C, 0, 900), offset(C, 0, 600)], "orient": "path"},
        {"unit": "foot", "type": "back_water", "path": [list(C), list(C)]},
        {"side": "b", "type": "blockade", "path": [offset(C, -2000, 2500), offset(C, 2000, 2500)]},
    ]
    doc["steps"][2]["positions"] = {"horse": {"state": "sunk"}}
    return doc


def test_naval_moves_and_ships_on_water_pass() -> None:
    rep = validate(_naval())
    assert rep.errors == []
    assert rep.warnings == []


def test_ships_ashore_and_troops_afloat_are_flagged_unless_landing() -> None:
    doc = _naval()
    doc["steps"][3]["positions"] = {"foot": {"at": offset(C, 0, 3300)}, "hoplites": {"at": offset(C, 500, 500)}}
    doc["steps"][3]["moves"] = [{"unit": "foot", "type": "advance", "path": [list(C), offset(C, 0, 3300)]}, {"unit": "hoplites", "type": "march", "path": [offset(C, 1300, 1300), offset(C, 500, 500)]}]
    warnings = _warnings(doc)
    assert "step 's3': hoplites (heavy_infantry) stands in the sea" in warnings
    assert "foot" not in warnings, "a ship within 400 m of the coast is afloat"

    doc["steps"][3]["positions"]["foot"]["at"] = offset(C, 0, 4000)
    doc["steps"][3]["moves"][0]["path"][-1] = offset(C, 0, 4000)
    doc["steps"][3]["moves"][1]["type"] = "landing"
    warnings = _warnings(doc)
    assert "foot (warship) is not on water" in warnings
    assert "step 's3': hoplites" not in warnings, "a unit on a landing move may start afloat"


def test_the_land_and_water_check_is_skipped_without_water_terrain() -> None:
    doc = _v2()
    doc["units"][0]["kind"] = "warship"
    assert "not on water" not in _warnings(doc)


def test_a_bad_orient_is_an_error() -> None:
    doc = _naval()
    doc["steps"][1]["moves"][0]["orient"] = "bow"
    assert "moves[0].orient: one of path" in _errors(doc)


# extras


def test_conjectural_alt_sites_fire_targets_mask_and_long_uncertainty() -> None:
    doc = _v2()
    doc["uncertainty"] = "u" * 1400
    doc["alt_sites"] = [{"at": offset(C, 2000, 0), "label": "Right bank", "note": "Older theory"}]
    doc["terrain"] = [{"id": "fill", "kind": "mask", "label": "Landfill", "area": [offset(C, 0, 0), offset(C, 100, 0), offset(C, 100, 100)], "conjectural": True}]
    doc["steps"][0]["positions"]["horse"]["conjectural"] = True
    doc["steps"][1]["moves"] = [{"unit": "foot", "type": "fire", "path": [list(C), offset(C, 0, 900)], "target": "horse", "arc": True, "conjectural": True}]
    doc["steps"][1]["notes"] = [{"at": list(C), "text": "Somewhere here", "conjectural": True}]
    rep = validate(doc)
    assert rep.errors == []
    assert rep.warnings == []


def test_bad_extras_are_errors() -> None:
    doc = _v2()
    doc["alt_sites"] = [{"at": list(C)}]
    doc["terrain"] = [{"id": "t", "kind": "town", "label": "T", "at": list(C), "conjectural": "maybe"}]
    doc["steps"][1]["moves"] = [{"unit": "foot", "type": "fire", "path": [list(C), offset(C, 0, 900)], "target": "nobody", "arc": 1}]
    errors = _errors(doc)
    assert "alt_sites[0]: {at, label, note?}" in errors
    assert "(t).conjectural: true or false" in errors
    assert "moves[0].target: unknown unit 'nobody'" in errors
    assert "moves[0].arc: true or false" in errors


def test_geo_point_in_ring_and_distance_to_line() -> None:
    ring = [offset(C, -100, -100), offset(C, 100, -100), offset(C, 100, 100), offset(C, -100, 100)]
    assert point_in_ring(C, ring)
    assert not point_in_ring(offset(C, 150, 0), ring)
    line = [offset(C, -500, 300), offset(C, 500, 300)]
    assert distance_to_line(C, line) == pytest.approx(300, abs=1)
    assert distance_to_line(offset(C, 900, 300), line) == pytest.approx(400, abs=1)


# ── schema 3 ──────────────────────────────────────────────────────────────

CAFFA, CPL, MESSINA = (35.38, 45.03), (28.97, 41.01), (15.55, 38.19)


def _v3() -> dict:
    """An epidemic: no sides, one side-less ship, dated steps, features."""
    return {
        "schema": 3,
        "slug": "plague-test",
        "kind": "epidemic",
        "entity": {"name": "Black Death", "wikidata": "Q42005"},
        "title": "Plague test",
        "date_label": "1346–1348",
        "year": 1346,
        "ambient": True,
        "intro": "x" * 300,
        "outcome": "The plague reached the whole Mediterranean.",
        "sources": [{"title": "A source"}],
        "sides": [],
        "units": [{"id": "galleys", "kind": "merchant_ship", "label": "Genoese galleys"}],
        "features": [
            {"id": "caffa", "kind": "outbreak", "label": "Caffa", "at": list(CAFFA), "entity": {"name": "Feodosia", "wikidata": "Q129323"}},
            {"id": "sea-lane", "kind": "route", "route_kind": "trade", "line": [list(CAFFA), list(CPL), list(MESSINA)], "goods": ["grain"], "active": False},
            {"id": "plague", "kind": "region", "region_kind": "spread", "area": [offset(CAFFA, -50_000, -50_000), offset(CAFFA, 50_000, -50_000), offset(CAFFA, 0, 50_000)]},
        ],
        "steps": [
            {"id": "s0", "title": "Caffa", "narrative": "y" * 200, "date": {"year": 1346}, "positions": {"galleys": {"at": list(CAFFA)}},
             "entities": [{"name": "Golden Horde", "wikidata": "Q79965", "role": "besieger", "show": True}]},
            {"id": "s1", "title": "Constantinople", "narrative": "y" * 200, "date": {"year": 1347, "month": 5, "end": {"year": 1347, "month": 7}},
             "positions": {"galleys": {"at": list(CPL)}}, "moves": [{"unit": "galleys", "type": "spread", "path": [list(CAFFA), list(CPL)]}],
             "features": {"sea-lane": {"active": True, "value_n": 40, "value_label": "40 ships"}, "caffa": {"state": "infected"}}},
            {"id": "s2", "title": "Messina", "narrative": "y" * 200, "date": {"year": 1347, "month": 10, "day": 1},
             "positions": {"galleys": {"at": list(MESSINA)}}, "moves": [{"unit": "galleys", "type": "sail", "path": [list(CPL), list(MESSINA)]}],
             "features": {"plague": {"area": [[list(CAFFA), list(CPL), offset(CPL, 0, 90_000)], [list(MESSINA), offset(MESSINA, 50_000, 0), offset(MESSINA, 0, 50_000)]], "intensity": 0.6},
                          "sea-lane": {"state": "disrupted"}}},
        ],
    }


def test_a_schema_3_story_without_sides_is_valid() -> None:
    rep = validate(_v3())
    assert rep.errors == []
    assert rep.warnings == []


def test_features_and_terrain_are_aliases_but_not_both() -> None:
    doc = _v3()
    doc["terrain"] = doc.pop("features")
    doc["steps"][1]["terrain_state"] = doc["steps"][1].pop("features")
    assert validate(doc).errors == []
    assert normalise(doc)["features"][0]["id"] == "caffa" and "terrain_state" not in normalise(doc)["steps"][1]
    doc["features"] = doc["terrain"]
    doc["steps"][1]["features"] = {}
    errors = _errors(doc)
    assert "features and terrain: give one" in errors
    assert "step 's1': features and terrain_state: give one" in errors


def test_a_v2_document_using_v3_fields_or_values_is_told_to_bump() -> None:
    doc = _v2()
    doc["ambient"] = False
    doc["features"] = doc.pop("terrain")
    doc["steps"][0]["date"] = {"year": -216}
    doc["units"][2]["kind"] = "army"
    doc["steps"][1]["moves"] = [{"unit": "horse", "type": "sail", "path": [offset(C, 0, 900), offset(C, 0, 800)]}]
    errors = _errors(doc)
    assert "document: ambient, features need schema 3 — bump schema to 3" in errors
    assert "step 's0': date need schema 3" in errors
    assert "(general).kind: 'army' needs schema 3" in errors
    assert "moves[0].type: 'sail' needs schema 3" in errors
    doc = _v2()
    doc["kind"] = "epidemic"
    doc["terrain"] = [{"id": "r", "kind": "region", "region_kind": "spread", "area": [[list(C), offset(C, 0, 100), offset(C, 100, 0)]]}]
    errors = _errors(doc)
    assert "kind: 'epidemic' needs schema 3" in errors
    assert "(r).kind: 'region' needs schema 3" in errors
    assert "(r): region_kind need schema 3" in errors
    assert "(r).area: a list of rings needs schema 3" in errors


def test_date_specs() -> None:
    doc = _v3()
    doc["steps"][0]["date"] = {"year": 1346, "month": 2, "day": 29}
    assert validate(doc).errors == []
    doc["steps"][0]["date"] = {"year": 1346, "month": 13}
    doc["steps"][1]["date"] = {"year": 1347, "month": 4, "day": 31}
    doc["steps"][2]["date"] = {"year": 1347, "day": 3, "end": {"year": 1346}}
    errors = _errors(doc)
    assert "step 's0'.date.month: 1–12" in errors
    assert "step 's1'.date.day: 1–30" in errors
    assert "step 's2'.date.day: needs a month" in errors
    doc["steps"][2]["date"] = {"year": 1347, "month": 10, "end": {"year": 1347, "month": 9}}
    assert "step 's2'.date.end: before the start" in _errors(doc)
    doc["steps"][2]["date"] = {"year": 1347, "end": {"year": 1347, "month": 9, "end": {"year": 1348}}}
    assert "date.end.end: only a step date has an end" in _errors(doc)


def test_period_year_and_date_order() -> None:
    doc = _v3()
    doc["period"] = {"start": {"year": 1346}, "end": {"year": 1353}}
    assert validate(doc).warnings == []
    doc["period"] = {"start": {"year": 1346}, "end": {"year": 1345}}
    assert "period.end: before the start" in _errors(doc)
    doc["period"] = {"start": {"year": 1346}, "end": {"year": 1347}}
    doc["year"] = 1347
    doc["steps"][1]["date"] = {"year": 1345}
    warnings = _warnings(doc)
    assert "step 's1': dated before the previous step" in warnings
    assert "step 's1': date lies outside the period" in warnings
    assert "year: 1347, but the story starts in 1346" in warnings


def test_ambient_stories_date_every_step() -> None:
    doc = _v3()
    del doc["steps"][2]["date"]
    assert "step 's2'.date: an ambient story dates every step" in _errors(doc)
    doc["ambient"] = False
    assert validate(doc).errors == []
    doc["ambient"] = "yes"
    assert "ambient: true or false" in _errors(doc)


def test_a_story_belongs_to_an_entity_or_a_chronicle() -> None:
    doc = _v3()
    del doc["entity"]
    assert "entity or chronicle: a story belongs to" in _errors(doc)
    doc["chronicle"] = {"slug": "indian-ocean-dhow-trade"}
    assert validate(doc).errors == []
    doc["chronicle"] = {"title": "Dhows"}
    assert "chronicle: {slug} of an existing chronicle" in _errors(doc)


def test_chronicle_entries_are_0_based_sequence_orders_and_unique() -> None:
    doc = _v3()
    doc["chronicle"] = {"slug": "indian-ocean-dhow-trade"}
    doc["steps"][0]["entry"] = 0
    doc["steps"][1]["entry"] = 4
    assert validate(doc).errors == []
    doc["steps"][2]["entry"] = 4
    doc["steps"][1]["entry"] = -1
    errors = _errors(doc)
    assert "step 's1'.entry: the entry's sequence_order as stored, an integer ≥ 0" in errors
    doc["steps"][1]["entry"] = 4
    assert "step 's2'.entry: entry 4 already has a step" in _errors(doc)
    del doc["chronicle"]
    assert "entry: only a chronicle's story keys steps to entries" in _errors(doc)


def test_side_is_optional_only_without_sides() -> None:
    doc = _v3()
    assert validate(doc).errors == []
    doc["sides"] = [{"id": "genoa", "name": "Genoa", "color": "#b91c1c"}]
    assert "(galleys).side: unknown side 'None'" in _errors(doc)
    doc["units"][0]["side"] = "genoa"
    doc["features"][0]["side"] = "venice"
    assert "(caffa).side: unknown side 'venice'" in _errors(doc)


def test_multipolygon_areas() -> None:
    doc = _v3()
    doc["features"][2]["area"] = [doc["features"][2]["area"], [list(MESSINA), offset(MESSINA, 9000, 0), offset(MESSINA, 0, 9000)]]
    assert validate(doc).errors == []
    doc["features"][2]["area"][1] = [list(MESSINA)]
    assert "(plague): a region needs `area`: a ring of ≥3 points, or a list of such rings" in _errors(doc)


def test_feature_kinds_need_their_route_or_region_kind() -> None:
    doc = _v3()
    del doc["features"][1]["route_kind"]
    doc["features"][2]["region_kind"] = "blob"
    doc["features"][0]["route_kind"] = "trade"
    doc["features"][0]["goods"] = "grain"
    errors = _errors(doc)
    assert "(sea-lane).route_kind: a route needs one of trade" in errors
    assert "(plague).region_kind: a region needs one of spread" in errors
    assert "(caffa).route_kind: only a route has one" in errors
    assert "(caffa).goods: a list of short names" in errors


def test_feature_state_fields() -> None:
    doc = _v3()
    doc["steps"][0]["features"] = {"plague": {"area_from_entity": {"wikidata": "Q79965"}}}
    assert validate(doc).errors == []
    doc["steps"][0]["features"] = {
        "plague": {"area_from_entity": {"name": "Golden Horde"}, "intensity": 2},
        "sea-lane": {"area_from_entity": {"wikidata": "Q1"}, "value_n": -3, "active": "yes", "state": "closed"},
        "caffa": {"line": [list(CAFFA), list(CPL)]},
    }
    errors = _errors(doc)
    assert "plague.area_from_entity: {wikidata} or {entity_id}" in errors
    assert "plague.intensity: a number 0–1" in errors
    assert "sea-lane.area_from_entity: on an area feature only" in errors
    assert "sea-lane.value_n: a number ≥ 0" in errors
    assert "sea-lane.active: true or false" in errors
    assert "sea-lane.state: one of held" in errors
    assert "caffa.line: ≥2 points, on a line feature only" in errors


def test_step_entities_and_legend() -> None:
    doc = _v3()
    doc["legend"] = [{"swatch": "#7f1d1d", "label": "Plague reached", "style": "fill"}]
    assert validate(doc).errors == []
    doc["legend"] = [{"swatch": "red", "label": "x"}, {"swatch": "#7f1d1d", "label": "y", "style": "hatch"}]
    doc["steps"][0]["entities"] = [{"wikidata": "Q79965"}, {"name": "Genoa", "wikidata": "Genoa", "show": "yes"}]
    errors = _errors(doc)
    assert "legend[0]: {swatch: #rrggbb, label, style?}" in errors
    assert "legend[1].style: one of fill, line, dot" in errors
    assert "entities[0].name: missing" in errors
    assert "entities[1].wikidata: a Q-id" in errors
    assert "entities[1].show: true or false" in errors


def test_scale_follows_the_story_kind() -> None:
    doc = _v3()
    assert "km from the story's centre" not in _warnings(doc)  # Caffa to Messina is ~1,800 km
    doc["steps"][2]["moves"] = []
    assert "galleys moves" not in _warnings(doc), "an epidemic allows 2,000 km between steps"
    doc["kind"] = "campaign"
    warnings = _warnings(doc)
    assert "galleys moves" in warnings
    doc["kind"] = "diffusion"
    assert "lie more than 5000 km" not in _warnings(doc)


def test_resolve_features_carries_each_key_and_replaces_geometry() -> None:
    frames = resolve_features(_v3())
    assert frames[0]["sea-lane"]["active"] is False
    assert frames[1]["sea-lane"]["active"] is True and frames[1]["sea-lane"]["value_n"] == 40
    assert frames[2]["sea-lane"]["value_n"] == 40 and frames[2]["sea-lane"]["state"] == "disrupted"
    assert frames[2]["caffa"]["state"] == "infected" and frames[2]["caffa"]["at"] == list(CAFFA)
    assert len(frames[2]["plague"]["area"]) == 2 and frames[1]["plague"]["area"][0] == offset(CAFFA, -50_000, -50_000)
    doc = _v3()
    doc["steps"][2]["features"]["plague"] = {"area_from_entity": {"wikidata": "Q79965"}}
    last = resolve_features(doc)[2]["plague"]
    assert "area" not in last and last["area_from_entity"] == {"wikidata": "Q79965"}
    doc["steps"][2]["features"]["caffa"] = {"state": None}
    assert "state" not in resolve_features(doc)[2]["caffa"]
