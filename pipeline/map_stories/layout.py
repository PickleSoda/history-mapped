"""Placement helpers and a step recorder for map-story builders.

    from pipeline.map_stories.layout import Story, local_frame, deploy_line, behind, ...

Every helper returns plain placement dicts (`at`, `facing`, `width`, `depth`,
`shape`, `curve`) — schema-1 fields only — so they work with any schema.
"Left" and "right" are as the troops see them, facing the enemy. `specs` are
`(unit_id, size)` or `(unit_id, size, {extra placement keys})` tuples.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import math

from pipeline.map_stories.geo import along, bearing, distance, great_circle, length, mid, offset, r4, r6, rel
from pipeline.map_stories.schema import SCHEMA_VERSION

Point = Sequence[float]
Spec = tuple


def local_frame(origin: Point):
    """`P = local_frame(anchor)`; then `P(east, north)` is a point in metres from it."""

    def P(east: float, north: float) -> list[float]:
        return offset(origin, east=east, north=north)

    return P


def facing_toward(a: Point | dict, b: Point | dict) -> int:
    """Compass bearing from a to b (points or placements), rounded."""
    pa = a["at"] if isinstance(a, dict) else a
    pb = b["at"] if isinstance(b, dict) else b
    return round(bearing(pa, pb)) % 360


def default_depth(width: float) -> float:
    """The depth the atlas draws when a placement gives none."""
    return max(20.0, min(width / 4, 120.0))


def _depth(pl: dict) -> float:
    return float(pl.get("depth") or default_depth(float(pl.get("width", 300))))


def _spec(spec: Spec | str, default: float = 0.0) -> tuple[str, float, dict]:
    if isinstance(spec, str):
        return spec, default, {}
    uid, size, *rest = spec
    return uid, float(size), dict(rest[0]) if rest else {}


def front(left: Point, right: Point, depth: float = 20, **extra) -> dict:
    """One formation whose front edge runs from `left` to `right`."""
    facing = (bearing(left, right) - 90) % 360
    return {"at": rel(mid(left, right), facing, ahead=-depth / 2), "facing": round(facing) % 360, "width": round(distance(left, right)), "depth": depth, **extra}


def deploy_line(left: Point, right: Point, specs: Iterable[Spec], depth: float = 20, gap: float = 0) -> dict[str, dict]:
    """Units side by side along a front from `left` to `right`, each taking a
    share of the width proportional to its size (use strengths or frontages)."""
    rows = [_spec(s, 1.0) for s in specs]
    total = sum(r[1] for r in rows) or 1.0
    span = distance(left, right) - gap * (len(rows) - 1)
    out, t = {}, 0.0
    for uid, share, extra in rows:
        w = span * share / total
        a = along([left, right], t / distance(left, right))
        b = along([left, right], (t + w) / distance(left, right))
        out[uid] = front(a, b, extra.pop("depth", depth), **extra)
        t += w + gap
    return out


def wing(anchor: Point, facing: float, specs: Iterable[Spec], side: str = "left", depth: float = 40, gap: float = 20) -> dict[str, dict]:
    """Units (specs give widths) side by side outward from `anchor` (the inner
    end of the wing's front) toward `side`, all facing `facing`."""
    sign = -1 if side == "left" else 1
    out, t = {}, 0.0
    for uid, width, extra in (_spec(s, 300) for s in specs):
        d = extra.pop("depth", depth)
        out[uid] = {"at": rel(anchor, facing, ahead=-d / 2, right=sign * (t + width / 2)), "facing": round(facing) % 360, "width": round(width), "depth": d, **extra}
        t += width + gap
    return out


def echelon(start: Point, facing: float, specs: Iterable[Spec], back: float = 120, side: str = "right", depth: float = 30, gap: float = 20) -> dict[str, dict]:
    """Units (specs give widths) stepped back by `back` metres each, extending
    toward `side` from `start` (the first unit's front centre): oblique order."""
    sign = 1 if side == "right" else -1
    out, offset_side, prev_w = {}, 0.0, None
    for i, (uid, width, extra) in enumerate(_spec(s, 300) for s in specs):
        d = extra.pop("depth", depth)
        if prev_w is not None:
            offset_side += prev_w / 2 + gap + width / 2
        out[uid] = {"at": rel(start, facing, ahead=-(i * back) - d / 2, right=sign * offset_side), "facing": round(facing) % 360, "width": round(width), "depth": d, **extra}
        prev_w = width
    return out


def crescent(centre: Point, facing: float, width: float, bulge: float, depth: float = 40, **extra) -> dict:
    """A crescent whose middle bows `bulge` metres toward the enemy (negative: back)."""
    return {"at": r6(centre), "facing": round(facing) % 360, "width": round(width), "depth": depth, "shape": "crescent", "curve": round(bulge), **extra}


def column(path: Sequence[Point], units: Iterable[Spec | str], spacing: float = 15, width: float = 20) -> dict[str, dict]:
    """A marching column along `path` (in the direction of march): the first
    unit's head is at the path's end, the rest follow. Specs give lengths."""
    rev = [list(p) for p in reversed(path)]
    total = length(rev) or 1.0
    out, d = {}, 0.0
    for uid, ln, extra in (_spec(s, 100) for s in units):
        centre = along(rev, min(1.0, (d + ln / 2) / total))
        ahead = along(rev, max(0.0, (d + ln / 2 - 30) / total))
        head = bearing(centre, ahead) if distance(centre, ahead) > 1 else bearing(rev[1], rev[0])
        out[uid] = {"at": centre, "facing": round(head) % 360, "width": width, "depth": round(ln), "shape": "column", **extra}
        d += ln + spacing
    return out


def behind(pl: dict, gap: float, **over) -> dict:
    """A formation `gap` metres behind `pl`'s rear edge, same facing and width
    (override any key: depth=, width=, shape=…)."""
    d = float(over.get("depth", _depth(pl)))
    at = rel(pl["at"], pl.get("facing", 0), ahead=-(_depth(pl) / 2 + gap + d / 2))
    return {**{k: pl[k] for k in ("facing", "width", "depth") if k in pl}, **over, "at": at}


def screen(pl: dict, gap: float = 40, depth: float = 8, **over) -> dict:
    """A thin skirmish line `gap` metres in front of `pl`, same facing and width."""
    at = rel(pl["at"], pl.get("facing", 0), ahead=_depth(pl) / 2 + gap + depth / 2)
    return {"facing": pl.get("facing", 0), "width": pl.get("width", 300), "shape": "line", **over, "depth": depth, "at": at}


def facing_off(target: dict, depth: float, gap: float = 4, width: float | None = None, slide: float = 0, **over) -> dict:
    """A formation `gap` metres in front of `target`, facing it (in contact when
    gap is small). `slide` shifts it along the front, to the target's right."""
    at = rel(target["at"], target.get("facing", 0), ahead=_depth(target) / 2 + gap + depth / 2, right=slide)
    out = {"at": at, "facing": round((target.get("facing", 0) + 180) % 360) % 360, "depth": depth, **over}
    if width:
        out["width"] = round(width)
    return out


# ── schema 3: routes, dates, linked entities ──────────────────────────────


def route(*waypoints: Point, sea: bool = False, step_km: float | None = None) -> list[list[float]]:
    """A route line through `waypoints`, kept exactly as given (no land or sea
    avoidance: name the capes, straits and passes yourself), each leg densified
    along the great circle into pieces of at most `step_km` (default 100 km at
    sea, 40 km on land) so long legs bow like real courses."""
    if len(waypoints) < 2:
        raise ValueError("route needs at least two waypoints")
    step = (step_km or (100.0 if sea else 40.0)) * 1000
    out: list[list[float]] = [r4(waypoints[0])]
    for a, b in zip(waypoints, waypoints[1:]):
        n = max(1, math.ceil(distance(a, b) / step))
        out.extend(great_circle(a, b, n)[1:])
    return out


def when(year: int, month: int | None = None, day: int | None = None, end: tuple | dict | None = None) -> dict:
    """A step date: `when(1347, 10)`, `when(1348, 1, end=(1348, 6))` → {year, month?, day?, end?}."""
    d: dict = {"year": year}
    if month is not None:
        d["month"] = month
    if day is not None:
        d["day"] = day
    if end is not None:
        d["end"] = end if isinstance(end, dict) else when(*end)
    return d


def ent(name: str, wikidata: str | None = None, role: str | None = None, show: bool | None = None) -> dict:
    """A linked entity for `step.entities` (or a feature's `entity`): {name, wikidata?, role?, show?}."""
    out: dict = {"name": name}
    if wikidata:
        out["wikidata"] = wikidata
    if role:
        out["role"] = role
    if show is not None:
        out["show"] = show
    return out


# ── the step recorder ─────────────────────────────────────────────────────


class Story:
    """Records steps while tracking every unit's current placement, so a move
    arrow always starts where its unit last stood and ends where it now stands.

        st = Story()
        st.step("deployment", "The armies deploy", "Dawn", '''narrative…''')
        st.place(deploy_line(P(-900, 0), P(900, 0), [("left", 3), ("centre", 5)], depth=30))
        st.put("cav", move="charge", via=[P(-1200, 400)], at=P(-600, 900), state="engaged")
        st.pin("hannibal", "centre"); st.note(P(0, 950), "Paullus is killed", "death")
        doc = st.doc(slug=…, kind="battle", …)   # adds schema and steps
    """

    def __init__(self) -> None:
        self.cur: dict[str, dict] = {}
        self.steps: list[dict] = []

    # steps
    def step(self, sid: str, title: str, time: str | None, narrative: str, **extra) -> dict:
        """Start a step (narrative whitespace is collapsed; extra: camera=, light=, …)."""
        st = {"id": sid, "title": title, **({"time": time} if time else {}), "narrative": " ".join(narrative.split()), "positions": {}, "moves": [], "notes": [], **extra}
        self.steps.append(st)
        return st

    @property
    def s(self) -> dict:
        """The current step dict."""
        return self.steps[-1]

    # reading state
    def pl(self, uid: str) -> dict:
        """The unit's current full placement (`at` resolved for pinned markers)."""
        p = dict(self.cur[uid])
        if "with" in p:
            p["at"] = self.at(p["with"])
        return p

    def at(self, uid: str) -> list[float]:
        """The unit's current point (a pinned marker's host point)."""
        p = self.cur[uid]
        return self.at(p["with"]) if "with" in p and "at" not in p else p["at"]

    # writing
    def put(self, uid: str, placement: dict | None = None, move: str | None = None, via: Iterable[Point] = (), mlabel: str | None = None, start: Point | None = None, **pl) -> None:
        """Place a unit: only keys that differ from its current placement are
        written. With `move`, draw its arrow from where it stood (or `start`,
        for a unit entering the field) through `via` to its new `at`."""
        new = {**(placement or {}), **pl}
        if move and "at" not in new:
            raise ValueError(f"{uid}: a move needs the new `at`")
        prev = list(start) if start is not None else (self.at(uid) if uid in self.cur else None)
        if move and prev is None:
            raise ValueError(f"{uid}: first placement with a move needs `start=`")
        old = self.cur.get(uid)
        written = dict(new) if old is None else {k: v for k, v in new.items() if old.get(k) != v}
        if "at" in new and old is not None and "with" in old:
            written["at"] = new["at"]
        if written:
            self.s["positions"].setdefault(uid, {}).update(written)
        state = self.cur.setdefault(uid, {})
        if "at" in new:
            state.pop("with", None)
        state.update(new)
        if move:
            mv = {"unit": uid, "type": move, "path": [r6(prev), *[r6(v) for v in via], r6(new["at"])]}
            if mlabel:
                mv["label"] = mlabel
            self.s["moves"].append(mv)

    def place(self, placements: dict[str, dict], move: str | None = None, **common) -> None:
        """`put` every unit of a helper's result (e.g. deploy_line), with the same move type."""
        for uid, p in placements.items():
            self.put(uid, p, move=move if uid in self.cur else None, **common)

    def pin(self, uid: str, host: str) -> None:
        """Pin a marker (commander, standard, baggage) to a unit: it rides behind it."""
        if self.cur.get(uid, {}).get("with") == host:
            return
        self.s["positions"][uid] = {"with": host}
        self.cur[uid] = {**{k: v for k, v in self.cur.get(uid, {}).items() if k != "at"}, "with": host}

    def hide(self, uid: str) -> None:
        """Take a unit off the map (state hidden) until it is placed again."""
        self.put(uid, state="hidden")

    def fire(self, uid: str, target: Point | str, mlabel: str | None = None, **extra) -> None:
        """A missile/artillery arrow from the unit to a point or another unit."""
        end = self.at(target) if isinstance(target, str) else target
        mv = {"unit": uid, "type": "fire", "path": [r6(self.at(uid)), r6(end)], **extra}
        if mlabel:
            mv["label"] = mlabel
        self.s["moves"].append(mv)

    def side_move(self, side: str, kind: str, path: Sequence[Point], label: str | None = None, **extra) -> None:
        """An arrow for a whole side (an approach march), not tied to one unit."""
        mv = {"side": side, "type": kind, "path": [r6(p) for p in path], **extra}
        if label:
            mv["label"] = label
        self.s["moves"].append(mv)

    def note(self, at: Point, text: str, kind: str = "event", **extra) -> None:
        """A map note (≤70 chars) at a point; kind label|clash|death|capture|event."""
        self.s["notes"].append({"at": r6(at), "text": text, "kind": kind, **extra})

    def state(self, fid: str, **state) -> None:
        """Set a feature's state from this step on (schema 3): active=, state=,
        value_n=, value_label=, intensity=, area=, line=, at=, held_by=, label=."""
        self.s.setdefault("features", {}).setdefault(fid, {}).update(state)

    def doc(self, **meta) -> dict:
        """The finished document: `meta` (slug, kind, entity, title, …, sides,
        units, terrain) plus the recorded steps. Empty lists are dropped."""
        steps = []
        for st in self.steps:
            steps.append({k: v for k, v in st.items() if not (k in ("positions", "moves", "notes", "features") and not v)})
        return {"schema": meta.pop("schema", SCHEMA_VERSION), **meta, "steps": steps}
