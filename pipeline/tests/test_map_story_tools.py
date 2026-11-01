"""Tests for the map-story authoring tools: layout helpers, the Story recorder,
lint checks, concise check output, research/places parsing, the queue, the
cheatsheet and scripts/agent-costs.py. No network: lookups are monkeypatched."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from pipeline.map_stories import cheatsheet, digest, lint as L, net, places, queue, research
from pipeline.map_stories.__main__ import analyse, cli, report_lines
from pipeline.map_stories.geo import bearing, buffer_ring, distance, great_circle, hull_region, local, merge_rings, offset, point_in_ring
from pipeline.map_stories.layout import (
    Story,
    behind,
    column,
    crescent,
    deploy_line,
    echelon,
    facing_off,
    facing_toward,
    front,
    local_frame,
    route,
    screen,
    when,
    wing,
)
from pipeline.map_stories.preview import step_index
from pipeline.map_stories.schema import UNIT_KINDS
from pipeline.map_stories.validate import validate

REPO = Path(__file__).resolve().parents[2]
O = (16.13, 41.30)
P = local_frame(O)


# ── layout ────────────────────────────────────────────────────────────────


def test_local_frame_and_facing_toward() -> None:
    assert local(P(300, -200), O) == pytest.approx((300, -200), abs=0.5)
    assert facing_toward(P(0, 0), P(0, 500)) == 0
    assert facing_toward({"at": P(0, 0)}, {"at": P(500, 0)}) == 90


def test_front_faces_away_from_the_left_to_right_line() -> None:
    north = front(P(-500, 0), P(500, 0), depth=20)
    assert north["facing"] == 0 and north["width"] == pytest.approx(1000, abs=2)
    assert local(north["at"], O)[1] == pytest.approx(-10, abs=0.5)  # centre sits behind the front edge
    assert front(P(500, 0), P(-500, 0))["facing"] == 180


def test_deploy_line_shares_the_front_by_size() -> None:
    out = deploy_line(P(-1000, 0), P(1000, 0), [("a", 1), ("b", 3), ("c", 1, {"depth": 40, "shape": "line"})], gap=0)
    assert list(out) == ["a", "b", "c"]
    assert sum(p["width"] for p in out.values()) == pytest.approx(2000, abs=3)
    assert out["b"]["width"] == pytest.approx(1200, abs=2)
    assert out["c"]["depth"] == 40 and out["c"]["shape"] == "line"
    xs = [local(p["at"], O)[0] for p in out.values()]
    assert xs == sorted(xs)  # left to right


def test_wing_echelon_crescent_column() -> None:
    w = wing(P(-1000, 0), 0, [("h1", 400), ("h2", 200)], side="left", gap=20)
    assert local(w["h1"]["at"], O)[0] == pytest.approx(-1200, abs=2)
    assert local(w["h2"]["at"], O)[0] == pytest.approx(-1520, abs=2)
    e = echelon(P(0, 0), 0, [("a", 200), ("b", 200)], back=100, side="right", gap=0)
    ea, eb = local(e["a"]["at"], O), local(e["b"]["at"], O)
    assert eb[0] - ea[0] == pytest.approx(200, abs=2) and ea[1] - eb[1] == pytest.approx(100, abs=2)
    c = crescent(P(0, 0), 10, 1500, 200)
    assert c["shape"] == "crescent" and c["curve"] == 200
    col = column([P(0, 0), P(0, 2000)], [("head", 200), ("tail", 200)], spacing=20)
    assert local(col["head"]["at"], O)[1] > local(col["tail"]["at"], O)[1]
    assert col["head"]["facing"] == 0 and col["head"]["shape"] == "column"


def test_behind_screen_and_facing_off_keep_their_distances() -> None:
    base = {"at": P(0, 0), "facing": 0, "width": 600, "depth": 20}
    b = behind(base, 50, depth=30)
    assert local(b["at"], O)[1] == pytest.approx(-(10 + 50 + 15), abs=0.5) and b["width"] == 600
    s = screen(base, gap=40, depth=8)
    assert local(s["at"], O)[1] == pytest.approx(10 + 40 + 4, abs=0.5) and s["shape"] == "line"
    f = facing_off(base, depth=30, gap=4)
    assert f["facing"] == 180 and local(f["at"], O)[1] == pytest.approx(10 + 4 + 15, abs=0.5)


# ── Story ─────────────────────────────────────────────────────────────────

NARR = "The armies moved into position along the river at first light, each commander watching the other for an opening. " * 2


def _story(extra_steps: int = 4) -> dict:
    st = Story()
    st.step("deploy", "The armies deploy", "Dawn", NARR)
    st.place(deploy_line(P(-600, 0), P(600, 0), [("a-inf", 2), ("a-cav", 1)], depth=30))
    st.put("b-inf", at=P(0, 1200), facing=180, width=1200, depth=40)
    st.put("a-gen", at=P(0, -200))
    st.pin("a-gen", "a-inf")
    for i in range(extra_steps):
        st.step(f"s{i}", f"Step {i}", None, NARR)
        st.put("a-inf", move="advance", at=P(-200, 100 * (i + 1)))
    st.note(P(0, 700), "The lines meet", "clash")
    return st.doc(
        slug="battle-of-test", kind="battle", entity={"name": "Battle of Test"}, title="Battle of Test",
        date_label="1 May 1000", year=1000, intro="x" * 300, outcome="The test side won the day.",
        sources=[{"title": "Test source"}],
        sides=[{"id": "a", "name": "A", "color": "#b91c1c"}, {"id": "b", "name": "B", "color": "#1d4ed8"}],
        units=[{"id": "a-inf", "side": "a", "kind": "infantry", "label": "A foot"},
               {"id": "a-cav", "side": "a", "kind": "cavalry", "label": "A horse"},
               {"id": "a-gen", "side": "a", "kind": "commander", "label": "A general"},
               {"id": "b-inf", "side": "b", "kind": "infantry", "label": "B foot"}],
        terrain=[{"id": "town", "kind": "town", "label": "Test", "at": P(0, -800)}],
    )


def test_story_doc_is_valid_and_arrows_start_where_units_stood() -> None:
    doc = _story()
    rep = validate(doc)
    assert rep.ok, rep.errors
    assert not [w for w in rep.warnings if "arrow" in w or "no move arrow" in w]
    s0, s1 = doc["steps"][1], doc["steps"][2]
    assert distance(s1["moves"][0]["path"][0], s0["positions"]["a-inf"]["at"]) < 1
    assert not [i for i in L.lint(doc) if i.code == "arrow-start"]


def test_story_writes_only_changed_keys_and_needs_a_start_for_entering_units() -> None:
    st = Story()
    st.step("one", "One", None, NARR)
    st.put("u", at=P(0, 0), facing=0, width=300)
    st.step("two", "Two", None, NARR)
    st.put("u", at=P(0, 0), facing=0, width=300, state="engaged")
    assert st.s["positions"] == {"u": {"state": "engaged"}}
    with pytest.raises(ValueError):
        st.put("new", move="march", at=P(0, 100))
    st.put("new", move="march", at=P(0, 100), start=P(0, -3000))
    assert st.s["moves"][-1]["path"][0] == [round(v, 6) for v in P(0, -3000)]


def test_pin_resolves_to_the_host_point() -> None:
    st = Story()
    st.step("one", "One", None, NARR)
    st.put("host", at=P(100, 100), facing=0, width=200)
    st.pin("gen", "host")
    assert st.at("gen") == st.at("host") and st.s["positions"]["gen"] == {"with": "host"}


# ── schema-3 geometry ─────────────────────────────────────────────────────

CAFFA, MESSINA, MARSEILLE = (35.38, 45.03), (15.55, 38.19), (5.37, 43.30)


def test_great_circle_and_route_keep_their_waypoints() -> None:
    gc = great_circle(CAFFA, MARSEILLE, 10)
    assert len(gc) == 11 and gc[0] == list(CAFFA) and gc[-1] == list(MARSEILLE)
    # A great circle between two northern points bows north of the straight lon/lat line.
    assert gc[5][1] > (CAFFA[1] + MARSEILLE[1]) / 2
    line = route(CAFFA, MESSINA, MARSEILLE, sea=True)
    assert line[0] == list(CAFFA) and list(MESSINA) in line and line[-1] == list(MARSEILLE)
    assert max(distance(a, b) for a, b in zip(line, line[1:])) <= 100_500
    assert len(route(CAFFA, MESSINA)) > len(line) / 2, "land legs are densified more finely"
    with pytest.raises(ValueError):
        route(CAFFA)


def test_buffer_ring_hull_region_and_merge_rings() -> None:
    ring = buffer_ring(MESSINA, 50, n=12)
    assert len(ring) == 12 and all(abs(distance(MESSINA, p) - 50_000) < 100 for p in ring)
    hull = hull_region([CAFFA, MESSINA, MARSEILLE], 100)
    assert 3 <= len(hull) <= 48
    assert all(point_in_ring(p, hull) for p in ((25.0, 42.0), (15.55, 38.5)))
    assert not point_in_ring((10.0, 55.0), hull)
    assert min(distance(MARSEILLE, p) for p in hull) == pytest.approx(100_000, rel=0.15)
    merged = merge_rings(buffer_ring(MESSINA, 100), buffer_ring((16.5, 38.19), 100), [buffer_ring(CAFFA, 50)])
    assert len(merged) == 2 and all(len(r) >= 3 and r[0] != r[-1] for r in merged)


def test_when_builds_date_specs() -> None:
    assert when(1347, 10) == {"year": 1347, "month": 10}
    assert when(1348, 1, end=(1348, 6, 30)) == {"year": 1348, "month": 1, "end": {"year": 1348, "month": 6, "day": 30}}


def test_story_state_records_feature_state() -> None:
    st = Story()
    st.step("one", "One", None, NARR, date=when(1347))
    st.state("lane", active=True, value_n=3)
    st.state("lane", state="disrupted")
    st.step("two", "Two", None, NARR)
    doc = st.doc(slug="x")
    assert doc["steps"][0]["features"] == {"lane": {"active": True, "value_n": 3, "state": "disrupted"}}
    assert "features" not in doc["steps"][1] and doc["schema"] == 3


# ── lint ──────────────────────────────────────────────────────────────────


def _doc(steps: list[dict], units: list[dict] | None = None, kind: str = "battle") -> dict:
    return {
        "schema": 2, "slug": "t", "kind": kind, "sides": [{"id": "a", "name": "Alpha army"}, {"id": "b", "name": "Beta army"}],
        "units": units or [{"id": "a1", "side": "a", "kind": "infantry", "label": "Alpha foot"},
                           {"id": "a2", "side": "a", "kind": "infantry", "label": "Alpha reserve"},
                           {"id": "b1", "side": "b", "kind": "infantry", "label": "Beta foot"}],
        "steps": steps,
    }


def _codes(doc: dict) -> list[str]:
    return [i.code for i in L.lint(doc)]


def test_same_side_overlap_is_flagged() -> None:
    doc = _doc([{"id": "s", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 400, "depth": 30},
                                          "a2": {"at": P(100, 0), "facing": 0, "width": 400, "depth": 30}}}])
    assert "overlap" in _codes(doc)
    doc["steps"][0]["positions"]["a2"]["at"] = P(0, -60)
    assert "overlap" not in _codes(doc)


def test_opposing_contact_needs_an_engaged_state() -> None:
    pos = {"a1": {"at": P(0, 0), "facing": 0, "width": 400, "depth": 30}, "b1": {"at": P(0, 20), "facing": 180, "width": 400, "depth": 30}}
    assert "contact" in _codes(_doc([{"id": "s", "positions": pos}]))
    pos["b1"]["state"] = "engaged"
    assert "contact" not in _codes(_doc([{"id": "s", "positions": pos}]))


def test_density_uses_strength_n() -> None:
    units = [{"id": "a1", "side": "a", "kind": "infantry", "label": "Alpha foot", "strength_n": 50_000},
             {"id": "b1", "side": "b", "kind": "infantry", "label": "Beta foot"}]
    doc = _doc([{"id": "s", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200, "depth": 20}}}], units)
    assert "density" in _codes(doc)
    doc["steps"][0]["positions"]["a1"].update(width=2000, depth=30)
    assert "density" not in _codes(doc)


def test_camera_flags_units_out_of_view_but_not_frame_false() -> None:
    pos = {"a1": {"at": P(0, 0), "facing": 0, "width": 200}, "b1": {"at": P(9000, 0), "facing": 0, "width": 200}}
    doc = _doc([{"id": "s", "camera": {"center": P(0, 0), "zoom": 15}, "positions": pos}])
    assert "camera" in _codes(doc)
    pos["b1"]["frame"] = False
    assert "camera" not in _codes(doc)


def test_notes_that_overlap_on_screen_are_flagged() -> None:
    pos = {"a1": {"at": P(0, 0), "facing": 0, "width": 200}, "b1": {"at": P(2000, 0), "facing": 0, "width": 200}}
    notes = [{"at": P(1000, 0), "text": "First note here"}, {"at": P(1005, 3), "text": "Second note here"}]
    assert "notes" in _codes(_doc([{"id": "s", "positions": pos, "notes": notes}]))
    notes[1]["at"] = P(1000, -1500)
    assert "notes" not in _codes(_doc([{"id": "s", "positions": pos, "notes": notes}]))


def test_arrows_must_start_near_the_previous_position() -> None:
    steps = [{"id": "s1", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200}}},
             {"id": "s2", "positions": {"a1": {"at": P(0, 800)}}, "moves": [{"unit": "a1", "type": "advance", "path": [P(0, 0), P(0, 800)]}]}]
    assert "arrow-start" not in _codes(_doc(steps))
    steps[1]["moves"][0]["path"][0] = P(1000, 0)
    assert "arrow-start" in _codes(_doc(steps))


def test_beat_arrows_start_from_the_frame_before_their_beat() -> None:
    beats = [{"label": "b1", "positions": {"a1": {"at": P(0, 400)}}, "moves": [{"unit": "a1", "type": "advance", "path": [P(0, 0), P(0, 400)]}]},
             {"label": "b2", "positions": {"a1": {"at": P(0, 900)}}, "moves": [{"unit": "a1", "type": "advance", "path": [P(0, 400), P(0, 900)]}]}]
    steps = [{"id": "s1", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200}}}, {"id": "s2", "beats": beats}]
    assert "arrow-start" not in _codes(_doc(steps))
    beats[1]["moves"][0]["path"][0] = P(0, 0)  # the frame before all the beats: wrong for beat 2
    issues = [i for i in L.lint(_doc(steps)) if i.code == "arrow-start"]
    assert len(issues) == 1 and "arrow beat 2 starts 400 m" in issues[0].msg


def test_lint_scales_with_the_story_kind_and_skips_formations_for_non_military_kinds() -> None:
    pos = {"a1": {"at": P(0, 0), "facing": 0, "width": 400, "depth": 30}, "a2": {"at": P(100, 0), "facing": 0, "width": 400, "depth": 30}}
    assert "overlap" in _codes(_doc([{"id": "s", "positions": pos}]))
    assert "overlap" not in _codes(_doc([{"id": "s", "positions": pos}], kind="epidemic"))
    steps = [{"id": "s1", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200}}},
             {"id": "s2", "positions": {"a1": {"at": P(0, 900_000)}}, "moves": [{"unit": "a1", "type": "sail", "path": [P(0, 150_000), P(0, 900_000)]}]}]
    assert "arrow-start" in _codes(_doc(steps, kind="campaign"))
    assert "arrow-start" not in _codes(_doc(steps, kind="trade_route"))
    assert "framing" not in _codes(_doc(steps, kind="exploration"))


def test_framing_wider_than_the_spread_limit() -> None:
    pos = {"a1": {"at": P(0, 0), "facing": 0, "width": 200}, "b1": {"at": P(30_000, 0), "facing": 0, "width": 200}}
    assert "framing" in _codes(_doc([{"id": "s", "positions": pos}]))
    pos["b1"]["frame"] = False
    assert "framing" not in _codes(_doc([{"id": "s", "positions": pos}]))


def test_static_unit_whose_narrative_says_it_advances() -> None:
    steps = [{"id": "s0", "narrative": "x", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200}}}]
    steps += [{"id": f"s{i}", "narrative": "The Alpha foot advanced steadily on the ridge."} for i in range(1, 6)]
    assert "static" in _codes(_doc(steps))
    for st in steps[1:]:
        st["narrative"] = "Rather than advance, the Alpha foot held the ridge."
    assert "static" not in _codes(_doc(steps))


def test_says_advances_needs_the_unit_as_subject() -> None:
    unit = {"id": "roman-infantry", "label": "Roman infantry"}
    assert L.says_advances("The Roman legions advanced into the hollow.", unit)
    assert not L.says_advances("With the Roman mass deep inside the hollow, the African infantry on each wing turned to face inward and advanced.", unit)


def test_flatten_beats_folds_beats_into_the_step() -> None:
    doc = _doc([{"id": "s", "positions": {"a1": {"at": P(0, 0), "facing": 0, "width": 200}},
                 "beats": [{"label": "b", "positions": {"a1": {"at": P(0, 300)}}, "moves": [{"unit": "a1", "type": "advance", "path": [P(0, 0), P(0, 300)]}]}]}])
    flat = L.flatten_beats(doc)
    assert "beats" not in flat["steps"][0] and flat["steps"][0]["positions"]["a1"]["at"] == P(0, 300)
    assert len(flat["steps"][0]["moves"]) == 1 and "beats" in doc["steps"][0]


# ── check output ──────────────────────────────────────────────────────────


def test_report_is_concise_and_grouped_by_step() -> None:
    doc = _story()
    res = analyse(doc)
    res["warnings"] += [f"step 's0': warning number {i}" for i in range(40)] + ["units never placed: x"]
    lines = report_lines("t", doc, res)
    assert len(lines) <= 20
    assert lines[0].startswith("t: ok")
    assert any(line.startswith("  [s0] warning number 0 · warning number 1") for line in lines)
    assert any(line.startswith("  [story] units never placed") for line in lines)
    assert len(report_lines("t", doc, res, verbose=True)) > 40


def test_check_exit_codes_and_json(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_story()))
    bad = tmp_path / "bad.json"
    broken = _story()
    broken["units"][0]["kind"] = "dragons"
    bad.write_text(json.dumps(broken))
    runner = CliRunner()
    r = runner.invoke(cli, ["check", str(good)])
    assert r.exit_code == 0 and len(r.output.splitlines()) <= 20
    r = runner.invoke(cli, ["check", str(bad)])
    assert r.exit_code == 1 and "ERROR" in r.output
    r = runner.invoke(cli, ["check", "--json", str(good)])
    data = json.loads(r.output)
    assert data["ok"] is True and isinstance(data["lint"], list)


def test_step_index_takes_ids_or_numbers() -> None:
    doc = {"steps": [{"id": "a"}, {"id": "b"}]}
    assert step_index(doc, "b") == 1 and step_index(doc, "1") == 0 and step_index(doc, None) is None
    with pytest.raises(SystemExit):
        step_index(doc, "zz")


def test_build_writes_json_and_reports_concisely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import types

    import pipeline.map_stories.__main__ as main

    fake = types.SimpleNamespace(build=_story)
    monkeypatch.setattr(main.importlib, "import_module", lambda name: fake)
    monkeypatch.setattr(main, "OUT", tmp_path)
    r = CliRunner().invoke(cli, ["build", "battle_of_test"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "battle-of-test.json").exists() and "wrote" in r.output and len(r.output.splitlines()) <= 20


def test_digest_lists_schema_3_links_and_step_entities() -> None:
    doc = {"chronicle": {"slug": "dhows"}, "features": [{"id": "siraf", "kind": "port", "at": [52.3, 27.7], "entity": {"name": "Siraf", "wikidata": "Q4"}},
                                                     {"id": "r", "kind": "region", "region_kind": "extent", "area": []}],
           "steps": [{"id": "a", "title": "T", "narrative": "N", "entry": 3, "entities": [{"name": "Sulaiman", "wikidata": "Q5", "role": "merchant"}],
                      "features": {"r": {"area_from_entity": {"wikidata": "Q6"}}}}]}
    assert digest.links(doc) == [("feature", "Siraf", "Q4"), ("step", "Sulaiman", "Q5"), ("feature", "r", "Q6")]
    text = "\n".join(digest.prose(doc, "a"))
    assert "· entry 3" in text and "entities: Sulaiman (merchant)" in text


def test_digest_lists_links_and_flags_bad_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = {"entity": {"name": "Battle of Hastings", "wikidata": "Q1"},
           "sides": [{"id": "n", "polity": {"name": "Duchy of Normandy", "wikidata": "Q2"}, "commanders": [{"name": "William", "wikidata": "Q3"}]}],
           "units": [{"id": "w", "kind": "commander", "label": "William", "wikidata": "Q3"}], "steps": [{"id": "a", "title": "T", "narrative": "N"}]}
    assert digest.links(doc) == [("entity", "Battle of Hastings", "Q1"), ("polity", "Duchy of Normandy", "Q2"), ("commander", "William", "Q3")]
    wd = {"Q1": {"label": "Battle of Hastings", "p31": ["C1"]}, "Q2": {"label": "Normandy", "p31": ["C2"]},
          "Q3": {"label": "William the Conqueror", "p31": ["C3"]}}
    monkeypatch.setattr(net, "wd_entities", lambda q: wd)
    monkeypatch.setattr(net, "wd_labels", lambda q: {"C1": "battle", "C2": "village", "C3": "human"})
    out = digest.link_lines(doc)
    assert out[0] == "3 links, 1 to check"
    assert [line for line in out if line.startswith("CHECK")][0].endswith("← class")
    text = "\n".join(digest.prose(doc, "a"))
    assert "[a] T" in text and "INTRO" not in text


# ── research ──────────────────────────────────────────────────────────────

EXTRACT = """The battle was fought in 1066.
== Background ==
Some background text.
=== Claims ===
Claimant text here.
== Battle ==
Fighting text.
=== Hillock ===
Hillock text.
== References ==
Ref text.
"""

WIKITEXT = """{{Infobox military conflict
| conflict = Battle of Test
| date = {{Start date|1066|10|14|df=y}}
| place = Near [[Battle, East Sussex|Battle]]
| result = Norman victory{{efn|A footnote [[Footnote target]]}}
| commander1 = {{plainlist|
* {{flagicon|England}} [[Harold Godwinson]] {{KIA}}
* [[Gyrth Godwinson|Gyrth]]
}}
| strength1 = 7,000<ref>Some ref</ref>
}}
Body text."""


def _article() -> research.Article:
    return research.Article("Battle of Test", "Q1", "en", research.split_sections(EXTRACT), WIKITEXT)


def test_sections_outline_and_lookup() -> None:
    art = _article()
    names = [s.name for s in research.kept(art)]
    assert names[0] == "lead" and "References" not in names
    out = research.outline(art)
    assert out[1].strip().startswith("Background") and "Claims" in out[1]
    found, missing = research.find_sections(art, ["hill", "nope"])
    assert found[0][0].name == "Hillock" and missing == ["nope"]
    text = "\n".join(research.section_text(art, ["Background"], 2000))
    assert "### Claims" in text and "Claimant text" in text
    assert "[cut:" in "\n".join(research.section_text(art, ["Background"], 40))


def test_infobox_drops_footnotes_and_collects_live_links() -> None:
    values, links = research.infobox(WIKITEXT)
    assert values["date"] == "1066-10-14"
    assert values["result"] == "Norman victory"
    assert values["commander1"] == "Harold Godwinson †; Gyrth"
    assert values["strength1"] == "7,000"
    assert links["commander1"] == ["Harold Godwinson", "Gyrth Godwinson"]


def test_wikidata_summary_and_time_format() -> None:
    ent = {"id": "Q1", "labels": {"en": {"value": "X"}}, "sitelinks": {"enwiki": {"title": "X"}, "dewiki": {}},
           "claims": {"P31": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"id": "Q178561"}}}}],
                      "P585": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"time": "-0216-08-02T00:00:00Z", "precision": 11}}}}],
                      "P625": [{"mainsnak": {"snaktype": "value", "datavalue": {"value": {"latitude": 41.3, "longitude": 16.13}}}}]}}
    s = net.summarise(ent)
    assert s["p31"] == ["Q178561"] and s["dates"]["P585"] == "-216-08-02" and s["coord"] == [16.13, 41.3] and s["sitelinks"] == 2
    assert net._time({"time": "+1815-06-18T00:00:00Z", "precision": 9}) == "1815"


# ── places ────────────────────────────────────────────────────────────────


def test_places_ranks_in_range_and_marks_ambiguity(monkeypatch: pytest.MonkeyPatch) -> None:
    near = (4.41, 50.68)
    a, b, far = offset(near, east=1000), offset(near, north=-3000), offset(near, east=40_000)
    rows = [{"lon": a[0], "lat": a[1], "category": "place", "type": "farm"},
            {"lon": a[0] + 0.0001, "lat": a[1], "category": "building", "type": "yes"},
            {"lon": b[0], "lat": b[1], "category": "place", "type": "hamlet"},
            {"lon": far[0], "lat": far[1], "category": "place", "type": "town"}]
    monkeypatch.setattr(places, "nominatim", lambda *a, **k: rows)
    hit = places.lookup("Somewhere", near, 15)
    assert hit is not None and hit.km == pytest.approx(1.0, abs=0.01) and hit.source == "osm:place=farm"
    assert len(hit.alts) == 1  # the building next door is the same place; the town is out of range
    line = places.fmt(hit, "Somewhere", near)
    assert "AMBIGUOUS 2" in line and " E " in line
    assert places.compass(bearing(near, b)) == "S"


def test_places_falls_back_to_wikidata(monkeypatch: pytest.MonkeyPatch) -> None:
    near = (4.41, 50.68)
    monkeypatch.setattr(places, "nominatim", lambda *a, **k: [])
    monkeypatch.setattr(places, "wd_search", lambda name: ["Q5"])
    monkeypatch.setattr(places, "wd_entities", lambda q: {"Q5": {"id": "Q5", "coord": list(offset(near, north=500))}})
    hit = places.lookup("La Haye Sainte", near, 15)
    assert hit is not None and hit.source == "wd:Q5"


def test_shape_lines_clips_and_simplifies() -> None:
    near = (16.13, 41.30)
    line = [offset(near, east=x, north=(x % 200) - 100) for x in range(-20_000, 20_001, 100)]
    out = places.shape_lines({"type": "LineString", "coordinates": line}, near, 5, 30, False)
    assert out and sum(len(x) for x in out) <= 30
    assert all(distance(p, near) <= 5050 for x in out for p in x)


# ── queue ─────────────────────────────────────────────────────────────────


def test_slugs_kinds_and_year_tags() -> None:
    assert queue.slugify("Battle of Châlons") == "battle-of-chalons"
    assert queue.year_tag(-216) == "216-bc" and queue.year_tag(1066) == "1066"
    assert queue.kind_of("Battle of Salamis", ["Q1261499"]) == "naval_battle"
    assert queue.kind_of("Siege of Alesia", []) == "siege"
    assert queue.kind_of("Atomic bombing of X", ["Q2656967"]) == "other"
    assert queue.kind_of("Battle of Nowhere", []) == "battle"


def _row(name: str, qid: str, year: int, rels: int = 5, story: str | None = None) -> queue.Row:
    return queue.Row(name, qid, year, rels, 1, 500, True, story)


def test_queue_ranks_dedupes_slugs_and_keeps_statuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wd = {"Q1": {"sitelinks": 90, "p31": ["Q178561"]}, "Q2": {"sitelinks": 10, "p31": ["Q178561"]},
          "Q3": {"sitelinks": 30, "p31": ["Q178561"]}, "Q4": {"sitelinks": 99, "p31": ["Q178561"]},
          "Q5": {"sitelinks": 50, "p31": ["Q3199915"]}}
    monkeypatch.setattr(queue, "wd_entities", lambda qids: wd)
    rows = lambda: [_row("Battle of Foo", "Q1", 1200), _row("Battle of Foo", "Q2", -50), _row("Battle of Bar", "Q3", 900),  # noqa: E731
                    _row("Battle of Done", "Q4", 1000, story="battle-of-done"), _row("Foo massacre", "Q5", 1300)]
    path = tmp_path / "queue.tsv"
    out = queue.build(10, ("battle", "siege", "naval_battle"), path, rows())
    assert [r.qid for r in out] == ["Q1", "Q3", "Q2"]  # the story and the massacre are not candidates
    assert {r.slug for r in out} == {"battle-of-foo-1200", "battle-of-foo-50-bc", "battle-of-bar"}
    text = path.read_text().splitlines()
    assert text[0].split("\t") == list(queue.COLUMNS)
    path.write_text("\n".join(line.replace("\ttodo", "\tskip") if "\tQ3\t" in line else line for line in text) + "\n")
    out = queue.build(1, ("battle",), path, rows())
    assert {(r.qid, r.status) for r in out} == {("Q1", "todo"), ("Q3", "skip")}  # Q3 fell out of the cut but kept its status


# ── cheatsheet ────────────────────────────────────────────────────────────


def test_cheatsheet_is_short_and_reads_the_schema() -> None:
    text = cheatsheet.render()
    # Authors read it instead of the modules; it stays well under a screenful of context.
    assert len(text.splitlines()) < 160
    assert "PLACEMENT_KEYS:" in text
    for kind in UNIT_KINDS:
        assert kind in text
    assert "deploy_line(" in text and "def build()" in text and "intro 250–" in text
    assert "STORIES BEYOND BATTLES" in text and "hull_region(" in text and "route(" in text and "SCHEMA-3 FIELDS" in text


# ── agent-costs ───────────────────────────────────────────────────────────


def test_agent_costs_counts_a_split_response_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("agent_costs", REPO / "scripts" / "agent-costs.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    monkeypatch.setitem(sys.modules, "agent_costs", mod)  # dataclasses look their module up
    spec.loader.exec_module(mod)
    usage = {"input_tokens": 2, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 100, "output_tokens": 50}
    lines = [
        {"type": "assistant", "timestamp": "2026-10-31T10:00:00Z", "message": {"id": "m1", "usage": usage, "content": [{"type": "thinking", "thinking": "…"}]}},
        {"type": "assistant", "timestamp": "2026-10-31T10:00:01Z", "message": {"id": "m1", "usage": usage, "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.map_stories check x.json"}}]}},
        {"type": "user", "timestamp": "2026-10-31T10:00:31Z", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 500}]}},
        {"type": "assistant", "timestamp": "2026-10-31T10:01:00Z", "message": {"id": "m2", "usage": usage, "content": [{"type": "text", "text": "done"}]}},
    ]
    sub = tmp_path / "subagents"
    sub.mkdir()
    (sub / "agent-a1.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    (sub / "agent-a1.meta.json").write_text(json.dumps({"description": "Author Foo map story"}))
    (sub / "agent-a2.jsonl").write_text(json.dumps(lines[0]))
    (sub / "agent-a2.meta.json").write_text(json.dumps({"description": "something else"}))
    found = mod.transcripts(tmp_path, "map story")
    assert [label for _, label in found] == ["Author Foo map story"]
    st = mod.analyse(found[0][0], "x")
    assert st.turns == 2 and st.billed == 2 * (2 + 1000 + 100 + 50) and st.peak == 1102
    assert st.cats["ms:check"].n == 1 and st.cats["ms:check"].secs == pytest.approx(30) and st.wall == pytest.approx(60)
