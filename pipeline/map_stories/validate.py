"""Check a map-story document: structure, references, and plausibility.

    python -m pipeline.map_stories check api/resources/map-stories/battle-of-cannae.json

Errors make the story unusable; warnings flag things that are probably wrong
(a unit teleporting kilometres with no move arrow, an arrow that doesn't end at
its unit, a battle spread over 40 km, a warship on dry land, steps out of date
order) and should be fixed or explained.

Schema 3 renames `terrain` to `features` and a step's `terrain_state` to its
`features`; the old names stay accepted. `normalise` gives the new names, and
everything here works on a normalised copy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from pipeline.map_stories.geo import distance, distance_to_line, point_in_ring
from pipeline.map_stories.schema import (
    BATTLE_KINDS,
    FEATURE_KINDS,
    FEATURE_STATES,
    FORMATION_FIELDS,
    FORMATION_RANGES,
    LEGEND_STYLES,
    LIGHTS,
    MAX_BEATS,
    MILITARY_KINDS,
    MOVE_ORIENTS,
    MOVE_TYPES,
    NOTE_KINDS,
    POINT_UNIT_KINDS,
    REGION_KINDS,
    ROUTE_KINDS,
    SCHEMA_VERSIONS,
    SHAPES,
    SHIP_UNIT_KINDS,
    SHORE_M,
    SOURCE_KINDS,
    SPREAD_KM,
    STATE_KINDS,
    STORY_KINDS,
    TELEPORT_M,
    UNIT_KINDS,
    UNIT_STATES,
    V2_FIELDS,
    V2_MOVE_TYPES,
    V2_TERRAIN_KINDS,
    V2_UNIT_KINDS,
    V2_UNIT_STATES,
    V3_FEATURE_KINDS,
    V3_FEATURE_STATES,
    V3_FIELDS,
    V3_MOVE_TYPES,
    V3_STORY_KINDS,
    V3_UNIT_KINDS,
    WATER_AREA_KINDS,
    WATER_LINE_KINDS,
    WIND_STRENGTHS,
)

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,120}$")
QID_RE = re.compile(r"^Q[1-9][0-9]*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Move types whose path need not end where the unit stands.
UNANCHORED_MOVES = ("fire", "blockade")
#: The longest day of each month (a date check, so 29 February always passes).
MONTH_DAYS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


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


@dataclass
class _Ctx:
    """What the structural checks look ids up in, plus the running unit state."""

    r: Report
    v2: bool
    v3: bool = True
    side_ids: set[str] = field(default_factory=set)
    contingents: dict[str, set[str]] = field(default_factory=dict)
    units: dict[str, dict] = field(default_factory=dict)
    terrain: dict[str, dict] = field(default_factory=dict)
    placed: set[str] = field(default_factory=set)
    sized: set[str] = field(default_factory=set)
    #: Each placed unit's current state, to know who is on the field.
    states: dict[str, str] = field(default_factory=dict)

    def on_field(self) -> set[str]:
        return {uid for uid, state in self.states.items() if state != "hidden"}

    def needs_v2(self, where: str, obj: Any, group: str) -> None:
        """Error on the schema-2 fields a schema-1 document uses."""
        if self.v2 or not isinstance(obj, dict):
            return
        used = [f for f in V2_FIELDS[group] if f in obj]
        if used:
            self.r.err(f"{where}: {', '.join(used)} need schema 2 — set `schema: 2`")

    def v2_value(self, where: str, value: Any, added: tuple[str, ...]) -> None:
        if not self.v2 and value in added:
            self.r.err(f"{where}: '{value}' needs schema 2 — set `schema: 2`")

    def needs_v3(self, where: str, obj: Any, group: str) -> None:
        """Error on the schema-3 fields a schema-1 or -2 document uses."""
        if self.v3 or not isinstance(obj, dict):
            return
        used = [f for f in V3_FIELDS[group] if f in obj]
        if used:
            self.r.err(f"{where}: {', '.join(used)} need schema 3 — bump schema to 3")

    def v3_value(self, where: str, value: Any, added: tuple[str, ...]) -> None:
        if not self.v3 and value in added:
            self.r.err(f"{where}: '{value}' needs schema 3 — bump schema to 3")


def _is_point(p: Any) -> bool:
    return (
        isinstance(p, list)
        and len(p) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)
        and -180 <= p[0] <= 180
        and -90 <= p[1] <= 90
    )


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_count(v: Any, lo: int = 0, hi: int | None = None) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= lo and (hi is None or v <= hi)


def _is_text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _is_ring(a: Any) -> bool:
    return isinstance(a, list) and len(a) >= 3 and all(_is_point(p) for p in a)


def _is_line(a: Any) -> bool:
    return isinstance(a, list) and len(a) >= 2 and all(_is_point(p) for p in a)


def is_multi(area: Any) -> bool:
    """Whether an `area` is a list of rings (schema 3) rather than one ring."""
    return isinstance(area, list) and bool(area) and isinstance(area[0], list) and bool(area[0]) and isinstance(area[0][0], list)


def rings(area: Any) -> list[list[list[float]]]:
    """An `area` as a list of rings, whether it is one ring or several."""
    if not isinstance(area, list) or not area:
        return []
    return [r for r in area if isinstance(r, list)] if is_multi(area) else [area]


def _is_area(a: Any) -> bool:
    return _is_ring(a) or (is_multi(a) and all(_is_ring(r) for r in a))


# ── schema-3 names and dates ──────────────────────────────────────────────


def normalise(doc: Any) -> Any:
    """A shallow copy with the schema-3 names: `features` for `terrain`, and
    each step's `features` for its `terrain_state`. When both names are given
    the new one wins (`validate` reports the clash)."""
    if not isinstance(doc, dict):
        return doc
    out = dict(doc)
    if "terrain" in out:
        old = out.pop("terrain")
        out.setdefault("features", old)
    steps = out.get("steps")
    if isinstance(steps, list):
        fixed = []
        for st in steps:
            if isinstance(st, dict) and "terrain_state" in st:
                st = dict(st)
                old = st.pop("terrain_state")
                st.setdefault("features", old)
            fixed.append(st)
        out["steps"] = fixed
    return out


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def date_key(spec: Any, latest: bool = False) -> tuple[int, int, int] | None:
    """A date spec `{year, month?, day?}` as a sortable tuple: missing parts are
    the earliest (or, with `latest`, the last) month and day."""
    if not isinstance(spec, dict) or not _is_int(spec.get("year")):
        return None
    month = spec["month"] if _is_int(spec.get("month")) and 1 <= spec["month"] <= 12 else None
    day = spec["day"] if _is_int(spec.get("day")) else None
    if latest:
        m = month or 12
        return (spec["year"], m, day or MONTH_DAYS[m - 1])
    return (spec["year"], month or 1, day or 1)


def step_dates(doc: dict) -> list[dict | None]:
    """Each step's `date` (a step without one inherits the document's `year`)."""
    year = doc.get("year") if isinstance(doc, dict) else None
    out: list[dict | None] = []
    for st in doc.get("steps") or []:
        d = st.get("date") if isinstance(st, dict) else None
        out.append(d if isinstance(d, dict) else ({"year": year} if isinstance(year, int) else None))
    return out


def story_period(doc: dict) -> tuple[dict, dict] | None:
    """The document's `period` (start, end), or the range of its step dates."""
    per = doc.get("period")
    if isinstance(per, dict) and isinstance(per.get("start"), dict) and isinstance(per.get("end"), dict):
        return per["start"], per["end"]
    starts = [d for d in step_dates(doc) if date_key(d)]
    if not starts:
        return None
    ends = [d.get("end") if isinstance(d.get("end"), dict) else d for d in starts]
    first = min(starts, key=lambda d: date_key(d))
    last = max(ends, key=lambda d: date_key(d, latest=True) or (0, 0, 0))
    return {k: v for k, v in first.items() if k != "end"}, last


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


def _beats(step: dict) -> list[dict]:
    beats = step.get("beats")
    return [b for b in beats if isinstance(b, dict)] if isinstance(beats, list) else []


def _phases(step: dict) -> list[dict]:
    """The step itself, then each of its beats: each has its own positions,
    moves and notes, and resolves to one frame."""
    return [step, *_beats(step)]


# ── resolution ────────────────────────────────────────────────────────────


def _resolve(doc: dict) -> list[list[dict[str, dict]]]:
    """Every step's frames: after the step's own positions, then after each beat."""
    current: dict[str, dict] = {}
    out: list[list[dict[str, dict]]] = []
    for step in doc.get("steps", []):
        frames: list[dict[str, dict]] = []
        for phase in _phases(step):
            for uid, pl in (phase.get("positions") or {}).items():
                merged = {**current.get(uid, {}), **pl}
                if "at" in pl and "with" not in pl:
                    merged.pop("with", None)
                if "with" in pl and "at" not in pl:
                    merged.pop("at", None)
                current[uid] = merged
            frames.append(_snapshot(current))
            # `from` happens once; a unit merged `into` another leaves the field.
            for pl in current.values():
                pl.pop("from", None)
                if pl.pop("into", None) is not None:
                    pl["state"] = "hidden"
        out.append(frames)
    return out


def _snapshot(current: dict[str, dict]) -> dict[str, dict]:
    snapshot = {uid: dict(pl) for uid, pl in current.items() if pl.get("state") != "hidden"}
    for pl in snapshot.values():
        if "with" in pl and "at" not in pl:
            host = snapshot.get(pl["with"]) or current.get(pl["with"]) or {}
            if "at" in host:
                pl["at"] = host["at"]
    for pl in snapshot.values():
        target = snapshot.get(pl.get("into") or "")
        if target and "at" in target:
            pl["at"] = target["at"]
    return snapshot


def resolve_steps(doc: dict) -> list[dict[str, dict]]:
    """Each step's full placement of every unit on the field, after its last
    beat: placements carry forward until changed, `with` resolves to the
    escorted unit's point, and a unit merging `into` another stands on it.
    Units not yet placed (or `hidden`, or merged in an earlier frame) are absent."""
    return [frames[-1] for frames in _resolve(doc)]


def resolve_beats(doc: dict, i: int) -> list[dict[str, dict]]:
    """Step `i`'s frames: `[frame_before_beats, after_beat_1, …]`. The first is
    the step's own positions applied to the previous step; a step without
    beats has just that one frame."""
    return _resolve(doc)[i]


#: Feature-state keys that set the geometry: setting one clears the others.
GEOMETRY_KEYS = ("at", "line", "area", "area_from_entity")


def resolve_terrain_state(doc: dict) -> list[dict[str, dict]]:
    """Each step's feature state by feature id (`step.features`, alias
    `terrain_state`): {held_by?, state?, label?, active?, value_n?, …}, carried
    forward and overridden key by key; a `null` value clears that key. Giving
    a new `at`/`line`/`area`/`area_from_entity` replaces the earlier geometry."""
    current: dict[str, dict] = {}
    out: list[dict[str, dict]] = []
    for step in normalise(doc).get("steps", []):
        for tid, ts in (step.get("features") or {}).items():
            if not isinstance(ts, dict):
                continue
            base = current.get(tid, {})
            if any(k in ts for k in GEOMETRY_KEYS):
                base = {k: v for k, v in base.items() if k not in GEOMETRY_KEYS}
            merged = {**base, **ts}
            current[tid] = {k: v for k, v in merged.items() if v is not None}
        out.append({tid: dict(ts) for tid, ts in current.items() if ts})
    return out


def resolve_features(doc: dict) -> list[dict[str, dict]]:
    """Each step's features by id: the document's feature merged with its
    carried-forward state, with `active` (default true) always set. A state's
    geometry (`at`, `line`, `area`, `area_from_entity`) replaces the feature's."""
    d = normalise(doc)
    base = {f["id"]: f for f in d.get("features") or [] if isinstance(f, dict) and isinstance(f.get("id"), str)}
    out: list[dict[str, dict]] = []
    for states in resolve_terrain_state(d):
        frame: dict[str, dict] = {}
        for fid, feat in base.items():
            st = states.get(fid, {})
            merged = {k: v for k, v in feat.items() if not (k in GEOMETRY_KEYS and any(g in st for g in GEOMETRY_KEYS))}
            merged.update(st)
            merged.setdefault("active", True)
            frame[fid] = merged
        out.append(frame)
    return out


# ── points ────────────────────────────────────────────────────────────────


def _geometry_points(obj: dict) -> list[list[float]]:
    pts = [obj["at"]] if _is_point(obj.get("at")) else []
    pts.extend(p for p in obj.get("line") or [] if _is_point(p))
    for ring in rings(obj.get("area")):
        pts.extend(p for p in ring if _is_point(p))
    return pts


def story_points(doc: dict) -> list[list[float]]:
    """Every point the story draws that should sit near its centre: features
    (and their per-step geometry), placements, arrows and notes. Units placed
    with `frame: false` (and their arrows), `continues` tails and `alt_sites`
    are left out."""
    doc = normalise(doc)
    pts: list[list[float]] = []
    for t in doc.get("features") or []:
        if isinstance(t, dict):
            pts.extend(_geometry_points(t))
    for step in doc.get("steps", []):
        for ts in (step.get("features") or {}).values():
            if isinstance(ts, dict):
                pts.extend(_geometry_points(ts))
    frames = _resolve(doc)
    for i, step in enumerate(doc.get("steps", [])):
        for k, phase in enumerate(_phases(step)):
            frame = frames[i][k]
            offstage = {uid for uid, pl in frame.items() if pl.get("frame") is False}
            for uid, pl in (phase.get("positions") or {}).items():
                if uid not in offstage and _is_point(pl.get("at")):
                    pts.append(pl["at"])
            for mv in phase.get("moves") or []:
                if mv.get("unit") not in offstage:
                    pts.extend(p for p in mv.get("path") or [] if _is_point(p))
            for note in phase.get("notes") or []:
                if _is_point(note.get("at")):
                    pts.append(note["at"])
    return pts


def centre(doc: dict) -> list[float] | None:
    pts = story_points(doc)
    if not pts:
        return None
    lons, lats = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
    return [lons[len(lons) // 2], lats[len(lats) // 2]]


# ── structure ─────────────────────────────────────────────────────────────


def validate(doc: Any) -> Report:
    r = Report()
    if not isinstance(doc, dict):
        r.err("document must be an object")
        return r

    if doc.get("schema") not in SCHEMA_VERSIONS:
        r.err(f"schema: must be {', '.join(map(str, SCHEMA_VERSIONS[:-1]))} or {SCHEMA_VERSIONS[-1]}")
    # An unknown version is checked as the latest.
    ctx = _Ctx(r, v2=doc.get("schema") != 1, v3=doc.get("schema") not in (1, 2))
    ctx.needs_v2("document", doc, "document")
    ctx.needs_v3("document", doc, "document")
    if "features" in doc and "terrain" in doc:
        r.err("features and terrain: give one (terrain is the old name of features)")
    for i, st in enumerate(doc.get("steps") or []):
        if isinstance(st, dict):
            ctx.needs_v3(f"step '{st.get('id')}'", st, "step")
            if "features" in st and "terrain_state" in st:
                r.err(f"step '{st.get('id')}': features and terrain_state: give one (terrain_state is the old name)")
    raw = doc
    doc = normalise(doc)

    if not isinstance(doc.get("slug"), str) or not SLUG_RE.match(doc["slug"]):
        r.err("slug: kebab-case, 3–120 characters")
    kind = doc.get("kind")
    if kind not in STORY_KINDS:
        r.err(f"kind: one of {', '.join(STORY_KINDS)}")
        kind = "battle"
    ctx.v3_value("kind", kind, V3_STORY_KINDS)

    ent, chron = doc.get("entity"), doc.get("chronicle")
    if ent is None and chron is None:
        r.err("entity or chronicle: a story belongs to an entity {name, wikidata?} or a chronicle {slug}" if ctx.v3 else "entity: {name, wikidata?} of the battle entity")
    if ent is not None:
        if not isinstance(ent, dict) or not isinstance(ent.get("name"), str):
            r.err("entity: {name, wikidata?} of the story's entity")
        elif ent.get("wikidata") is not None and not QID_RE.match(str(ent["wikidata"])):
            r.err("entity.wikidata: a Q-id like Q179591")
    if chron is not None and not (isinstance(chron, dict) and isinstance(chron.get("slug"), str) and SLUG_RE.match(chron["slug"])):
        r.err("chronicle: {slug} of an existing chronicle")

    _text(r, "title", doc.get("title"), 3, 120)
    _text(r, "date_label", doc.get("date_label"), 3, 80)
    if not _is_int(doc.get("year")):
        r.err("year: integer, negative for BCE")
    _text(r, "intro", doc.get("intro"), 250, 1400)
    _text(r, "outcome", doc.get("outcome"), 20, 300)
    _text(r, "uncertainty", doc.get("uncertainty"), 40, 1500, required=False)

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

    alt = doc.get("alt_sites")
    if alt is not None and not isinstance(alt, list):
        r.err("alt_sites: a list of {at, label, note?}")
    for i, a in enumerate(alt if isinstance(alt, list) else []):
        if not (isinstance(a, dict) and _is_point(a.get("at")) and _is_text(a.get("label"))):
            r.err(f"alt_sites[{i}]: {{at, label, note?}}")
        elif a.get("note") is not None and not isinstance(a["note"], str):
            r.err(f"alt_sites[{i}].note: text")

    _period(ctx, doc)
    _legend(ctx, doc.get("legend"))

    _sides(ctx, doc.get("sides") or [])
    if len(ctx.side_ids) < 2 and kind in BATTLE_KINDS:
        r.err("sides: a battle needs at least two sides")
    _units(ctx, doc.get("units") or [], kind)
    feat_key = "terrain" if "terrain" in raw and "features" not in raw else "features"
    _features(ctx, doc.get("features") or [], feat_key)

    steps = doc.get("steps") or []
    lo, hi = (5, 16) if kind in BATTLE_KINDS else (3, 40)
    if not lo <= len(steps) <= hi:
        r.warn(f"steps: {len(steps)} (aim for {lo}–{hi})")
    step_ids: set[str] = set()
    entries: set[int] = set()
    raw_steps = raw.get("steps") or []
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            r.err(f"steps[{i}]: object")
            continue
        sid = st.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid) or sid in step_ids:
            r.err(f"steps[{i}].id: unique lowercase id")
        step_ids.add(str(sid))
        state_key = "terrain_state" if i < len(raw_steps) and isinstance(raw_steps[i], dict) and "terrain_state" in raw_steps[i] else "features"
        _step(ctx, f"step '{sid}'", st, state_key)
        _step_v3(ctx, f"step '{sid}'", st, doc, entries)

    never = sorted(set(ctx.units) - ctx.placed)
    if never:
        r.warn(f"units never placed: {', '.join(never)}")

    if r.errors:
        return r

    _dates(doc, r)
    _plausibility(doc, kind, r)
    return r


def _date(r: Report, where: str, value: Any, with_end: bool = True) -> bool:
    """A date spec {year, month?, day?} (and, on a step, an optional `end`)."""
    shape = "{year, month?, day?, end?}" if with_end else "{year, month?, day?}"
    if not isinstance(value, dict) or not _is_int(value.get("year")):
        r.err(f"{where}: {shape} with an integer year")
        return False
    ok = True
    month, day = value.get("month"), value.get("day")
    if month is not None and not (_is_int(month) and 1 <= month <= 12):
        r.err(f"{where}.month: 1–12")
        ok = False
    if day is not None:
        if month is None:
            r.err(f"{where}.day: needs a month")
            ok = False
        elif not (_is_int(day) and 1 <= day <= (MONTH_DAYS[month - 1] if ok else 31)):
            r.err(f"{where}.day: 1–{MONTH_DAYS[month - 1] if ok else 31}")
            ok = False
    if "end" in value:
        if not with_end:
            r.err(f"{where}.end: only a step date has an end")
            return False
        if not _date(r, f"{where}.end", value["end"], with_end=False):
            return False
        if ok and (date_key(value["end"], latest=True) or (0, 0, 0)) < (date_key(value) or (0, 0, 0)):
            r.err(f"{where}.end: before the start")
            ok = False
    return ok


def _period(ctx: _Ctx, doc: dict) -> None:
    r = ctx.r
    per = doc.get("period")
    if per is not None:
        if not (isinstance(per, dict) and "start" in per and "end" in per):
            r.err("period: {start: {year, …}, end: {year, …}}")
        elif _date(r, "period.start", per["start"], with_end=False) and _date(r, "period.end", per["end"], with_end=False):
            if (date_key(per["end"], latest=True) or (0, 0, 0)) < (date_key(per["start"]) or (0, 0, 0)):
                r.err("period.end: before the start")
    amb = doc.get("ambient")
    if amb is not None and not isinstance(amb, bool):
        r.err("ambient: true or false")


def _legend(ctx: _Ctx, legend: Any) -> None:
    r = ctx.r
    if legend is None:
        return
    if not isinstance(legend, list):
        r.err("legend: a list of {swatch, label, style?}")
        return
    for i, item in enumerate(legend):
        where = f"legend[{i}]"
        if not (isinstance(item, dict) and isinstance(item.get("swatch"), str) and HEX_RE.match(item["swatch"]) and _is_text(item.get("label"))):
            r.err(f"{where}: {{swatch: #rrggbb, label, style?}}")
        elif item.get("style") is not None and item["style"] not in LEGEND_STYLES:
            r.err(f"{where}.style: one of {', '.join(LEGEND_STYLES)}")


def _linked(r: Report, where: str, ref: Any, need_name: bool = True) -> None:
    """A linked entity reference {name, wikidata?, entity_id?}."""
    shape = "{name, wikidata?}" if need_name else "{wikidata} or {entity_id}"
    if not isinstance(ref, dict):
        r.err(f"{where}: {shape}")
        return
    if need_name and not _is_text(ref.get("name")):
        r.err(f"{where}.name: missing")
    if not need_name and not (ref.get("wikidata") or ref.get("entity_id")):
        r.err(f"{where}: {shape}")
    if ref.get("wikidata") is not None and not QID_RE.match(str(ref["wikidata"])):
        r.err(f"{where}.wikidata: a Q-id like Q42005")
    if ref.get("entity_id") is not None and not isinstance(ref["entity_id"], str):
        r.err(f"{where}.entity_id: text")


def _sides(ctx: _Ctx, sides: list) -> None:
    r = ctx.r
    for i, s in enumerate(sides):
        where = f"sides[{i}]"
        sid = s.get("id") if isinstance(s, dict) else None
        if not isinstance(sid, str) or not ID_RE.match(sid):
            r.err(f"{where}.id: lowercase id")
            continue
        if sid in ctx.side_ids:
            r.err(f"{where}.id: duplicate '{sid}'")
        ctx.side_ids.add(sid)
        ctx.needs_v2(where, s, "side")
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
        ids = ctx.contingents.setdefault(sid, set())
        cons = s.get("contingents")
        if cons is not None and not isinstance(cons, list):
            r.err(f"{where}.contingents: a list of {{id, name, color?}}")
        for j, c in enumerate(cons if isinstance(cons, list) else []):
            cw = f"{where}.contingents[{j}]"
            cid = c.get("id") if isinstance(c, dict) else None
            if not isinstance(cid, str) or not ID_RE.match(cid):
                r.err(f"{cw}.id: lowercase id")
                continue
            if cid in ids:
                r.err(f"{cw}.id: duplicate '{cid}'")
            ids.add(cid)
            if not _is_text(c.get("name")):
                r.err(f"{cw}.name: missing")
            if c.get("color") is not None and not (isinstance(c["color"], str) and HEX_RE.match(c["color"])):
                r.err(f"{cw}.color: #rrggbb")


def _units(ctx: _Ctx, units: list, story_kind: str = "battle") -> None:
    r = ctx.r
    for i, u in enumerate(units):
        where = f"units[{i}]"
        uid = u.get("id") if isinstance(u, dict) else None
        if not isinstance(uid, str) or not ID_RE.match(uid):
            r.err(f"{where}.id: lowercase id")
            continue
        if uid in ctx.units:
            r.err(f"{where}.id: duplicate '{uid}'")
        ctx.units[uid] = u
        uw = f"{where} ({uid})"
        ctx.needs_v2(uw, u, "unit")
        # Schema 3: a story without sides (an epidemic, a trade network) has side-less units.
        if u.get("side") not in ctx.side_ids and not (ctx.v3 and not ctx.side_ids and u.get("side") is None):
            r.err(f"{uw}.side: unknown side '{u.get('side')}'")
        kind = u.get("kind")
        if kind not in UNIT_KINDS:
            r.err(f"{uw}.kind: '{kind}' is not one of {', '.join(UNIT_KINDS)}")
        ctx.v2_value(f"{uw}.kind", kind, V2_UNIT_KINDS)
        ctx.v3_value(f"{uw}.kind", kind, V3_UNIT_KINDS)
        if not isinstance(u.get("label"), str) or not u["label"].strip():
            r.err(f"{uw}.label: missing")
        elif len(u["label"]) > 48:
            r.warn(f"{uw}.label: {len(u['label'])} characters — keep map labels short")
        if u.get("wikidata") is not None and not QID_RE.match(str(u["wikidata"])):
            r.err(f"{uw}.wikidata: Q-id")
        if "strength_n" in u and not _is_count(u["strength_n"]):
            r.err(f"{uw}.strength_n: a whole number ≥ 0")
        if "contingent" in u and u["contingent"] not in ctx.contingents.get(str(u.get("side")), set()):
            r.err(f"{uw}.contingent: '{u['contingent']}' is not a contingent of side '{u.get('side')}'")
        if "ranks" in u:
            _ranks(ctx, uw, u)
    if not ctx.units and story_kind in MILITARY_KINDS:
        r.err("units: none")


def _ranks(ctx: _Ctx, uw: str, u: dict) -> None:
    r, ranks = ctx.r, u["ranks"]
    if not isinstance(ranks, list) or not ranks:
        r.err(f"{uw}.ranks: a list of {{kind, share}} bands, front to back")
        return
    total, ok = 0.0, True
    for k, band in enumerate(ranks):
        if not (isinstance(band, dict) and band.get("kind") in UNIT_KINDS and _is_num(band.get("share")) and 0 <= band["share"] <= 1):
            r.err(f"{uw}.ranks[{k}]: {{kind: a unit kind, share: 0–1}}")
            ok = False
            continue
        total += band["share"]
        if band["kind"] in POINT_UNIT_KINDS:
            r.warn(f"{uw}.ranks[{k}]: '{band['kind']}' is a marker, not a formation band")
    if u.get("kind") in POINT_UNIT_KINDS:
        r.warn(f"{uw}.ranks: ignored on a {u['kind']} marker")
    if ok and abs(total - 1) > 0.05:
        r.warn(f"{uw}.ranks: shares sum to {total:.2f} (should be about 1)")


def _features(ctx: _Ctx, features: list, key: str = "features") -> None:
    """The document's persistent features (`features`, alias `terrain`)."""
    r = ctx.r
    if not isinstance(features, list):
        r.err(f"{key}: a list of features")
        return
    for i, t in enumerate(features):
        where = f"{key}[{i}]"
        if not isinstance(t, dict):
            r.err(f"{where}: object")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not ID_RE.match(tid) or tid in ctx.terrain:
            r.err(f"{where}.id: unique lowercase id")
        ctx.terrain[str(tid)] = t
        fw = f"{where} ({tid})"
        ctx.needs_v2(fw, t, "terrain")
        ctx.needs_v3(fw, t, "feature")
        for flag in ("conjectural", "bidirectional", "active"):
            if flag in t and not isinstance(t[flag], bool):
                r.err(f"{fw}.{flag}: true or false")
        kind = t.get("kind")
        geom = FEATURE_KINDS.get(kind)
        if geom is None:
            r.err(f"{fw}.kind: '{kind}' is not one of {', '.join(FEATURE_KINDS)}")
            continue
        ctx.v2_value(f"{fw}.kind", kind, V2_TERRAIN_KINDS)
        ctx.v3_value(f"{fw}.kind", kind, V3_FEATURE_KINDS)
        if geom == "at" and not _is_point(t.get("at")):
            r.err(f"{fw}: a {kind} needs `at: [lon, lat]`")
        if geom == "line" and not _is_line(t.get("line")):
            r.err(f"{fw}: a {kind} needs `line` with ≥2 points")
        if geom == "area":
            if not _is_area(t.get("area")):
                r.err(f"{fw}: a {kind} needs `area`: a ring of ≥3 points, or a list of such rings")
            elif is_multi(t["area"]) and not ctx.v3:
                r.err(f"{fw}.area: a list of rings needs schema 3 — bump schema to 3")
        _feature_extras(ctx, fw, t, kind)


def _feature_extras(ctx: _Ctx, fw: str, t: dict, kind: str) -> None:
    r = ctx.r
    for sub, values, owner in (("route_kind", ROUTE_KINDS, "route"), ("region_kind", REGION_KINDS, "region")):
        if kind == owner and t.get(sub) not in values:
            r.err(f"{fw}.{sub}: a {owner} needs one of {', '.join(values)}")
        elif kind != owner and sub in t:
            r.err(f"{fw}.{sub}: only a {owner} has one")
    if "entity" in t:
        _linked(r, f"{fw}.entity", t["entity"])
    if "side" in t and t["side"] not in ctx.side_ids:
        r.err(f"{fw}.side: unknown side '{t['side']}'")
    if "goods" in t and not (isinstance(t["goods"], list) and all(_is_text(g) for g in t["goods"])):
        r.err(f"{fw}.goods: a list of short names")
    _values(r, fw, t)


def _values(r: Report, where: str, obj: dict) -> None:
    """`value_n` (a number ≥ 0), `value_label` (text) and `intensity` (0–1)."""
    if "value_n" in obj and obj["value_n"] is not None and not (_is_num(obj["value_n"]) and obj["value_n"] >= 0):
        r.err(f"{where}.value_n: a number ≥ 0")
    if obj.get("value_label") is not None and not _is_text(obj["value_label"]):
        r.err(f"{where}.value_label: text")
    if "intensity" in obj and obj["intensity"] is not None and not (_is_num(obj["intensity"]) and 0 <= obj["intensity"] <= 1):
        r.err(f"{where}.intensity: a number 0–1")


def _step(ctx: _Ctx, where: str, st: dict, state_key: str = "features") -> None:
    r = ctx.r
    ctx.needs_v2(where, {("terrain_state" if k == "features" else k): v for k, v in st.items()}, "step")
    _text(r, f"{where}.title", st.get("title"), 3, 80)
    _text(r, f"{where}.narrative", st.get("narrative"), 150, 1100)
    if st.get("camera") is not None and not (isinstance(st["camera"], dict) and _is_point(st["camera"].get("center")) and isinstance(st["camera"].get("zoom"), (int, float))):
        r.err(f"{where}.camera: {{center, zoom, bearing?}}")
    if "light" in st and st["light"] not in LIGHTS:
        r.err(f"{where}.light: one of {', '.join(LIGHTS)}")
    for key in ("wind", "sun"):
        if key in st:
            _bearing_marker(ctx, f"{where}.{key}", st[key], key == "wind")
    if "features" in st:
        _feature_state(ctx, f"{where}.{state_key}", st["features"], "terrain" if state_key == "terrain_state" else "feature")

    _phase(ctx, where, st)
    beats = st.get("beats")
    if beats is None:
        return
    if not isinstance(beats, list):
        r.err(f"{where}.beats: a list of {{label, positions?, moves?, notes?}}")
        return
    if len(beats) > MAX_BEATS:
        r.err(f"{where}.beats: {len(beats)} beats (at most {MAX_BEATS})")
    for k, beat in enumerate(beats):
        bw = f"{where}.beats[{k}]"
        if not isinstance(beat, dict):
            r.err(f"{bw}: object")
            continue
        if not _is_text(beat.get("label")):
            r.err(f"{bw}.label: missing")
        elif len(beat["label"]) > 80:
            r.warn(f"{bw}.label: {len(beat['label'])} characters — keep captions short")
        if not beat.get("positions") and not beat.get("moves"):
            r.err(f"{bw}: needs `positions` or `moves`")
        _phase(ctx, bw, beat)


def _bearing_marker(ctx: _Ctx, where: str, value: Any, wind: bool) -> None:
    shape = "{from: degrees, strength?, label?}" if wind else "{from: degrees, label?}"
    if not (isinstance(value, dict) and _is_num(value.get("from")) and -360 <= value["from"] <= 720):
        ctx.r.err(f"{where}: {shape}")
        return
    if wind and value.get("strength") is not None and value["strength"] not in WIND_STRENGTHS:
        ctx.r.err(f"{where}.strength: one of {', '.join(WIND_STRENGTHS)}")
    if value.get("label") is not None and not isinstance(value["label"], str):
        ctx.r.err(f"{where}.label: text")


def _feature_state(ctx: _Ctx, where: str, value: Any, noun: str = "feature") -> None:
    """A step's feature state: feature id → {held_by?, state?, label?, active?,
    value_n?, value_label?, intensity?, at?/line?/area?/area_from_entity?}."""
    r = ctx.r
    if not isinstance(value, dict):
        r.err(f"{where}: object of {noun} id → {{held_by?, state?, label?, …}}")
        return
    for tid, ts in value.items():
        tw = f"{where}.{tid}"
        if tid not in ctx.terrain:
            r.err(f"{tw}: unknown {noun}")
            continue
        if not isinstance(ts, dict):
            r.err(f"{tw}: {{held_by?, state?, label?, …}}")
            continue
        ctx.needs_v3(tw, ts, "feature_state")
        if ts.get("held_by") is not None and ts["held_by"] not in ctx.side_ids:
            r.err(f"{tw}.held_by: unknown side '{ts['held_by']}'")
        if "state" in ts and ts["state"] is not None:
            if ts["state"] not in FEATURE_STATES:
                r.err(f"{tw}.state: one of {', '.join(FEATURE_STATES if ctx.v3 else FEATURE_STATES[:6])}")
            ctx.v3_value(f"{tw}.state", ts["state"], V3_FEATURE_STATES)
        if ts.get("label") is not None and not isinstance(ts["label"], str):
            r.err(f"{tw}.label: text")
        if "active" in ts and not isinstance(ts["active"], bool):
            r.err(f"{tw}.active: true or false")
        _values(r, tw, ts)
        geom = FEATURE_KINDS.get(ctx.terrain[tid].get("kind"))
        if "at" in ts and (geom != "at" or not _is_point(ts["at"])):
            r.err(f"{tw}.at: [lon, lat], on a point feature only")
        if "line" in ts and (geom != "line" or not _is_line(ts["line"])):
            r.err(f"{tw}.line: ≥2 points, on a line feature only")
        if "area" in ts and (geom != "area" or not _is_area(ts["area"])):
            r.err(f"{tw}.area: a ring or a list of rings, on an area feature only")
        if "area_from_entity" in ts:
            if geom != "area":
                r.err(f"{tw}.area_from_entity: on an area feature only")
            else:
                _linked(r, f"{tw}.area_from_entity", ts["area_from_entity"], need_name=False)
            if "area" in ts:
                r.err(f"{tw}: give `area` or `area_from_entity`, not both")
        if geom == "line" and ts.get("held_by") is not None:
            r.warn(f"{tw}: a line feature has no held state to draw — use a point or area")


def _step_v3(ctx: _Ctx, where: str, st: dict, doc: dict, entries: set[int]) -> None:
    """A step's date, chronicle entry and entities (schema 3)."""
    r = ctx.r
    if "date" in st:
        _date(r, f"{where}.date", st["date"])
    elif doc.get("ambient") is True:
        r.err(f"{where}.date: an ambient story dates every step")
    if "entry" in st:
        e = st["entry"]
        if doc.get("chronicle") is None:
            r.err(f"{where}.entry: only a chronicle's story keys steps to entries")
        elif not (_is_int(e) and e >= 0):
            r.err(f"{where}.entry: the entry's sequence_order as stored, an integer ≥ 0")
        elif e in entries:
            r.err(f"{where}.entry: entry {e} already has a step")
        else:
            entries.add(e)
    ents = st.get("entities")
    if ents is None:
        return
    if not isinstance(ents, list):
        r.err(f"{where}.entities: a list of {{name, wikidata?, role?, show?}}")
        return
    for j, e in enumerate(ents):
        ew = f"{where}.entities[{j}]"
        _linked(r, ew, e)
        if isinstance(e, dict):
            if e.get("role") is not None and not _is_text(e["role"]):
                r.err(f"{ew}.role: text")
            if "show" in e and not isinstance(e["show"], bool):
                r.err(f"{ew}.show: true or false")


def _phase(ctx: _Ctx, where: str, phase: dict) -> None:
    """A step's (or beat's) positions, moves and notes, in order."""
    r = ctx.r
    positions = phase.get("positions") or {}
    if not isinstance(positions, dict):
        r.err(f"{where}.positions: object of unit id → placement")
        positions = {}
    before = ctx.on_field()
    merging: dict[str, Any] = {}
    for uid, pl in positions.items():
        pw = f"{where}.positions.{uid}"
        if uid not in ctx.units:
            r.err(f"{pw}: unknown unit")
            continue
        if not isinstance(pl, dict):
            r.err(f"{pw}: object")
            continue
        _placement(ctx, pw, uid, pl, before)
        if "into" in pl:
            merging[uid] = pl["into"]
    now = ctx.on_field()
    for uid, target in merging.items():
        if target in ctx.units and target not in now:
            r.err(f"{where}.positions.{uid}.into: '{target}' is not on the field in this step")
        # It slides onto the target, then leaves the field.
        ctx.states[uid] = "hidden"

    for j, mv in enumerate(phase.get("moves") or []):
        _move(ctx, f"{where}.moves[{j}]", mv)
    for j, note in enumerate(phase.get("notes") or []):
        _note(ctx, f"{where}.notes[{j}]", note)
    for uid in phase.get("focus") or []:
        if uid not in ctx.units:
            r.err(f"{where}.focus: unknown unit '{uid}'")


def _placement(ctx: _Ctx, pw: str, uid: str, pl: dict, before: set[str]) -> None:
    r, kind = ctx.r, ctx.units[uid].get("kind")
    ctx.needs_v2(pw, pl, "placement")
    if "at" in pl and not _is_point(pl["at"]):
        r.err(f"{pw}.at: [lon, lat]")
    if "with" in pl and pl["with"] not in ctx.units:
        r.err(f"{pw}.with: unknown unit '{pl['with']}'")
    if uid not in ctx.placed and "at" not in pl and "with" not in pl:
        r.err(f"{pw}: first placement needs `at` or `with`")
    ctx.placed.add(uid)
    if "facing" in pl and not (isinstance(pl["facing"], (int, float)) and -360 <= pl["facing"] <= 720):
        r.err(f"{pw}.facing: compass degrees")
    for dim, (dlo, dhi) in (("width", (5, 12000)), ("depth", (3, 6000))):
        if dim in pl and not (isinstance(pl[dim], (int, float)) and dlo <= pl[dim] <= dhi):
            r.err(f"{pw}.{dim}: metres between {dlo} and {dhi}")
    if "shape" in pl and pl["shape"] not in SHAPES:
        r.err(f"{pw}.shape: one of {', '.join(SHAPES)}")
    if "state" in pl:
        if pl["state"] not in UNIT_STATES:
            r.err(f"{pw}.state: one of {', '.join(UNIT_STATES)}")
        ctx.v2_value(f"{pw}.state", pl["state"], V2_UNIT_STATES)
        fits = STATE_KINDS.get(pl["state"])
        if fits and kind not in fits:
            r.warn(f"{pw}.state: '{pl['state']}' is for {', '.join(fits)}, not {kind}")
        if pl["state"] == "captured" and "by" not in pl:
            r.err(f"{pw}.state: 'captured' needs `by: <side id>` (the captor)")
    if "by" in pl and pl["by"] not in ctx.side_ids:
        r.err(f"{pw}.by: unknown side '{pl['by']}'")
    for key in ("frame", "conjectural"):
        if key in pl and not isinstance(pl[key], bool):
            r.err(f"{pw}.{key}: true or false")
    if "strength_n" in pl and not _is_count(pl["strength_n"]):
        r.err(f"{pw}.strength_n: a whole number ≥ 0")
    for key in FORMATION_FIELDS:
        if key not in pl:
            continue
        flo, fhi = FORMATION_RANGES[key]
        if not _is_count(pl[key], flo, fhi):
            r.err(f"{pw}.{key}: a whole number {flo}–{fhi}")
        elif kind in POINT_UNIT_KINDS:
            r.warn(f"{pw}.{key}: ignored on a {kind} marker")
    if "from" in pl:
        if pl["from"] not in ctx.units or pl["from"] == uid:
            r.err(f"{pw}.from: unknown unit '{pl['from']}'")
        elif uid in before:
            r.err(f"{pw}.from: {uid} is already on the field — `from` goes on its first placement")
        elif pl["from"] not in before:
            r.err(f"{pw}.from: '{pl['from']}' was not on the field in the previous step")
    if "into" in pl and (pl["into"] not in ctx.units or pl["into"] == uid):
        r.err(f"{pw}.into: unknown unit '{pl['into']}'")
    if kind not in POINT_UNIT_KINDS and uid not in ctx.sized and not ("width" in pl or "with" in pl):
        r.warn(f"{pw}: formation placed without `width` (defaults to 300 m)")
    if "width" in pl:
        ctx.sized.add(uid)
    if "state" in pl:
        ctx.states[uid] = str(pl["state"])
    else:
        ctx.states.setdefault(uid, "ready")


def _move(ctx: _Ctx, mw: str, mv: Any) -> None:
    r = ctx.r
    if not isinstance(mv, dict):
        r.err(f"{mw}: object")
        return
    ctx.needs_v2(mw, mv, "move")
    if mv.get("unit") is not None and mv["unit"] not in ctx.units:
        r.err(f"{mw}.unit: unknown unit '{mv['unit']}'")
    if mv.get("unit") is None and mv.get("side") not in ctx.side_ids:
        r.err(f"{mw}: needs `unit` or `side`")
    if mv.get("type") not in MOVE_TYPES:
        r.err(f"{mw}.type: one of {', '.join(MOVE_TYPES)}")
    ctx.v2_value(f"{mw}.type", mv.get("type"), V2_MOVE_TYPES)
    ctx.v3_value(f"{mw}.type", mv.get("type"), V3_MOVE_TYPES)
    p = mv.get("path")
    if not (isinstance(p, list) and len(p) >= 2 and all(_is_point(q) for q in p)):
        r.err(f"{mw}.path: ≥2 [lon, lat] points")
    cont = mv.get("continues")
    if cont is not None and not (isinstance(cont, dict) and _is_point(cont.get("toward")) and (cont.get("label") is None or isinstance(cont["label"], str))):
        r.err(f"{mw}.continues: {{toward: [lon, lat], label?}}")
    if "orient" in mv and mv["orient"] not in MOVE_ORIENTS:
        r.err(f"{mw}.orient: one of {', '.join(MOVE_ORIENTS)}")
    if "target" in mv:
        if mv["target"] not in ctx.units:
            r.err(f"{mw}.target: unknown unit '{mv['target']}'")
        elif mv.get("type") != "fire":
            r.warn(f"{mw}.target: only `fire` moves end on a target")
    for key in ("arc", "conjectural"):
        if key in mv and not isinstance(mv[key], bool):
            r.err(f"{mw}.{key}: true or false")
    if mv.get("arc") and mv.get("type") != "fire":
        r.warn(f"{mw}.arc: only `fire` moves are drawn as an arc")


def _note(ctx: _Ctx, nw: str, note: Any) -> None:
    r = ctx.r
    if not isinstance(note, dict) or not _is_point(note.get("at")) or not isinstance(note.get("text"), str):
        r.err(f"{nw}: {{at, text, kind?}}")
        return
    ctx.needs_v2(nw, note, "note")
    if note.get("kind") is not None and note["kind"] not in NOTE_KINDS:
        r.err(f"{nw}.kind: one of {', '.join(NOTE_KINDS)}")
    elif len(note["text"]) > 70:
        r.warn(f"{nw}.text: {len(note['text'])} characters — keep map notes short")
    if "conjectural" in note and not isinstance(note["conjectural"], bool):
        r.err(f"{nw}.conjectural: true or false")


# ── plausibility (warnings) ───────────────────────────────────────────────


def _transitions(doc: dict) -> Iterator[tuple[str, dict, dict | None, dict[str, dict]]]:
    """(where, phase, previous frame, frame) for every step and beat, in order."""
    frames = _resolve(doc)
    prev: dict[str, dict] | None = None
    for i, st in enumerate(doc["steps"]):
        for k, phase in enumerate(_phases(st)):
            where = f"step '{st['id']}'" + (f" beat {k}" if k else "")
            yield where, phase, prev, frames[i][k]
            prev = frames[i][k]


def _dates(doc: dict, r: Report) -> None:
    """Steps in date order, inside the period, and `year` = the first year."""
    prev: tuple[int, int, int] | None = None
    dated = False
    for st in doc["steps"]:
        d = st.get("date")
        if not isinstance(d, dict):
            continue
        dated = True
        key = date_key(d)
        if prev is not None and key is not None and key < prev:
            r.warn(f"step '{st['id']}': dated before the previous step")
        prev = key or prev
    per = story_period(doc) if (dated or doc.get("period")) else None
    if per is None:
        return
    start, end = date_key(per[0]), date_key(per[1], latest=True)
    if isinstance(doc.get("period"), dict):
        for st in doc["steps"]:
            d = st.get("date")
            if isinstance(d, dict) and start and end:
                lo, hi = date_key(d), date_key(d.get("end") if isinstance(d.get("end"), dict) else d, latest=True)
                if lo and hi and (lo < start or hi > end):
                    r.warn(f"step '{st['id']}': date lies outside the period")
    if start and doc["year"] != start[0]:
        r.warn(f"year: {doc['year']}, but the story starts in {start[0]} (year is the first year)")


def _plausibility(doc: dict, kind: str, r: Report) -> None:
    c = centre(doc)
    if c is None:
        return
    limit = SPREAD_KM[kind] * 1000
    far = [p for p in story_points(doc) if distance(p, c) > limit]
    if far:
        r.warn(f"{len(far)} point(s) lie more than {SPREAD_KM[kind]} km from the story's centre {c} (e.g. {far[0]})")

    for where, phase, prev, cur in _transitions(doc):
        moves = phase.get("moves") or []
        if prev is not None:
            moved_units = {mv.get("unit") for mv in moves}
            for uid, pl in cur.items():
                # A marker riding `with` a unit moves with it (and its arrow);
                # a unit merging `into` another slides onto it.
                if "with" in pl or "into" in pl or "at" not in pl or uid in moved_units:
                    continue
                start = (prev.get(uid) or prev.get(pl.get("from") or "") or {}).get("at")
                if start is not None:
                    d = distance(start, pl["at"])
                    if d > TELEPORT_M[kind]:
                        r.warn(f"{where}: {uid} moves {d:.0f} m with no move arrow")
        for mv in moves:
            uid = mv.get("unit")
            if uid and uid in cur and "at" in cur[uid] and mv.get("type") not in UNANCHORED_MOVES:
                d = distance(mv["path"][-1], cur[uid]["at"])
                slack = max(250.0, float(cur[uid].get("depth", 100)) * 2) if kind in BATTLE_KINDS else TELEPORT_M[kind] / 7.5
                if d > slack:
                    r.warn(f"{where}: {uid}'s arrow ends {d:.0f} m from where the unit stands")
            if mv.get("target") and mv["target"] not in cur:
                r.warn(f"{where}: {uid or mv.get('side')}'s fire target '{mv['target']}' is not on the field")

    _land_and_water(doc, r)


def _land_and_water(doc: dict, r: Report) -> None:
    """Ships on water, troops on land — when the story draws any water."""
    terrain = normalise(doc).get("features") or []
    seas = [ring for t in terrain if t["kind"] in WATER_AREA_KINDS for ring in rings(t["area"])]
    shores = [t["line"] for t in terrain if t["kind"] in WATER_LINE_KINDS]
    if not seas and not shores:
        return
    islands = [ring for t in terrain if t["kind"] == "island" for ring in rings(t["area"])]

    def afloat(p: list[float]) -> bool:
        return any(point_in_ring(p, a) for a in seas) and not any(point_in_ring(p, a) for a in islands)

    units = {u["id"]: u for u in doc.get("units") or []}
    flagged: set[str] = set()
    for where, phase, _prev, cur in _transitions(doc):
        landing = {mv.get("unit") for mv in phase.get("moves") or [] if mv.get("type") == "landing"}
        for uid, pl in cur.items():
            if uid in flagged or "with" in pl or "into" in pl or not _is_point(pl.get("at")):
                continue
            ukind, p = units[uid]["kind"], pl["at"]
            if ukind in SHIP_UNIT_KINDS:
                if not afloat(p) and not any(distance_to_line(p, line) <= SHORE_M for line in shores):
                    r.warn(f"{where}: {uid} ({ukind}) is not on water — outside every sea/lake and over {SHORE_M} m from a river or coast")
                    flagged.add(uid)
            elif uid not in landing and afloat(p):
                r.warn(f"{where}: {uid} ({ukind}) stands in the sea or a lake")
                flagged.add(uid)
