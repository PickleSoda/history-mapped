"""Everything a builder author needs on one screen (under 150 lines).

    python -m pipeline.map_stories cheatsheet

The vocabulary is read from schema.py and the text limits from validate.py at
run time, and the helper signatures from geo.py and layout.py, so the sheet
follows the toolkit as it changes. Authors read this instead of the modules.
"""

from __future__ import annotations

import inspect
import re
import textwrap
from pathlib import Path

from pipeline.map_stories import geo, layout, schema

CLI = "scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.map_stories"

COMMANDS = """\
research "<Title>"|Qid               outline (sections + sizes) and infobox: date, coords, sides, commanders [Qids], strength, losses
research <ref> --section A "B c"     plain text of those sections ('lead' = intro); --max-chars N (default 6000)
research --qids Q1 Q2 …              label, dates, class and description of each Q-id: link only Q-ids confirmed here
places "A" "B" … --near LON,LAT|Qid  coordinates, source, distance; AMBIGUOUS when two matches lie in range; --elevation
places "Fiume X" --near … --geometry river|stream|coast|lake|woods|marsh|ridge|road   simplified line as a Python literal
build <module>                       run stories/<module>.py → validate + lint → api/resources/map-stories/<slug>.json
check <json> [--verbose|--json]      ≤20 lines: counts, then issues by step; exit 1 only on errors
preview <json>                       contact sheet of every step (one PNG); --step ID for one step at 900×600
digest <json> [--links|--step ID]    the story's prose without coordinates; --links checks every Q-id's label/class
queue [--limit N]                    ranked battles without a story → output/map-stories/queue.tsv"""

SKELETON = '''\
"""Battle of X, <date> — map story builder. Anchors: <what each came from>."""
from pipeline.map_stories.geo import arc, bearing, distance, ellipse, mid, offset, rel
from pipeline.map_stories.layout import Story, behind, crescent, deploy_line, facing_off, local_frame, screen, wing

ANCHOR = (lon, lat)            # from research/places, never guessed
P = local_frame(ANCHOR)        # P(east_m, north_m)
RIVER = [[…], […]]             # pasted from `places … --geometry river`

def build() -> dict:
    st = Story()
    st.step("deployment", "The armies deploy", "Dawn", """2–6 sentences of original prose.""")
    st.place(deploy_line(P(-900, 0), P(900, 0), [("a-left", 3), ("a-centre", 5), ("a-right", 3)], depth=30))
    st.put("a-horse", wing(P(-900, 0), 0, [("a-horse", 600)], side="left")["a-horse"])
    st.put("b-line", at=P(0, 1500), facing=180, width=1600, depth=40)
    st.pin("a-general", "a-centre")
    st.step("clash", "The lines meet", "c. 10:00", """…""")
    st.put("a-centre", facing_off(st.pl("b-line"), depth=30), move="attack", state="engaged")
    st.put("b-line", state="engaged")
    st.note(P(0, 1000), "Short note ≤70 chars", "clash")
    return st.doc(slug="battle-of-x", kind="battle", entity={"name": "Battle of X", "wikidata": "Q…"},
        title="Battle of X", date_label="2 August 216 BC", year=-216, intro="…", outcome="…",
        uncertainty="…", sources=[{"title": "Battle of X — Wikipedia", "url": "https://en.wikipedia.org/wiki/…", "kind": "web"}],
        sides=[{"id": "a", "name": "…", "color": "#b91c1c", "polity": {"name": "…", "wikidata": "Q…"},
                "commanders": [{"name": "…", "wikidata": "Q…", "role": "…"}], "strength": "c. …", "losses": "…"}, …],
        units=[{"id": "a-centre", "side": "a", "kind": "heavy_infantry", "label": "≤28 chars", "strength": "c. 9,000"}, …],
        terrain=[{"id": "river", "kind": "river", "label": "…", "line": RIVER}, …])'''

RULES = """\
- Coordinates [lon, lat]; bearings 0 = north, 90 = east; metres. Ids lowercase-kebab.
- Placements carry forward: a step lists only what changes. `at` = formation centre, `facing` = bearing its front faces.
- A move arrow starts where the unit stood and ends at its new `at` (Story.put(move=…) does this for you).
- Leave `camera` out unless a step needs a wider/tighter frame. 6–12 steps; 8–20 units.
- Frontage: close foot ≈ 1 m/file, depth ≈ 1 m/rank; cavalry 1–1.5 m/horse, 4–8 deep; Napoleonic battalion line ≈ 180×10 m.
- Original prose only; no markdown. Mark reconstructed positions `conjectural: true` (schema 2) and say so in `uncertainty`."""

NON_BATTLE = """\
Kinds war trade_route epidemic migration exploration expansion diffusion event (schema: 3); `sides` may be [], then units need no side.
Belongs to `entity` {name, wikidata} and/or `chronicle` {slug}; a chronicle's steps set `entry`: its sequence_order as stored (0-based).
Dates: step `date=when(1347, 10, end=(1348, 3))`; `time` stays the label; `period` defaults to the step range; `year` = the first year.
`ambient: true` (shown faintly on the plain atlas at its dates) needs a date on every step. legend=[{swatch, label, style: fill|line|dot}].
Features (= terrain): points city port market mine outbreak site | route (line, route_kind) | region (area, region_kind; `area` may be a
  list of rings). Optional: entity, side, goods [..], bidirectional, active, value_n, intensity, conjectural.
State: st.state("fid", active=False, state="disrupted", value_n=120, value_label="120 ships", intensity=.8, area=…, area_from_entity={"wikidata": "Q…"})
Step entities=[ent("Genoa", "Q1449", role="…", show=True)]: chips; show draws the entity's own atlas shape at the step's date.
Geometry: route(a, b, c, sea=True) keeps waypoints (name the straits); hull_region(places, buffer_km); buffer_ring(pt, km); merge_rings(…)."""


def _first_line(obj) -> str:  # noqa: ANN001
    doc = inspect.getdoc(obj) or ""
    first = doc.split("\n\n")[0].replace("\n", " ")
    sentence = re.split(r"(?<=[.!?])\s", first)[0]
    return sentence if len(sentence) <= 130 else sentence[: sentence.rfind(" ", 0, 127)] + " …"


def _sig(fn) -> str:  # noqa: ANN001
    """(a, b, n=8, **extra) — parameter names and defaults, no annotations."""
    parts = []
    for prm in inspect.signature(fn).parameters.values():
        if prm.name == "self":
            continue
        if prm.kind is prm.VAR_KEYWORD:
            parts.append(f"**{prm.name}")
        elif prm.kind is prm.VAR_POSITIONAL:
            parts.append(f"*{prm.name}")
        elif prm.default is not prm.empty:
            parts.append(f"{prm.name}={prm.default!r}")
        else:
            parts.append(prm.name)
    return f"({', '.join(parts)})"


def _functions(mod, skip: set[str]) -> list[str]:  # noqa: ANN001
    out = []
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_") or name in skip or fn.__module__ != mod.__name__:
            continue
        out.append(f"  {name}{_sig(fn)} — {_first_line(fn)}")
    return out


def _fmt(value) -> str:  # noqa: ANN001
    if isinstance(value, dict):
        if all(isinstance(v, str) for v in value.values()):  # e.g. TERRAIN_KINDS: kind -> geometry
            groups: dict[str, list[str]] = {}
            for k, g in value.items():
                groups.setdefault(g, []).append(k)
            return " | ".join(f"{g}: {' '.join(ks)}" for g, ks in groups.items())
        items = []
        for k, v in value.items():
            if isinstance(v, (tuple, list)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
                items.append(f"{k} {v[0]}–{v[1]}")
            elif isinstance(v, (tuple, list)):
                items.append(f"{k}: {' '.join(map(str, v))}")
            else:
                items.append(f"{k}={v}")
        return " | ".join(items)
    return " ".join(map(str, value))


#: Constants the sheet leaves out: superseded by FEATURE_* or shown another way.
HIDDEN = {"SCHEMA_VERSION", "TERRAIN_KINDS", "TERRAIN_STATES", "STATE_KINDS", "SPREAD_KM", "TELEPORT_M", "WATER_AREA_KINDS", "WATER_LINE_KINDS"}


def vocabulary() -> list[str]:
    """Every upper-case constant in schema.py (so new schema fields show up)."""
    out, scalars = [], []
    for name, value in vars(schema).items():
        if not name.isupper() or name in HIDDEN or (name[:3] in ("V2_", "V3_") and not name.endswith("_FIELDS")):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            scalars.append(f"{name} {value}")
        elif isinstance(value, (dict, tuple, list, set, frozenset)):
            label = {"V2_FIELDS": "SCHEMA-2 FIELDS (need schema: 2)", "V3_FIELDS": "SCHEMA-3 FIELDS (need schema: 3)"}.get(name, name)
            out.append(f"  {label}: {_fmt(value)}")
    out.append("  SCALE (spread km / teleport m): " + " | ".join(f"{k} {schema.SPREAD_KM[k]:,}/{schema.TELEPORT_M[k]:,}" for k in schema.SPREAD_KM))
    if scalars:
        out.append("  " + ", ".join(scalars))
    return [w for line in out for w in textwrap.wrap(line, 150, subsequent_indent="      ")]


def limits() -> str:
    src = (Path(schema.__file__).parent / "validate.py").read_text()
    found = re.findall(r'_text\(r, f?"([^"]+)", [^\n]*?, (\d+), (\d+)', src)
    parts = [f"{'step ' + n.rsplit('.', 1)[-1] if '{' in n else n} {lo}–{hi}" for n, lo, hi in found]
    label = re.search(r'len\(u\["label"\]\) > (\d+)', src)
    note = re.search(r'len\(note\["text"\]\) > (\d+)', src)
    extra = [f"unit label ≤{label.group(1)}" if label else "", f"note ≤{note.group(1)}" if note else ""]
    return "  chars: " + ", ".join(parts + [e for e in extra if e])


def render() -> str:
    lines = [f"MAP-STORY CHEATSHEET — schema {schema.SCHEMA_VERSION}. Read this instead of the toolkit modules.", ""]
    lines.append(f"COMMANDS  (prefix every one with: {CLI})")
    lines += ["  " + c for c in COMMANDS.splitlines()]
    lines += ["", "VOCABULARY (schema.py)"] + vocabulary()
    lines += [limits(), ""]
    lines.append("GEO  from pipeline.map_stories.geo import …   (pt = (lon, lat); prefer the `places` command to lookups)")
    lines += _functions(geo, {"nominatim", "place_geometry", "elevation", "profile", "r6", "r4", "path", "lines_of"})
    lines += ["", "LAYOUT  from pipeline.map_stories.layout import …   (specs: (unit_id, size[, {extra keys}]); left/right as the troops see it)"]
    lines += _functions(layout, {"default_depth"})
    lines += ["  Story() — records steps; st.<method>:"]
    lines += [f"    {n}{_sig(f)} — {_first_line(f)}" for n, f in inspect.getmembers(layout.Story, inspect.isfunction) if not n.startswith("_")]
    lines += ["", "BUILDER SKELETON  (pipeline/map_stories/stories/battle_of_x.py)"] + ["  " + s for s in SKELETON.splitlines()]
    lines += ["", "RULES"] + ["  " + r for r in RULES.splitlines()]
    lines += ["", "STORIES BEYOND BATTLES  (from pipeline.map_stories.layout import route, when, ent; geo: hull_region, merge_rings …)"]
    lines += ["  " + r for r in NON_BATTLE.splitlines()]
    return "\n".join(lines)
