"""Map-story authoring toolkit: geometry helpers, the validator, and the
committed sample stories (which must stay valid as the schema evolves)."""

import copy
import json
from pathlib import Path

import pytest

from pipeline.map_stories.geo import bearing, dest, distance, local, offset, rel
from pipeline.map_stories.validate import resolve_steps, validate

REPO = Path(__file__).resolve().parents[2]
STORIES = sorted((REPO / "api" / "resources" / "map-stories").glob("*.json"))

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
