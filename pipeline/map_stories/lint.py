"""Numeric layout checks that catch what an author would otherwise have to
see in a preview: overlapping blocks, absurd densities, arrows that start in
the wrong place, colliding notes, over-wide framing, units that never move.

    from pipeline.map_stories.lint import lint
    for issue in lint(doc): print(issue.step, issue.code, issue.msg)

Run by `python -m pipeline.map_stories check` after `validate`. Every issue
is a warning: fix it or be sure it is deliberate. Schema-2 fields are honoured
where they matter (`beats`, `frame: false`, `strength_n`, `from`, `into`) and
ignored otherwise. Distances scale with the story kind (schema.SPREAD_KM /
TELEPORT_M), and the formation checks (overlap, contact, density, static) only
run for military kinds that have formation units.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass

from pipeline.map_stories.geo import distance, local
from pipeline.map_stories.schema import MILITARY_KINDS, POINT_UNIT_KINDS, SPREAD_KM, TELEPORT_M
from pipeline.map_stories.validate import resolve_beats, resolve_steps

#: Same-side blocks may overlap by this share of the smaller one's area.
SAME_SIDE_OVERLAP = 0.15
#: Opposing blocks overlapping by more than this share are "in contact".
OPPOSED_OVERLAP = 0.02
#: An arrow must start this close to where its unit stood (metres, by story
#: kind); kinds not listed allow TELEPORT_M / 7.5 (40 km for diffusion, 267 km
#: for an epidemic).
ARROW_START_M = {"battle": 300, "naval_battle": 500, "siege": 300, "campaign": 20_000}


def arrow_start_m(kind: str) -> float:
    return ARROW_START_M.get(kind) or TELEPORT_M.get(kind, 900) / 7.5
#: Men (or horses) per square metre a formation may plausibly hold.
DENSITY = {"foot": (0.01, 2.5), "mounted": (0.004, 0.8), "other": (0.002, 3.0)}
MOUNTED = {"cavalry", "heavy_cavalry", "light_cavalry", "horse_archers", "chariots", "elephants", "camels"}
NAVAL = {"warship", "transport", "ship"}
#: The atlas viewport assumed for camera and label checks (CSS px, after the panel).
VIEWPORT = (1100, 650)
FRAME_PAD = 44
MAX_ZOOM = 15.5
#: Spent states: a unit in one of these is not "in the way" of anything.
SPENT = {"destroyed", "captured", "sunk", "hidden"}
STATIC_RUN = 5


@dataclass
class Issue:
    step: str | None
    code: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.step or 'story'}] {self.code}: {self.msg}"


# ── frames ────────────────────────────────────────────────────────────────


def flatten_beats(doc: dict) -> dict:
    """A copy whose steps carry their beats' positions, moves and notes, so the
    step frames from `resolve_steps` are the final (after-last-beat) frames."""
    out = copy.deepcopy(doc)
    for st in out.get("steps", []):
        for beat in st.pop("beats", None) or []:
            for uid, pl in (beat.get("positions") or {}).items():
                merged = {**st.setdefault("positions", {}).get(uid, {}), **pl}
                if "at" in pl and "with" not in pl:
                    merged.pop("with", None)
                if "with" in pl and "at" not in pl:
                    merged.pop("at", None)
                st["positions"][uid] = merged
            st.setdefault("moves", []).extend(beat.get("moves") or [])
            st.setdefault("notes", []).extend(beat.get("notes") or [])
    return out


def _units(doc: dict) -> dict[str, dict]:
    return {u["id"]: u for u in doc.get("units", []) if isinstance(u, dict) and "id" in u}


def _is_formation(unit: dict | None) -> bool:
    return bool(unit) and unit.get("kind") not in POINT_UNIT_KINDS


def _default_depth(w: float) -> float:
    return max(20.0, min(w / 4, 120.0))


def footprint(pl: dict, origin) -> "object":  # noqa: ANN001 - shapely Polygon
    """The formation's outline in metres around `origin`, drawn as the atlas does."""
    from shapely.geometry import Polygon

    cx, cy = local(pl["at"], origin)
    f = math.radians(float(pl.get("facing", 0) or 0))
    w = float(pl.get("width", 300) or 300)
    d = float(pl.get("depth") or _default_depth(w))
    fx, fy = math.sin(f), math.cos(f)  # toward the front
    rx, ry = math.cos(f), -math.sin(f)  # toward the right flank

    def at(fwd: float, right: float) -> tuple[float, float]:
        return cx + fx * fwd + rx * right, cy + fy * fwd + ry * right

    shape = pl.get("shape", "block")
    if shape == "wedge":
        pts = [at(d / 2, 0), at(-d / 2, w / 2), at(-d / 2, -w / 2)]
    elif shape == "circle":
        pts = [at(math.cos(a) * d / 2, math.sin(a) * w / 2) for a in (2 * math.pi * i / 24 for i in range(24))]
    elif shape == "crescent":
        bulge = float(pl.get("curve", w * 0.18))
        front, back = [], []
        for i in range(13):
            x = -w / 2 + w * i / 12
            k = bulge * (1 - (2 * x / w) ** 2) - bulge / 2
            front.append(at(d / 2 + k, x))
            back.append(at(-d / 2 + k, x))
        pts = front + back[::-1]
    else:
        pts = [at(d / 2, -w / 2), at(d / 2, w / 2), at(-d / 2, w / 2), at(-d / 2, -w / 2)]
    poly = Polygon(pts)
    return poly if poly.is_valid else poly.buffer(0)


def _origin(frames: list[dict[str, dict]]) -> list[float] | None:
    for fr in frames:
        for pl in fr.values():
            if "at" in pl:
                return pl["at"]
    return None


# ── checks (each takes the flattened doc and its frames) ──────────────────


def check_overlaps(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Same-side blocks overlapping > 15% of the smaller; opposing blocks
    overlapping while neither is `engaged`."""
    units, origin, out = _units(doc), _origin(frames), []
    if origin is None:
        return out
    for st, fr in zip(doc["steps"], frames):
        live = [(uid, pl) for uid, pl in fr.items() if _is_formation(units.get(uid)) and "at" in pl and pl.get("state") not in SPENT and not pl.get("into")]
        polys = {uid: footprint(pl, origin) for uid, pl in live}
        for i, (a, pa) in enumerate(live):
            for b, pb in live[i + 1 :]:
                inter = polys[a].intersection(polys[b]).area
                if inter <= 0:
                    continue
                share = inter / max(1.0, min(polys[a].area, polys[b].area))
                same = units[a].get("side") == units[b].get("side")
                if same and share > SAME_SIDE_OVERLAP:
                    out.append(Issue(st.get("id"), "overlap", f"{a}/{b} {share:.0%} (same side)"))
                elif not same and share > OPPOSED_OVERLAP and "engaged" not in (pa.get("state"), pb.get("state")):
                    out.append(Issue(st.get("id"), "contact", f"{a}/{b} {share:.0%}, neither engaged"))
    return out


def check_density(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Men per m² from `strength_n` (unit or placement) against width × depth."""
    units, out, seen = _units(doc), [], set()
    for st, fr in zip(doc["steps"], frames):
        for uid, pl in fr.items():
            u = units.get(uid)
            n = pl.get("strength_n", (u or {}).get("strength_n"))
            if not _is_formation(u) or not isinstance(n, (int, float)) or n <= 0 or u.get("kind") in NAVAL or u.get("kind") in ("artillery", "siege_engine"):
                continue
            w = float(pl.get("width", 300) or 300)
            area = w * float(pl.get("depth") or _default_depth(w))
            dens = n / area
            lo, hi = DENSITY["mounted" if u.get("kind") in MOUNTED else "foot"]
            key = (uid, round(math.log10(dens), 1))
            if (dens > hi or dens < lo) and key not in seen:
                seen.add(key)
                what = "packed" if dens > hi else "sparse"
                out.append(Issue(st.get("id"), "density", f"{uid} {n:,.0f} in {w:.0f}×{area / w:.0f} m = {dens:.2f}/m² ({what}; {lo}–{hi})"))
    return out


def mpp(lat: float, zoom: float) -> float:
    """Metres per CSS pixel at a MapLibre zoom (512 px tiles)."""
    return 40_075_016.686 * math.cos(math.radians(lat)) / (512 * 2**zoom)


def check_camera(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Units outside a step's explicit camera (ignores `frame: false`)."""
    out = []
    for st, fr in zip(doc["steps"], frames):
        cam = st.get("camera")
        if not isinstance(cam, dict) or "center" not in cam or "zoom" not in cam:
            continue
        m = mpp(cam["center"][1], float(cam["zoom"]))
        half_w, half_h = VIEWPORT[0] / 2 * m, VIEWPORT[1] / 2 * m
        rot = math.radians(float(cam.get("bearing", 0) or 0))
        outside = []
        for uid, pl in fr.items():
            if "at" not in pl or pl.get("frame") is False:
                continue
            x, y = local(pl["at"], cam["center"])
            x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
            if abs(x) > half_w or abs(y) > half_h:
                outside.append(uid)
        if outside:
            out.append(Issue(st.get("id"), "camera", f"off-view: {', '.join(outside[:5])}{f' +{len(outside) - 5}' if len(outside) > 5 else ''}"))
    return out


def _framing_points(doc: dict, st: dict, fr: dict[str, dict], origin) -> list[tuple[float, float]]:  # noqa: ANN001
    units = _units(doc)
    pts: list[tuple[float, float]] = []
    for uid, pl in fr.items():
        if "at" not in pl or pl.get("frame") is False:
            continue
        if _is_formation(units.get(uid)):
            pts.extend(footprint(pl, origin).exterior.coords)
        else:
            pts.append(local(pl["at"], origin))
    for mv in st.get("moves") or []:
        pts.extend(local(p, origin) for p in mv.get("path") or [])
    for n in st.get("notes") or []:
        if "at" in n:
            pts.append(local(n["at"], origin))
    return pts


def framing_zoom(doc: dict, st: dict, fr: dict[str, dict], origin) -> float | None:  # noqa: ANN001
    """The zoom the atlas will frame this step at (its camera, or fit-to-content)."""
    cam = st.get("camera")
    if isinstance(cam, dict) and "zoom" in cam:
        return float(cam["zoom"])
    pts = _framing_points(doc, st, fr, origin)
    if not pts:
        return None
    dx = max(p[0] for p in pts) - min(p[0] for p in pts)
    dy = max(p[1] for p in pts) - min(p[1] for p in pts)
    m0 = mpp(origin[1], 0)
    need = max(dx / (VIEWPORT[0] - 2 * FRAME_PAD), dy / (VIEWPORT[1] - 2 * FRAME_PAD), 1e-6)
    return min(MAX_ZOOM, math.log2(m0 / need))


def note_box(x: float, y: float, text: str) -> tuple[float, float, float, float]:
    """A note label's pixel box: 12 px bold, wrapped at ~24 chars, above its point."""
    per_line = 24
    lines = max(1, math.ceil(len(text) / per_line))
    w = min(len(text), per_line) * 7.0 + 6
    h = lines * 14.5
    bottom = y - 17
    return (x - w / 2, bottom - h, x + w / 2, bottom)


def check_notes(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Note labels that collide at the step's framing zoom."""
    origin, out = _origin(frames), []
    if origin is None:
        return out
    for st, fr in zip(doc["steps"], frames):
        notes = [n for n in st.get("notes") or [] if "at" in n and isinstance(n.get("text"), str)]
        if len(notes) < 2:
            continue
        z = framing_zoom(doc, st, fr, origin)
        if z is None:
            continue
        m = mpp(origin[1], z)
        boxes = []
        for n in notes:
            x, y = local(n["at"], origin)
            boxes.append((n["text"], note_box(x / m, -y / m, n["text"])))
        for i, (ta, a) in enumerate(boxes):
            for tb, b in boxes[i + 1 :]:
                if a[0] < b[2] - 2 and b[0] < a[2] - 2 and a[1] < b[3] - 2 and b[1] < a[3] - 2:
                    out.append(Issue(st.get("id"), "notes", f"'{ta[:24]}' / '{tb[:24]}' at z{z:.1f}"))
    return out


def check_arrows(doc: dict, frames: list[dict[str, dict]], raw: dict) -> list[Issue]:
    """Unit arrows that don't start near where the unit stood before the move:
    a step's own arrows against the previous step's last frame, and each
    beat's arrows against the frame before that beat (`resolve_beats`)."""
    limit = arrow_start_m(raw.get("kind", "battle"))
    out = []
    raw_steps = [st for st in raw.get("steps", []) if isinstance(st, dict)]
    final = resolve_steps(raw)
    for i, st in enumerate(raw_steps):
        beats = [b for b in st.get("beats") or [] if isinstance(b, dict)]
        beat_frames = resolve_beats(raw, i) if beats else [final[i]]
        for k, phase in enumerate([st, *beats]):
            prev = (final[i - 1] if i else {}) if k == 0 else beat_frames[k - 1]
            now = beat_frames[k]
            for mv in phase.get("moves") or []:
                uid, path = mv.get("unit"), mv.get("path") or []
                if not uid or len(path) < 2:
                    continue
                refs = [prev[uid]["at"]] if uid in prev and "at" in prev[uid] else []
                src = (phase.get("positions") or {}).get(uid, {}).get("from")
                if src and src in prev and "at" in prev[src]:
                    refs.append(prev[src]["at"])
                if mv.get("type") == "fire" and uid in now and "at" in now[uid]:
                    refs.append(now[uid]["at"])
                if not refs:
                    continue
                d = min(distance(path[0], r) for r in refs)
                if d > limit:
                    where = f" beat {k}" if k else ""
                    out.append(Issue(st.get("id"), "arrow-start", f"{uid} {mv.get('type')} arrow{where} starts {d:.0f} m from where it stood"))
    return out


def check_framing(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Steps whose auto-framing spans more than the kind's spread limit."""
    origin, out = _origin(frames), []
    if origin is None:
        return out
    limit = SPREAD_KM.get(doc.get("kind", "battle"), 20) * 1000
    for st, fr in zip(doc["steps"], frames):
        if isinstance(st.get("camera"), dict):
            continue
        pts = _framing_points(doc, st, fr, origin)
        if not pts:
            continue
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
        if span > limit:
            out.append(Issue(st.get("id"), "framing", f"spans {span / 1000:.0f} km > {limit / 1000:.0f}"))
    return out


_SENT = re.compile(r"(?<=[.!?])\s+")


#: Label words too generic to identify a unit in a sentence.
GENERIC = {"army", "infantry", "cavalry", "horse", "foot", "left", "right", "centre", "center", "wing", "line",
           "corps", "division", "guard", "light", "heavy", "troops", "with", "from", "allied", "allies", "reserve"}


def _unit_words(unit: dict) -> set[str]:
    words = {w for w in re.findall(r"[a-z\u00c0-\u024f]{4,}", (unit.get("label") or "").casefold())} - GENERIC
    return words | ({w for w in str(unit.get("id", "")).split("-") if len(w) >= 4} - GENERIC)


def says_advances(sentence: str, unit: dict) -> bool:
    """Does the sentence say this unit advances? A distinctive word of its label
    or id must come shortly before "advanc…", and the verb must not be negated."""
    s = sentence.casefold()
    words = _unit_words(unit)
    for m in re.finditer(r"advanc", s):
        before = s[max(0, m.start() - 60) : m.start()]
        if re.search(r"\b(rather than|instead of|not|never|without|before)\W+(\w+\W+)?$", before):
            continue
        if any(re.search(rf"\b{re.escape(w)}", before) for w in words):
            return True
    return False


def check_static(doc: dict, frames: list[dict[str, dict]]) -> list[Issue]:
    """Units that stay put for 5+ steps while a narrative sentence naming them says they advance."""
    units = _units(doc)
    steps, out = doc["steps"], []
    for uid, u in units.items():
        if not _is_formation(u):
            continue
        run: list[int] = []
        for i, fr in enumerate(frames):
            moved = any(mv.get("unit") == uid for mv in steps[i].get("moves") or [])
            here = fr.get(uid, {}).get("at")
            before = frames[i - 1].get(uid, {}).get("at") if i else None
            if here and before and not moved and distance(here, before) < 50:
                run.append(i)
                continue
            out.extend(_static_issue(uid, u, run, steps))
            run = [i] if here else []
        out.extend(_static_issue(uid, u, run, steps))
    return out


def _static_issue(uid: str, unit: dict, run: list[int], steps: list[dict]) -> list[Issue]:
    if len(run) < STATIC_RUN:
        return []
    for i in run[1:]:
        for sentence in _SENT.split(steps[i].get("narrative") or ""):
            if says_advances(sentence, unit):
                ids = f"{steps[run[0]].get('id')}…{steps[run[-1]].get('id')}"
                return [Issue(steps[i].get("id"), "static", f"{uid} still for {len(run)} steps ({ids}) though the narrative says it advances")]
    return []


def has_formations(doc: dict) -> bool:
    """Whether the formation checks apply: a military kind with formation units."""
    return doc.get("kind", "battle") in MILITARY_KINDS and any(_is_formation(u) for u in _units(doc).values())


def lint(doc: dict) -> list[Issue]:
    """Every layout issue in a (validated) document."""
    flat = flatten_beats(doc)
    if not flat.get("steps"):
        return []
    frames = resolve_steps(flat)
    formations = has_formations(flat)
    issues: list[Issue] = []
    if formations:
        issues += check_overlaps(flat, frames)
        issues += check_density(flat, frames)
    issues += check_camera(flat, frames)
    issues += check_notes(flat, frames)
    issues += check_arrows(flat, frames, doc)
    issues += check_framing(flat, frames)
    if formations:
        issues += check_static(flat, frames)
    return issues
