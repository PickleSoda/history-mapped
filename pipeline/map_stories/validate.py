"""Check a map-story document: structure, references, and plausibility.

    python -m pipeline.map_stories check api/resources/map-stories/battle-of-cannae.json

Errors make the story unusable; warnings flag things that are probably wrong
(a unit teleporting kilometres with no move arrow, an arrow that doesn't end at
its unit, a battle spread over 40 km) and should be fixed or explained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pipeline.map_stories.geo import distance
from pipeline.map_stories.schema import (
    MOVE_TYPES,
    NOTE_KINDS,
    POINT_UNIT_KINDS,
    SCHEMA_VERSION,
    SHAPES,
    SOURCE_KINDS,
    STORY_KINDS,
    TERRAIN_KINDS,
    UNIT_KINDS,
    UNIT_STATES,
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,120}$")
QID_RE = re.compile(r"^Q[1-9][0-9]*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

#: How far (km) anything may sit from the story's centre before it is flagged.
SPREAD_KM = {"battle": 20, "naval_battle": 30, "siege": 15, "campaign": 3000}
#: A unit moving further than this between steps without a move arrow is flagged.
TELEPORT_M = {"battle": 900, "naval_battle": 1500, "siege": 600, "campaign": 150_000}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_point(p: Any) -> bool:
    return (
        isinstance(p, list)
        and len(p) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)
        and -180 <= p[0] <= 180
        and -90 <= p[1] <= 90
    )


def _text(r: Report, where: str, value: Any, lo: int, hi: int, required: bool = True) -> None:
    if value is None:
        if required:
            r.err(f"{where}: missing")
        return
    if not isinstance(value, str) or not value.strip():
        r.err(f"{where}: must be a non-empty string")
        return
    n = len(value.strip())
    if n < lo:
        r.warn(f"{where}: only {n} characters (aim for {lo}–{hi})")
    elif n > hi:
        r.warn(f"{where}: {n} characters (aim for {lo}–{hi})")


def resolve_steps(doc: dict) -> list[dict[str, dict]]:
    """Each step's full placement of every unit on the field: placements carry
    forward until changed, and `with` resolves to the escorted unit's point.
    Units not yet placed (or `hidden`) are absent."""
    current: dict[str, dict] = {}
    out: list[dict[str, dict]] = []
    for step in doc.get("steps", []):
        for uid, pl in (step.get("positions") or {}).items():
            merged = {**current.get(uid, {}), **pl}
            if "at" in pl and "with" not in pl:
                merged.pop("with", None)
            if "with" in pl and "at" not in pl:
                merged.pop("at", None)
            current[uid] = merged
        snapshot: dict[str, dict] = {}
        for uid, pl in current.items():
            if pl.get("state") == "hidden":
                continue
            snapshot[uid] = dict(pl)
        for uid, pl in snapshot.items():
            if "with" in pl and "at" not in pl:
                host = snapshot.get(pl["with"]) or current.get(pl["with"]) or {}
                if "at" in host:
                    pl["at"] = host["at"]
        out.append(snapshot)
    return out


def story_points(doc: dict) -> list[list[float]]:
    pts: list[list[float]] = []
    for t in doc.get("terrain", []):
        if _is_point(t.get("at")):
            pts.append(t["at"])
        for key in ("line", "area"):
            pts.extend(p for p in t.get(key) or [] if _is_point(p))
    for step in doc.get("steps", []):
        for pl in (step.get("positions") or {}).values():
            if _is_point(pl.get("at")):
                pts.append(pl["at"])
        for mv in step.get("moves") or []:
            pts.extend(p for p in mv.get("path") or [] if _is_point(p))
        for note in step.get("notes") or []:
            if _is_point(note.get("at")):
                pts.append(note["at"])
    return pts


def centre(doc: dict) -> list[float] | None:
    pts = story_points(doc)
    if not pts:
        return None
    lons, lats = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    return [lons[len(lons) // 2], lats[len(lats) // 2]]


def validate(doc: Any) -> Report:
    r = Report()
    if not isinstance(doc, dict):
        r.err("document must be an object")
        return r

    if doc.get("schema") != SCHEMA_VERSION:
        r.err(f"schema: must be {SCHEMA_VERSION}")
    if not isinstance(doc.get("slug"), str) or not SLUG_RE.match(doc["slug"]):
        r.err("slug: kebab-case, 3–120 characters")
    kind = doc.get("kind")
    if kind not in STORY_KINDS:
        r.err(f"kind: one of {', '.join(STORY_KINDS)}")
        kind = "battle"

    ent = doc.get("entity")
    if not isinstance(ent, dict) or not isinstance(ent.get("name"), str):
        r.err("entity: {name, wikidata?} of the battle entity")
    elif ent.get("wikidata") is not None and not QID_RE.match(str(ent["wikidata"])):
        r.err("entity.wikidata: a Q-id like Q179591")

    _text(r, "title", doc.get("title"), 3, 120)
    _text(r, "date_label", doc.get("date_label"), 3, 80)
    if not isinstance(doc.get("year"), int):
        r.err("year: integer, negative for BCE")
    _text(r, "intro", doc.get("intro"), 250, 1400)
    _text(r, "outcome", doc.get("outcome"), 20, 300)
    _text(r, "uncertainty", doc.get("uncertainty"), 40, 900, required=False)

    sources = doc.get("sources")
    if not isinstance(sources, list) or not sources:
        r.err("sources: at least one {title, url?, kind?}")
    else:
        for i, s in enumerate(sources):
            if not isinstance(s, dict) or not isinstance(s.get("title"), str):
                r.err(f"sources[{i}]: needs a title")
            elif s.get("kind") is not None and s["kind"] not in SOURCE_KINDS:
                r.err(f"sources[{i}].kind: one of {', '.join(SOURCE_KINDS)}")

    cam = doc.get("camera")
    if cam is not None and not (isinstance(cam, dict) and _is_point(cam.get("center")) and isinstance(cam.get("zoom"), (int, float))):
        r.err("camera: {center: [lon, lat], zoom, bearing?}")

    # sides
    side_ids: set[str] = set()
    for i, s in enumerate(doc.get("sides") or []):
        where = f"sides[{i}]"
        sid = s.get("id") if isinstance(s, dict) else None
        if not isinstance(sid, str) or not ID_RE.match(sid):
            r.err(f"{where}.id: lowercase id")
            continue
        if sid in side_ids:
            r.err(f"{where}.id: duplicate '{sid}'")
        side_ids.add(sid)
        if not isinstance(s.get("name"), str):
            r.err(f"{where}.name: missing")
        if not isinstance(s.get("color"), str) or not HEX_RE.match(s["color"]):
            r.err(f"{where}.color: #rrggbb")
        for j, c in enumerate(s.get("commanders") or []):
            if not isinstance(c, dict) or not isinstance(c.get("name"), str):
                r.err(f"{where}.commanders[{j}]: {{name, wikidata?, role?}}")
            elif c.get("wikidata") is not None and not QID_RE.match(str(c["wikidata"])):
                r.err(f"{where}.commanders[{j}].wikidata: Q-id")
        pol = s.get("polity")
        if pol is not None and not (isinstance(pol, dict) and isinstance(pol.get("name"), str)):
            r.err(f"{where}.polity: {{name, wikidata?}}")
    if len(side_ids) < 2 and kind != "campaign":
        r.err("sides: a battle needs at least two sides")

    # units
    units: dict[str, dict] = {}
    for i, u in enumerate(doc.get("units") or []):
        where = f"units[{i}]"
        uid = u.get("id") if isinstance(u, dict) else None
        if not isinstance(uid, str) or not ID_RE.match(uid):
            r.err(f"{where}.id: lowercase id")
            continue
        if uid in units:
            r.err(f"{where}.id: duplicate '{uid}'")
        units[uid] = u
        if u.get("side") not in side_ids:
            r.err(f"{where} ({uid}).side: unknown side '{u.get('side')}'")
        if u.get("kind") not in UNIT_KINDS:
            r.err(f"{where} ({uid}).kind: '{u.get('kind')}' is not one of {', '.join(UNIT_KINDS)}")
        if not isinstance(u.get("label"), str) or not u["label"].strip():
            r.err(f"{where} ({uid}).label: missing")
        elif len(u["label"]) > 48:
            r.warn(f"{where} ({uid}).label: {len(u['label'])} characters — keep map labels short")
        if u.get("wikidata") is not None and not QID_RE.match(str(u["wikidata"])):
            r.err(f"{where} ({uid}).wikidata: Q-id")
    if not units:
        r.err("units: none")

    # terrain
    terrain_ids: set[str] = set()
    for i, t in enumerate(doc.get("terrain") or []):
        where = f"terrain[{i}]"
        if not isinstance(t, dict):
            r.err(f"{where}: object")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not ID_RE.match(tid) or tid in terrain_ids:
            r.err(f"{where}.id: unique lowercase id")
        terrain_ids.add(str(tid))
        geom = TERRAIN_KINDS.get(t.get("kind"))
        if geom is None:
            r.err(f"{where} ({tid}).kind: '{t.get('kind')}' is not one of {', '.join(TERRAIN_KINDS)}")
            continue
        if geom == "at" and not _is_point(t.get("at")):
            r.err(f"{where} ({tid}): a {t['kind']} needs `at: [lon, lat]`")
        if geom == "line" and not (isinstance(t.get("line"), list) and len(t["line"]) >= 2 and all(_is_point(p) for p in t["line"])):
            r.err(f"{where} ({tid}): a {t['kind']} needs `line` with ≥2 points")
        if geom == "area" and not (isinstance(t.get("area"), list) and len(t["area"]) >= 3 and all(_is_point(p) for p in t["area"])):
            r.err(f"{where} ({tid}): a {t['kind']} needs `area` with ≥3 points")

    # steps
    steps = doc.get("steps") or []
    lo, hi = (3, 40) if kind == "campaign" else (5, 16)
    if not lo <= len(steps) <= hi:
        r.warn(f"steps: {len(steps)} (aim for {lo}–{hi})")
    step_ids: set[str] = set()
    placed: set[str] = set()
    for i, st in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(st, dict):
            r.err(f"{where}: object")
            continue
        sid = st.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid) or sid in step_ids:
            r.err(f"{where}.id: unique lowercase id")
        step_ids.add(str(sid))
        where = f"step '{sid}'"
        _text(r, f"{where}.title", st.get("title"), 3, 80)
        _text(r, f"{where}.narrative", st.get("narrative"), 150, 1100)
        if st.get("camera") is not None and not (isinstance(st["camera"], dict) and _is_point(st["camera"].get("center")) and isinstance(st["camera"].get("zoom"), (int, float))):
            r.err(f"{where}.camera: {{center, zoom, bearing?}}")

        for uid, pl in (st.get("positions") or {}).items():
            pw = f"{where}.positions.{uid}"
            if uid not in units:
                r.err(f"{pw}: unknown unit")
                continue
            if not isinstance(pl, dict):
                r.err(f"{pw}: object")
                continue
            if "at" in pl and not _is_point(pl["at"]):
                r.err(f"{pw}.at: [lon, lat]")
            if "with" in pl and pl["with"] not in units:
                r.err(f"{pw}.with: unknown unit '{pl['with']}'")
            if uid not in placed and "at" not in pl and "with" not in pl:
                r.err(f"{pw}: first placement needs `at` or `with`")
            placed.add(uid)
            if "facing" in pl and not (isinstance(pl["facing"], (int, float)) and -360 <= pl["facing"] <= 720):
                r.err(f"{pw}.facing: compass degrees")
            for dim, (dlo, dhi) in (("width", (5, 12000)), ("depth", (3, 6000))):
                if dim in pl and not (isinstance(pl[dim], (int, float)) and dlo <= pl[dim] <= dhi):
                    r.err(f"{pw}.{dim}: metres between {dlo} and {dhi}")
            if "shape" in pl and pl["shape"] not in SHAPES:
                r.err(f"{pw}.shape: one of {', '.join(SHAPES)}")
            if "state" in pl and pl["state"] not in UNIT_STATES:
                r.err(f"{pw}.state: one of {', '.join(UNIT_STATES)}")
            if units[uid].get("kind") not in POINT_UNIT_KINDS and uid not in _sized_before(steps, i, uid) and not ("width" in pl or "with" in pl):
                r.warn(f"{pw}: formation placed without `width` (defaults to 300 m)")

        for j, mv in enumerate(st.get("moves") or []):
            mw = f"{where}.moves[{j}]"
            if not isinstance(mv, dict):
                r.err(f"{mw}: object")
                continue
            if mv.get("unit") is not None and mv["unit"] not in units:
                r.err(f"{mw}.unit: unknown unit '{mv['unit']}'")
            if mv.get("unit") is None and mv.get("side") not in side_ids:
                r.err(f"{mw}: needs `unit` or `side`")
            if mv.get("type") not in MOVE_TYPES:
                r.err(f"{mw}.type: one of {', '.join(MOVE_TYPES)}")
            p = mv.get("path")
            if not (isinstance(p, list) and len(p) >= 2 and all(_is_point(q) for q in p)):
                r.err(f"{mw}.path: ≥2 [lon, lat] points")

        for j, note in enumerate(st.get("notes") or []):
            nw = f"{where}.notes[{j}]"
            if not isinstance(note, dict) or not _is_point(note.get("at")) or not isinstance(note.get("text"), str):
                r.err(f"{nw}: {{at, text, kind?}}")
            elif note.get("kind") is not None and note["kind"] not in NOTE_KINDS:
                r.err(f"{nw}.kind: one of {', '.join(NOTE_KINDS)}")
            elif len(note["text"]) > 70:
                r.warn(f"{nw}.text: {len(note['text'])} characters — keep map notes short")

        for uid in st.get("focus") or []:
            if uid not in units:
                r.err(f"{where}.focus: unknown unit '{uid}'")

    never = sorted(set(units) - placed)
    if never:
        r.warn(f"units never placed: {', '.join(never)}")

    if r.errors:
        return r

    _plausibility(doc, kind, r)
    return r


def _sized_before(steps: list, upto: int, uid: str) -> set[str]:
    for st in steps[:upto]:
        pl = (st.get("positions") or {}).get(uid)
        if isinstance(pl, dict) and "width" in pl:
            return {uid}
    return set()


def _plausibility(doc: dict, kind: str, r: Report) -> None:
    c = centre(doc)
    if c is None:
        return
    limit = SPREAD_KM[kind] * 1000
    far = [p for p in story_points(doc) if distance(p, c) > limit]
    if far:
        r.warn(f"{len(far)} point(s) lie more than {SPREAD_KM[kind]} km from the story's centre {c} (e.g. {far[0]})")

    resolved = resolve_steps(doc)
    steps = doc["steps"]
    for i in range(1, len(steps)):
        prev, cur = resolved[i - 1], resolved[i]
        moved_units = {mv.get("unit") for mv in steps[i].get("moves") or []}
        for uid, pl in cur.items():
            # A marker riding `with` a unit moves with it (and its arrow).
            if "with" in pl:
                continue
            if uid in prev and "at" in pl and "at" in prev[uid] and uid not in moved_units:
                d = distance(prev[uid]["at"], pl["at"])
                if d > TELEPORT_M[kind]:
                    r.warn(f"step '{steps[i]['id']}': {uid} moves {d:.0f} m with no move arrow")
    for i, st in enumerate(steps):
        for mv in st.get("moves") or []:
            uid = mv.get("unit")
            if uid and uid in resolved[i] and "at" in resolved[i][uid] and mv.get("type") != "fire":
                d = distance(mv["path"][-1], resolved[i][uid]["at"])
                slack = 20_000.0 if kind == "campaign" else max(250.0, float(resolved[i][uid].get("depth", 100)) * 2)
                if d > slack:
                    r.warn(f"step '{st['id']}': {uid}'s arrow ends {d:.0f} m from where the unit stands")
