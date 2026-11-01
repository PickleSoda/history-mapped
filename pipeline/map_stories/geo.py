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
USER_AGENT = "history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)"
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


def point_in_ring(p: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    """Whether `p` lies inside the (open or closed) ring — even-odd ray casting
    in lon/lat, fine at battlefield scale."""
    inside = False
    x, y = p[0], p[1]
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i - 1][:2], ring[i][:2]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def distance_to_line(p: Sequence[float], line: Sequence[Sequence[float]]) -> float:
    """The shortest distance in metres from `p` to a polyline."""
    if len(line) == 1:
        return distance(p, line[0])
    best = math.inf
    for a, b in zip(line, line[1:]):
        (ax, ay), (bx, by) = local(a, p), local(b, p)
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


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


# ── map scale (schema 3: routes, regions) ─────────────────────────────────


def r4(p: Sequence[float]) -> list[float]:
    """A point rounded to 4 decimals (~10 m): enough for continental features."""
    return [round(float(p[0]), 4), round(float(p[1]), 4)]


def great_circle(a: Sequence[float], b: Sequence[float], n: int = 16) -> list[list[float]]:
    """`n + 1` points along the shortest path over the globe from `a` to `b`
    (both included). Paths crossing the antimeridian are not split: keep
    stories on one side of it."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    va = (math.cos(lat1) * math.cos(lon1), math.cos(lat1) * math.sin(lon1), math.sin(lat1))
    vb = (math.cos(lat2) * math.cos(lon2), math.cos(lat2) * math.sin(lon2), math.sin(lat2))
    omega = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))
    if omega < 1e-9 or n < 1:
        return [r4(a), r4(b)]
    out = []
    for i in range(n + 1):
        t = i / n
        ka, kb = math.sin((1 - t) * omega) / math.sin(omega), math.sin(t * omega) / math.sin(omega)
        x, y, z = (ka * pa + kb * pb for pa, pb in zip(va, vb))
        out.append(r4((math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y))))))
    return out


def _projection(origin: Sequence[float]):  # noqa: ANN202
    """Azimuthal equidistant metres around `origin` (true distances from it): (forward, inverse)."""

    def fwd(p: Sequence[float]) -> tuple[float, float]:
        d, b = distance(origin, p), math.radians(bearing(origin, p))
        return d * math.sin(b), d * math.cos(b)

    def inv(x: float, y: float) -> list[float]:
        return r4(dest(origin, math.degrees(math.atan2(x, y)), math.hypot(x, y)))

    return fwd, inv


def buffer_ring(point: Sequence[float], km: float, n: int = 24) -> list[list[float]]:
    """A circle of radius `km` around `point`, as an open ring of `n` points."""
    return [r4(dest(point, 360 * i / n, km * 1000)) for i in range(n)]


def hull_region(points: Iterable[Sequence[float]], buffer_km: float, max_points: int = 48) -> list[list[float]]:
    """A spread region grown from places: the convex hull of `points`, widened
    by `buffer_km` all round and simplified to about `max_points` vertices (an
    open ring). One place gives a circle; two give a rounded band."""
    from shapely.geometry import MultiPoint

    pts = [tuple(p[:2]) for p in points]
    if not pts:
        raise ValueError("hull_region needs at least one point")
    origin = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    fwd, inv = _projection(origin)
    shape = MultiPoint([fwd(p) for p in pts]).convex_hull.buffer(buffer_km * 1000, quad_segs=8)
    tol = buffer_km * 1000 / 12
    while len(shape.exterior.coords) - 1 > max_points and tol < buffer_km * 1000:
        shape = shape.simplify(tol)
        tol *= 1.5
    return [inv(x, y) for x, y in list(shape.exterior.coords)[:-1]]


def merge_rings(*areas: Sequence) -> list[list[list[float]]]:
    """The union of rings (each argument one ring or a list of rings) as a list
    of simple rings — a multipolygon `area` (schema 3). Holes are dropped."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    polys = []
    for area in areas:
        is_multi = bool(area) and isinstance(area[0], (list, tuple)) and bool(area[0]) and isinstance(area[0][0], (list, tuple))
        for ring in area if is_multi else [area]:
            poly = Polygon([tuple(p[:2]) for p in ring])
            polys.append(poly if poly.is_valid else poly.buffer(0))
    merged = unary_union(polys)
    parts = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    return [[r4(c) for c in list(part.exterior.coords)[:-1]] for part in parts if not part.is_empty]


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
