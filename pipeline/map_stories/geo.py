"""Geometry helpers for writing map stories.

Story coordinates are `[lon, lat]` pairs (GeoJSON order). Builders place things
in metres around real anchors instead of guessing decimal degrees:

    from pipeline.map_stories.geo import *
    cannae = (16.1325, 41.3064)
    roman_centre = offset(cannae, east=-400, north=1200)
    front = dest(roman_centre, bearing=150, metres=900)

Lookups (`nominatim`, `place_geometry`, `elevation`) hit public services, are
cached under output/map-stories/cache/ and are rate-limited to one call a
second; use them while writing a builder, not at runtime.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Iterable, Sequence

import requests

EARTH_R = 6_371_008.8
LngLat = tuple[float, float]

REPO = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO / "output" / "map-stories" / "cache"
USER_AGENT = "history-mapped map-story builder (https://historymapped.org)"
_last_call = 0.0


# ── points ────────────────────────────────────────────────────────────────


def r6(p: Sequence[float]) -> list[float]:
    """A point rounded to 6 decimals (~10 cm), as a JSON-ready list."""
    return [round(float(p[0]), 6), round(float(p[1]), 6)]


def dest(p: Sequence[float], bearing: float, metres: float) -> list[float]:
    """The point `metres` from `p` along compass `bearing` (0 = north, 90 = east)."""
    lon1, lat1 = math.radians(p[0]), math.radians(p[1])
    b, d = math.radians(bearing), metres / EARTH_R
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return r6((math.degrees(lon2), math.degrees(lat2)))


def offset(p: Sequence[float], east: float = 0.0, north: float = 0.0) -> list[float]:
    """`p` moved `east` and `north` metres (negative = west / south)."""
    lat = math.radians(p[1])
    return r6((p[0] + math.degrees(east / (EARTH_R * math.cos(lat))), p[1] + math.degrees(north / EARTH_R)))


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Great-circle distance in metres."""
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def bearing(a: Sequence[float], b: Sequence[float]) -> float:
    """Initial compass bearing from `a` to `b`, 0–360."""
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlon = math.radians(b[0] - a[0])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def lerp(a: Sequence[float], b: Sequence[float], t: float) -> list[float]:
    """The point a fraction `t` of the way from `a` to `b` (fine at battlefield scale)."""
    return r6((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))


def mid(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return lerp(a, b, 0.5)


def local(p: Sequence[float], origin: Sequence[float]) -> tuple[float, float]:
    """`p` as (east, north) metres from `origin` — the inverse of `offset`."""
    lat = math.radians(origin[1])
    east = math.radians(p[0] - origin[0]) * EARTH_R * math.cos(lat)
    north = math.radians(p[1] - origin[1]) * EARTH_R
    return east, north


def rel(p: Sequence[float], facing: float, ahead: float = 0.0, right: float = 0.0) -> list[float]:
    """A point relative to a formation facing `facing`: `ahead` metres toward
    its front and `right` metres toward its right flank (negatives for behind /
    left). Handy for "the cavalry on the infantry's left wing"."""
    q = dest(p, facing, ahead) if ahead else r6(p)
    return dest(q, facing + 90, right) if right else q


# ── lines ─────────────────────────────────────────────────────────────────


def path(*points: Sequence[float]) -> list[list[float]]:
    return [r6(p) for p in points]


def arc(a: Sequence[float], b: Sequence[float], bulge: float, n: int = 8) -> list[list[float]]:
    """A curved path from `a` to `b` whose middle bows `bulge` metres to the
    right of the a→b direction (negative = to the left) — for flanking moves."""
    out = []
    head = bearing(a, b)
    for i in range(n + 1):
        t = i / n
        base = lerp(a, b, t)
        out.append(dest(base, head + 90, bulge * 4 * t * (1 - t)) if bulge else base)
    return out


def length(line: Sequence[Sequence[float]]) -> float:
    return sum(distance(line[i], line[i + 1]) for i in range(len(line) - 1))


def along(line: Sequence[Sequence[float]], t: float) -> list[float]:
    """The point a fraction `t` (0–1) of the way along a polyline."""
    total, target = length(line), max(0.0, min(1.0, t)) * length(line)
    for i in range(len(line) - 1):
        seg = distance(line[i], line[i + 1])
        if target <= seg or i == len(line) - 2:
            return lerp(line[i], line[i + 1], 0 if seg == 0 else min(1.0, target / seg))
        target -= seg
    return r6(line[-1])


def simplify(line: Sequence[Sequence[float]], tolerance_m: float = 25.0) -> list[list[float]]:
    """Douglas–Peucker in metres (via shapely in a local frame)."""
    from shapely.geometry import LineString

    if len(line) < 3:
        return [r6(p) for p in line]
    origin = line[0]
    xy = LineString([local(p, origin) for p in line]).simplify(tolerance_m)
    return [offset(origin, east=x, north=y) for x, y in xy.coords]


def clip(line: Sequence[Sequence[float]], center: Sequence[float], radius_m: float) -> list[list[float]]:
    """The longest run of a polyline inside `radius_m` of `center`."""
    best: list[list[float]] = []
    run: list[list[float]] = []
    for p in line:
        if distance(p, center) <= radius_m:
            run.append(r6(p))
        else:
            if len(run) > len(best):
                best = run
            run = []
    return run if len(run) > len(best) else best


def ellipse(center: Sequence[float], rx: float, ry: float, rotate: float = 0.0, n: int = 24) -> list[list[float]]:
    """An oval ring (`rx` east–west, `ry` north–south radius in metres, turned
    clockwise by `rotate` degrees) — for hills, woods, marshes, camps."""
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        r = math.radians(rotate)
        ring.append(offset(center, east=x * math.cos(r) + y * math.sin(r), north=-x * math.sin(r) + y * math.cos(r)))
    return ring


# ── lookups (cached, rate-limited) ────────────────────────────────────────


def _cached_get(url: str, params: dict) -> object:
    global _last_call
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    # One call a second across every builder process (Nominatim's usage policy):
    # hold a lock file while waiting out the previous call's slot.
    import fcntl

    with open(CACHE_DIR / ".ratelimit", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        lock.seek(0)
        stamp = lock.read().strip()
        last = max(_last_call, float(stamp) if stamp else 0.0)
        wait = 1.1 - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        lock.seek(0)
        lock.truncate()
        lock.write(str(_last_call))
        lock.flush()
        fcntl.flock(lock, fcntl.LOCK_UN)
    resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    cached.write_text(json.dumps(data))
    return data


def nominatim(query: str, limit: int = 5) -> list[dict]:
    """OpenStreetMap place search: [{name, lon, lat, type, display_name}, …]."""
    rows = _cached_get(
        "https://nominatim.openstreetmap.org/search",
        {"q": query, "format": "jsonv2", "limit": limit},
    )
    return [
        {"name": r.get("name"), "lon": float(r["lon"]), "lat": float(r["lat"]), "type": f"{r.get('category')}/{r.get('type')}", "display_name": r.get("display_name")}
        for r in rows  # type: ignore[union-attr]
    ]


def place_geometry(query: str, category: str | None = None) -> dict | None:
    """The OSM geometry (GeoJSON) of the most detailed of the top matches — a
    river's whole course, a lake's outline, a town's boundary. Use the local
    name for rivers ("Fiume Ofanto", not "Ofanto river": the English query
    matches single river segments). `category` filters, e.g. "waterway",
    "natural". Clip and simplify before use."""
    rows = _cached_get(
        "https://nominatim.openstreetmap.org/search",
        {"q": query, "format": "jsonv2", "limit": 5, "polygon_geojson": 1},
    )
    candidates = [r for r in rows if not category or r.get("category") == category]  # type: ignore[union-attr]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: sum(len(line) for line in lines_of(r.get("geojson") or {})))
    return best.get("geojson")


def lines_of(geojson: dict) -> list[list[list[float]]]:
    """Every LineString in a GeoJSON geometry (rivers come back as MultiLineString)."""
    t, c = geojson.get("type"), geojson.get("coordinates")
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return list(c)
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in c]
    return []


def elevation(points: Iterable[Sequence[float]]) -> list[float | None]:
    """Ground height in metres (SRTM 30 m, via opentopodata.org), ≤100 points a call."""
    pts = [r6(p) for p in points]
    out: list[float | None] = []
    for i in range(0, len(pts), 100):
        chunk = pts[i : i + 100]
        data = _cached_get(
            "https://api.opentopodata.org/v1/srtm30m",
            {"locations": "|".join(f"{p[1]},{p[0]}" for p in chunk)},
        )
        out.extend(r.get("elevation") for r in data.get("results", []))  # type: ignore[union-attr]
    return out


def profile(a: Sequence[float], b: Sequence[float], n: int = 20) -> list[tuple[float, float | None]]:
    """(distance from a in metres, elevation) along a→b — to find a ridge or a valley floor."""
    pts = [lerp(a, b, i / n) for i in range(n + 1)]
    return list(zip([distance(a, p) for p in pts], elevation(pts)))
