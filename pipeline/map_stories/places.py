"""Find battlefield anchors: many place names in one cached, rate-limited batch.

    python -m pipeline.map_stories places "Hougoumont" "La Haye Sainte" "Plancenoit" --near 4.412,50.678
    python -m pipeline.map_stories places "Fiume Ofanto" --near 16.13,41.31 --geometry river
    python -m pipeline.map_stories places "Mont-Saint-Jean" --near 4.412,50.678 --elevation

One line per name: coordinates, the source (OSM via Nominatim first, Wikidata
P625 second), the distance and direction from --near, and AMBIGUOUS when two
different matches lie in range. --geometry prints a simplified line or outline
as a Python literal ready to paste into a builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.map_stories.geo import bearing, distance, lines_of, local, offset
from pipeline.map_stories.net import get_json, wd_entities, wd_search

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OPENTOPO = "https://api.opentopodata.org/v1/srtm30m"
#: --geometry kind → the Nominatim `category` values that fit it (first match wins).
GEOMETRY_CATEGORIES = {
    "river": ("waterway",),
    "stream": ("waterway",),
    "coast": ("natural", "place"),
    "lake": ("natural", "water"),
    "ridge": ("natural",),
    "hill": ("natural",),
    "woods": ("natural", "landuse", "boundary"),
    "marsh": ("natural", "wetland"),
    "road": ("highway",),
    "town": ("boundary", "place"),
}
AREA_KINDS = ("lake", "woods", "marsh", "hill", "town")
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


@dataclass
class Hit:
    name: str
    lon: float
    lat: float
    source: str
    km: float | None = None
    alts: list["Hit"] = field(default_factory=list)
    elevation: float | None = None


def compass(deg: float) -> str:
    return COMPASS[int(((deg % 360) + 22.5) // 45) % 8]


def viewbox(near: tuple[float, float], radius_km: float) -> str:
    sw = offset(near, east=-radius_km * 1000, north=-radius_km * 1000)
    ne = offset(near, east=radius_km * 1000, north=radius_km * 1000)
    return f"{sw[0]},{ne[1]},{ne[0]},{sw[1]}"


def nominatim(name: str, near: tuple[float, float] | None, radius_km: float, geometry: bool = False) -> list[dict]:
    params: dict = {"q": name, "format": "jsonv2", "limit": 6}
    if near:
        params.update(viewbox=viewbox(near, radius_km), bounded=1)
    if geometry:
        params["polygon_geojson"] = 1
    return list(get_json(NOMINATIM, params))


def distinct(hits: list[Hit], apart_m: float = 1000.0) -> list[Hit]:
    """Drop hits within `apart_m` of a better (earlier) one."""
    out: list[Hit] = []
    for h in hits:
        if all(distance((h.lon, h.lat), (o.lon, o.lat)) > apart_m for o in out):
            out.append(h)
    return out


def rank(hits: list[Hit], near: tuple[float, float] | None, radius_km: float) -> list[Hit]:
    """Hits in range, best first (the source's own order), each with its distance."""
    for h in hits:
        h.km = distance(near, (h.lon, h.lat)) / 1000 if near else None
    if near:
        hits = [h for h in hits if h.km is not None and h.km <= radius_km]
    return distinct(hits)


def lookup(name: str, near: tuple[float, float] | None, radius_km: float) -> Hit | None:
    hits = [Hit(name, float(r["lon"]), float(r["lat"]), f"osm:{r.get('category')}={r.get('type')}") for r in nominatim(name, near, radius_km)]
    ranked = rank(hits, near, radius_km)
    if not ranked:
        rows = wd_entities(wd_search(name)).values()
        ranked = rank([Hit(name, r["coord"][0], r["coord"][1], f"wd:{r['id']}") for r in rows if r.get("coord")], near, radius_km)
    if not ranked:
        return None
    best, *alts = ranked
    best.alts = alts
    return best


def elevations(points: list[tuple[float, float]]) -> list[float | None]:
    out: list[float | None] = []
    for i in range(0, len(points), 100):
        chunk = points[i : i + 100]
        data = get_json(OPENTOPO, {"locations": "|".join(f"{p[1]:.5f},{p[0]:.5f}" for p in chunk)})
        out.extend(r.get("elevation") for r in data.get("results", []))
    return out


def fmt(h: Hit | None, name: str, near: tuple[float, float] | None) -> str:
    if h is None:
        return f"{name[:28]:28}  NOT FOUND in range (try the local-language name, or widen --radius-km)"
    where = f"{h.km:5.1f} km {compass(bearing(near, (h.lon, h.lat))):2}" if near and h.km is not None else ""
    elev = f"  {h.elevation:4.0f} m" if h.elevation is not None else ""
    line = f"{name[:28]:28}  [{h.lon:.5f}, {h.lat:.5f}]  {h.source[:26]:26} {where}{elev}"
    if h.alts:
        alt = h.alts[0]
        line += f"  AMBIGUOUS {len(h.alts) + 1}: next [{alt.lon:.5f}, {alt.lat:.5f}] {alt.source[:20]}"
    return line


def _r5(p) -> list[float]:  # noqa: ANN001
    return [round(p[0], 5), round(p[1], 5)]


def shape_lines(geojson: dict, near: tuple[float, float], radius_km: float, max_points: int, area: bool) -> list[list[list[float]]]:
    """The geometry's lines (or outer rings) inside the radius, merged and
    simplified until all of them together have at most `max_points` points."""
    from shapely.geometry import LineString, MultiLineString, Point
    from shapely.ops import linemerge

    radius = radius_km * 1000
    parts = [[local(p, near) for p in line] for line in lines_of(geojson) if len(line) >= 2]
    if not parts:
        return []
    disk = Point(0, 0).buffer(radius, 64)
    geom = MultiLineString([LineString(p) for p in parts]).intersection(disk)
    merged = linemerge(geom) if geom.geom_type == "MultiLineString" else geom
    lines = [merged] if merged.geom_type == "LineString" else list(getattr(merged, "geoms", []))
    lines = sorted((ln for ln in lines if ln.length >= 150), key=lambda ln: -ln.length)[:4]
    tol = 15.0
    while True:
        simple = [ln.simplify(tol) for ln in lines]
        if sum(len(s.coords) for s in simple) <= max_points or tol > 2000:
            break
        tol *= 1.5
    return [[_r5(offset(near, east=x, north=y)) for x, y in s.coords] for s in simple]


def geometry_text(name: str, kind: str, near: tuple[float, float], radius_km: float, max_points: int) -> list[str]:
    rows = nominatim(name, near, radius_km, geometry=True) or nominatim(name, None, radius_km, geometry=True)
    cats = GEOMETRY_CATEGORIES.get(kind, ())
    fitting = [r for r in rows if r.get("category") in cats] if cats else rows
    if not fitting:
        found = ", ".join(sorted({f"{r.get('category')}={r.get('type')}" for r in rows})) or "nothing"
        return [f"# {name}: no OSM {kind} by that name in range (found: {found}); try the local-language name, e.g. 'Fiume Ofanto'"]
    best = max(fitting, key=lambda r: sum(len(x) for x in lines_of(r.get("geojson") or {})))
    lines = shape_lines(best.get("geojson") or {}, near, radius_km, max_points, kind in AREA_KINDS)
    if not lines:
        return [f"# {name}: OSM {best.get('category')}={best.get('type')} has no line inside {radius_km} km"]
    var = "".join(ch if ch.isalnum() else "_" for ch in name.upper()).strip("_")
    out = [f"# {name}: OSM {best.get('category')}={best.get('type')}, {len(lines)} part(s) inside {radius_km} km, {sum(len(x) for x in lines)} points"]
    for i, ln in enumerate(lines):
        out.append(f"{var}{'' if i == 0 else f'_{i + 1}'} = {ln}")
    return out


def run(names: list[str], near: tuple[float, float] | None, radius_km: float, geometry: str | None, with_elevation: bool, max_points: int) -> str:
    if geometry:
        if not near:
            raise SystemExit("--geometry needs --near LON,LAT")
        return "\n".join(line for n in names for line in geometry_text(n, geometry, near, radius_km, max_points))
    hits = [lookup(n, near, radius_km) for n in names]
    if with_elevation:
        found = [h for h in hits if h]
        for h, e in zip(found, elevations([(h.lon, h.lat) for h in found])):
            h.elevation = e
    return "\n".join(fmt(h, n, near) for h, n in zip(hits, names))
