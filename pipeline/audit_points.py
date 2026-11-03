#!/usr/bin/env python3
"""Map-point audit: find and fix wrong points on entities that already have one.

The map draws an entity at its geometry_periods point; the admin shows its
primary entity_locations point. This audits the points that are already there
(placing entities that have none is pipeline/backfill_geo.py's job) and, under
the same rule, fixes the wrong ones:

  * the entity's own OHM feature (QID-tagged) or, for point-like types, its own
    Wikidata P625 is the only acceptable source of a point;
  * a related place's coordinate is never borrowed.

Where a point came from is read from the entity's geo refs and checked against
the coordinates themselves:

  own_p625    within 1 km of the entity's own P625 (or written by geo-backfill:wikidata_p625)
  ohm_own     written by geo-backfill:ohm (a QID-tagged OHM feature)
  borrowed    the P625 of another item, recorded as wikidata_place_of_association by the
              campaign import (birth/death/work place, location, HQ, admin area, country)
  centroid    chronicle_centroid: the mean of a chronicle's other points, no place at all
  stale_qid   the P625 of a QID the entity no longer carries
  derived     a derive:located_at presence period (a copy of the located_at target's point)
  unknown     none of these

What is suspect (the brief's three scopes, plus two exact markers):

  1. cluster          5+ points on one exact coordinate, unless the point is the entity's own
  2. far_from_p625    a point-like type more than 300 km from its own P625
  3. outside_ohm      a polity more than 300 km outside its own OHM relation's bbox (1000 km
                      from a node/way), or more than 2500 km from its own Wikidata coordinate
  +  centroid         every chronicle_centroid point, clustered or not
  +  lon_range        a longitude outside -180..180

and what is done, in order:

  replace   the entity's own OHM point (backfill_geo.pick_ohm) or own P625 (point-like types),
            written exactly as backfill_geo.apply_plan writes it, keeping the period's years;
  delete    no own source and the point is clearly not the entity's (a centroid, a borrowed
            person/organisation/country coordinate, far outside its own OHM extent, or a
            derived copy of a point removed here): the period row goes and the primary
            entity_locations.geom is nulled;
  keep      an event or site "located" (P276/P131) in a town or site (not a country, region
            or museum): it happened there;
  list      anything unsure, left as is: a P625 that contradicts the entity's own located-in
            place or its located_at target (more likely a namesake's QID), a QID-less point
            from an old QID, an entity a map story uses.

An OHM replacement is checked against a mis-tagged feature (far from the entity's own
Wikidata coordinate, or with no own coordinate and no shared name), and a bbox centre
is taken across the 180th meridian (backfill_geo.ohm_point averages the raw longitudes
and put the Kingdom of Fiji and Tuvalu in the Atlantic).

An entity with a bad entity_locations point and no geometry period gets only its
location nulled (null_location): placing it is the later backfill's job, which
fills a location only where its geom is NULL. For the same reason an admin
location left on an old point (more than 25 km off, not its own P625, not set by
a human) under a map point from the entity's own source is set to that map point
(sync_location), as backfill_geo would have mirrored it.

Derived presence periods (period_type 'presence', provenance 'derived') are map
points like any other: the map query does not filter on period_type and keeps one
period per entity, so a derive:located_at copy is drawn as the entity's point. A
copy of a point this run moves or removes goes too.

Dry run by default (writes planned.csv). --apply backs up the touched tables,
applies every change in one transaction (guarded on the values read, one
savepoint per entity), writes applied.csv and rollback.sql and tests the
rollback inside a transaction that is rolled back.

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit_points           # plan
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit_points --apply   # write
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg  # noqa: E402

from pipeline.audit.wd import QID_RE, SPARQL, WikidataClient  # noqa: E402
from pipeline.backfill_geo import (  # noqa: E402
    DSN,
    OHM_TIER,
    WIKIDATA_POINT_TYPES,
    WIKIDATA_TIER,
    apply_plan,
    confidence,
    fetch_ohm,
    km,
    load_ohm_refs,
    pick_ohm,
)

OUT_DIR = _REPO_ROOT / "output" / "audit" / "points-20261101"
MERGE_VERDICTS = _REPO_ROOT / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
STORIES_DIR = _REPO_ROOT / "api" / "resources" / "map-stories"
COMPOSE = ["docker", "compose", "-f", str(_REPO_ROOT / "docker" / "docker-compose.yml")]
# User-decision rows no agent writes to.
EXCLUDED_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")

CLUSTER_MIN = 5
SAME_KM = 1.0
FAR_FROM_P625_KM = 300
OUTSIDE_BBOX_KM = 300
FAR_FROM_OHM_POINT_KM = 1000
LOCATION_GAP_KM = 25
AREA_TARGET_KM = 800   # a place "located at" a country, checked against the country's centroid
OTHER_CONTINENT_KM = 2500
POLITY_TYPES = frozenset({"political_entity"})

# Wikidata classes of an item too large to stand for where something happened
# (its P625 is a country/region centroid, or the middle of a sea, river or lake).
# An event "located in" one of these sits on a fallback centroid, not a site.
AREA_CLASSES = frozenset({
    # countries, states and their subdivisions
    "Q6256", "Q3624078", "Q3024240", "Q7275", "Q7270", "Q512187", "Q859563", "Q179164", "Q123480",
    "Q1763527", "Q3336843", "Q107390", "Q35657", "Q10864048", "Q34876", "Q11828004", "Q50337",
    "Q2311958", "Q48349", "Q417175", "Q1250464", "Q12759805", "Q20181813", "Q43702", "Q182547",
    "Q164142", "Q2577883", "Q15239622", "Q99541706", "Q3591867", "Q1145276", "Q26830017",
    "Q5098", "Q12443800", "Q860290", "Q180673", "Q5852411",
    # regions, civilisations, continents, seas, rivers, lakes, ranges, peninsulas
    "Q28171280", "Q1620908", "Q82794", "Q3502482", "Q3434769", "Q123615496", "Q1970725", "Q107425",
    "Q5107", "Q165", "Q9430", "Q4022", "Q23397", "Q39594", "Q12284", "Q46831", "Q1402592", "Q34763",
})
# A place that is also a city (Tokyo is a prefecture, London a political territorial
# entity) stands for its centre.
CITY_CLASSES = frozenset({
    "Q515", "Q1549591", "Q174844", "Q200250", "Q5119", "Q1637706", "Q486972", "Q3957", "Q532",
    "Q133442", "Q839954", "Q15661340", "Q484170", "Q747074", "Q2074737", "Q15284", "Q1093829",
    "Q748149", "Q7930989", "Q1066984", "Q208511", "Q51929311",
})
# Museums, archives and other institutions: an object's P276 there is where it is kept
# now (the Rosetta Stone in the British Museum), not where its history happened.
INSTITUTION_CLASSES = frozenset({
    "Q33506", "Q207694", "Q17431399", "Q3343298", "Q708676", "Q3196771", "Q1007870", "Q163740",
    "Q166118", "Q7075", "Q31855", "Q3918", "Q43229", "Q2085381", "Q2668072",
})
PALACE_CLASSES = frozenset({"Q16560", "Q53536964", "Q23413"})
# Where a located-in place can stand for an entity's own site.
SITE_PROPS = ("P276", "P131")
SITE_GROUPS = frozenset({"EVENT", "PLACE"})
SITE_TYPES = frozenset({"cultural_work", "religious_text"})


def norm_lon(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


def wd_point(rec: dict | None) -> tuple[float, float] | None:
    """(lon, lat) of a Wikidata record's P625 (stored as [lat, lon])."""
    c = (rec or {}).get("coord")
    return (norm_lon(c[1]), c[0]) if c else None


def wd_points(rec: dict | None) -> list[tuple[float, float]]:
    """Every P625 of a record (a battle or a work may carry several)."""
    cs = (rec or {}).get("coords") or ([rec["coord"]] if (rec or {}).get("coord") else [])
    return [(norm_lon(c[1]), c[0]) for c in cs]


def km_to_own(pt: tuple[float, float], rec: dict | None) -> float | None:
    """Distance to the nearest of a record's own coordinates."""
    pts = wd_points(rec)
    return min(km(pt, c) for c in pts) if pts else None


def one_site(rec: dict | None) -> tuple[float, float] | None:
    """The record's P625 when it names one site (several values within 50 km), else None."""
    pts = wd_points(rec)
    if not pts or any(km(pts[0], c) > 50 for c in pts[1:]):
        return None
    return pts[0]


def crosses_antimeridian(b: dict) -> bool:
    """Overpass gives a feature across the 180th meridian minlon > maxlon (Fiji: 174.6 .. -178.2)."""
    return b["minlon"] > b["maxlon"]


def km_outside_bbox(pt: tuple[float, float], b: dict) -> float:
    """0 inside an Overpass bounds dict, else the distance to its nearest edge."""
    lon, lat = norm_lon(pt[0]), min(max(pt[1], b["minlat"]), b["maxlat"])
    inside = (b["minlon"] <= lon <= b["maxlon"] if not crosses_antimeridian(b)
              else lon >= b["minlon"] or lon <= b["maxlon"])
    if inside:
        return km((lon, pt[1]), (lon, lat))
    return min(km((lon, pt[1]), (edge, lat)) for edge in (b["minlon"], b["maxlon"]))


def bbox_centre(b: dict) -> tuple[float, float]:
    """The centre of an Overpass bounds dict, across the 180th meridian too
    (backfill_geo.ohm_point averages the raw longitudes and puts Fiji in the Atlantic)."""
    span = b["maxlon"] - b["minlon"] + (360 if crosses_antimeridian(b) else 0)
    return norm_lon(b["minlon"] + span / 2), (b["minlat"] + b["maxlat"]) / 2


GENERIC_WORDS = frozenset({
    "dynasty", "kingdom", "empire", "republic", "province", "state", "county", "duchy", "principality",
    "sultanate", "caliphate", "khanate", "people", "culture", "city", "battle", "treaty", "great",
    "northern", "southern", "eastern", "western", "upper", "lower", "united", "first", "second", "socialist",
    "people's", "democratic", "federal", "federation", "commandery", "territory", "colony", "the",
})


def name_words(*names: str | None) -> set[str]:
    return {w for n in names for w in re.findall(r"[^\W\d_]{4,}", (n or "").lower())} - GENERIC_WORDS


def ohm_names(el: dict) -> list[str]:
    tags = el.get("tags", {})
    return [v for k, v in tags.items() if k in ("name", "official_name", "alt_name", "old_name", "short_name")
            or k.startswith(("name:", "official_name:"))]


def is_area(rec: dict | None) -> bool:
    p31 = set((rec or {}).get("p31") or [])
    return bool(p31 & AREA_CLASSES) and not p31 & CITY_CLASSES


# ── Wikidata ────────────────────────────────────────────────────────────────
GEO_PROPS = ("P625", "P31", "P19", "P20", "P276", "P131")
EARTH = "http://www.wikidata.org/entity/Q2"


def parse_wkt_point(v: str) -> list[float] | None:
    """[lat, lon] of a WDQS coordinate literal; None for another globe (a Mars crater)."""
    m = re.match(r"^(?:<([^>]+)>\s*)?Point\(([-0-9.eE+]+) ([-0-9.eE+]+)\)$", v.strip())
    if not m or (m.group(1) and m.group(1) != EARTH):
        return None
    return [float(m.group(3)), float(m.group(2))]


def geo_records(bindings: list[dict], batch: list[str]) -> dict[str, dict]:
    """Records (status, label, p31, links, coords) from the query service's rows."""
    recs: dict[str, dict] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        k, v = b["k"]["value"], b["v"]["value"]
        r = recs.setdefault(qid, {"status": "missing", "label": "", "p31": [], "links": {}, "coords": []})
        if k == "version":
            r["status"] = "ok" if r["status"] != "redirect" else "redirect"
        elif k == "redirect":
            r.update(status="redirect", redirect_to=v.rsplit("/", 1)[-1])
        elif k == "label":
            r["label"] = v
        elif k == "P625":
            c = parse_wkt_point(v)
            if c and c not in r["coords"]:
                r["coords"].append(c)
            elif c is None:
                r["offworld"] = True
        elif v.startswith("http://www.wikidata.org/entity/Q"):
            target = r["p31"] if k == "P31" else r["links"].setdefault(k, [])
            q = v.rsplit("/", 1)[-1]
            if q not in target:
                target.append(q)
    for qid in batch:
        recs.setdefault(qid, {"status": "missing"})
    for r in recs.values():
        if r.get("coords"):
            r["coords"].sort()
            r["coord"] = r["coords"][0]
        elif r["status"] == "ok":
            r["coord"] = None
    return recs


def fetch_geo(qids: set[str], cache_dir: Path, offline: bool = False) -> dict[str, dict]:
    """P625, P31, birth/death place, location, admin area and English label per QID.

    Read from the query service, 200 ids a query, through the audit client (its
    User-Agent, ~1 request/s and 429 back-off): the API's maxlag tracks the query
    service's update lag and refused reads all evening, while minutes-old data is
    fine for coordinates. Cached in cache_dir/wdqs-geo.jsonl.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "wdqs-geo.jsonl"
    recs: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            recs[r.pop("qid")] = r
    client = WikidataClient(cache_dir, max_rps=1.0, workers=1, offline=offline)
    rounds = 0
    while rounds < 3:
        rounds += 1
        todo = sorted({q for q in qids if q and QID_RE.match(q)} - recs.keys(), key=lambda q: int(q[1:]))
        if not todo or offline:
            break
        print(f"   query service: {len(todo)} items", flush=True)
        for i in range(0, len(todo), 200):
            batch = todo[i:i + 200]
            union = " UNION ".join(
                [f'{{ ?item wdt:{p} ?v . BIND("{p}" AS ?k) }}' for p in GEO_PROPS]
                + ['{ ?item schema:version ?v . BIND("version" AS ?k) }',
                   '{ ?item owl:sameAs ?v . BIND("redirect" AS ?k) }',
                   '{ ?item rdfs:label ?v . FILTER(lang(?v) = "en") BIND("label" AS ?k) }'])
            query = f"SELECT ?item ?k ?v WHERE {{ VALUES ?item {{ {' '.join('wd:' + q for q in batch)} }} {union} }}"
            rows = client._get(SPARQL, {"query": query, "format": "json"}, timeout=120).json()["results"]["bindings"]
            got = geo_records(rows, batch)
            with path.open("a", encoding="utf-8") as fh:
                for q, r in got.items():
                    fh.write(json.dumps({"qid": q, **r}, ensure_ascii=False) + "\n")
            recs.update(got)
            if (i // 200) % 25 == 0:
                print(f"   query service {min(i + 200, len(todo))}/{len(todo)}", flush=True)
        # Follow redirects to their targets.
        qids = {r["redirect_to"] for r in recs.values() if r.get("status") == "redirect"}
    return recs


# ── data ────────────────────────────────────────────────────────────────────
@dataclass
class Point:
    """One map point (a geometry_periods row) or an admin-only entity_locations point."""

    kind: str                      # 'period' | 'location'
    entity_id: str
    name: str
    type: str
    group: str
    qid: str | None
    lon: float
    lat: float
    gp_id: str | None = None
    created_by: str = ""
    period_type: str = ""
    start: int | None = None
    end: int | None = None
    relationship_id: str | None = None
    target_id: str | None = None   # located_at target of a derived period
    target_qid: str | None = None
    loc_id: str | None = None
    loc_pt: tuple[float, float] | None = None
    loc_method: str | None = None
    primary_geo_ref_id: str | None = None
    wd_refs: list[dict] = field(default_factory=list)
    cluster_n: int = 1

    @property
    def pt(self) -> tuple[float, float]:
        return (self.lon, self.lat)

    @property
    def key(self) -> tuple[float, float]:
        return (round(self.lon, 5), round(self.lat, 5))


def load_points(cur) -> list[Point]:
    cur.execute("""
        SELECT 'period', gp.entity_id::text, e.name, e.entity_type::text, e.entity_group::text,
               NULLIF(e.wikidata_id, ''), ST_X(gp.geom), ST_Y(gp.geom), gp.geometry_period_id::text,
               coalesce(gp.created_by, ''), gp.period_type, gp.start_year, gp.end_year,
               gp.relationship_id::text, r.target_entity_id::text, NULLIF(t.wikidata_id, ''),
               l.location_id::text, ST_X(l.geom), ST_Y(l.geom), e.primary_geo_ref_id::text,
               l.location_method
        FROM geometry_periods gp
        JOIN entities e ON e.entity_id = gp.entity_id
        LEFT JOIN relationships r ON r.relationship_id = gp.relationship_id
        LEFT JOIN entities t ON t.entity_id = r.target_entity_id
        LEFT JOIN entity_locations l ON l.entity_id = gp.entity_id AND l.is_primary
        WHERE gp.geom IS NOT NULL AND gp.territory_geom IS NULL AND GeometryType(gp.geom) = 'POINT'
        UNION ALL
        SELECT 'location', l.entity_id::text, e.name, e.entity_type::text, e.entity_group::text,
               NULLIF(e.wikidata_id, ''), ST_X(l.geom), ST_Y(l.geom), NULL, '', '', NULL, NULL,
               NULL, NULL, NULL, l.location_id::text, ST_X(l.geom), ST_Y(l.geom), e.primary_geo_ref_id::text,
               l.location_method
        FROM entity_locations l
        JOIN entities e ON e.entity_id = l.entity_id
        WHERE l.is_primary AND l.geom IS NOT NULL AND l.territory_geom IS NULL
          AND GeometryType(l.geom) = 'POINT'
          AND NOT EXISTS (SELECT 1 FROM geometry_periods gp WHERE gp.entity_id = l.entity_id)
    """)
    pts = []
    for r in cur.fetchall():
        pts.append(Point(kind=r[0], entity_id=r[1], name=r[2], type=r[3], group=r[4], qid=r[5],
                         lon=r[6], lat=r[7], gp_id=r[8], created_by=r[9], period_type=r[10],
                         start=r[11], end=r[12], relationship_id=r[13], target_id=r[14], target_qid=r[15],
                         loc_id=r[16], loc_pt=(r[17], r[18]) if r[17] is not None else None,
                         primary_geo_ref_id=r[19], loc_method=r[20]))
    cur.execute("""
        SELECT entity_id::text, geo_ref_id::text, external_id, is_active, source_meta->>'source',
               geometry_period_id::text
        FROM entity_geo_refs WHERE provider = 'wikidata'
    """)
    refs: dict[str, list[dict]] = defaultdict(list)
    for eid, rid, ext, active, src, gpid in cur.fetchall():
        refs[eid].append({"geo_ref_id": rid, "external_id": ext, "is_active": active, "source": src or "",
                          "geometry_period_id": gpid})
    # Clusters are counted over map points and admin-only points alike.
    counts = Counter(p.key for p in pts)
    for p in pts:
        p.wd_refs = refs.get(p.entity_id, [])
        p.cluster_n = counts[p.key]
    return pts


def excluded_ids() -> set[str]:
    out: set[str] = set()
    if MERGE_VERDICTS.exists():
        with MERGE_VERDICTS.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                for k in ("survivor_id", "loser_id"):
                    if row.get(k):
                        out.add(row[k].strip().lower())
    return out


def is_excluded(eid: str, excl: set[str]) -> bool:
    return eid in excl or eid.startswith(EXCLUDED_PREFIXES)


def story_qids() -> set[str]:
    out: set[str] = set()
    for f in STORIES_DIR.glob("*.json"):
        def walk(o: Any) -> None:
            if isinstance(o, dict):
                q = o.get("wikidata")
                if isinstance(q, str):
                    out.add(q)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(f.read_text()))
    return out


# ── assessment ──────────────────────────────────────────────────────────────
def resolved(wd: dict, qid: str | None) -> dict | None:
    """A cached record, following redirects."""
    seen = set()
    rec = wd.get(qid) if qid else None
    while rec and rec.get("status") == "redirect" and qid not in seen:
        seen.add(qid)
        qid = rec["redirect_to"]
        rec = wd.get(qid)
    return rec if rec and rec.get("status") == "ok" else None


def origin(p: Point, wd: dict) -> tuple[str, str | None, str | None]:
    """(origin, source QID, property) of a point, per the module docstring."""
    own = resolved(wd, p.qid)
    own_km = km_to_own(p.pt, own)
    if p.created_by == OHM_TIER:
        return "ohm_own", p.qid, None
    if p.created_by == WIKIDATA_TIER:
        return "own_p625", p.qid, "P625"
    if p.created_by == "derive:located_at":
        return "derived", None, "located_at"
    if own_km is not None and own_km <= SAME_KM:
        return "own_p625", p.qid, "P625"
    links = (own or {}).get("links") or {}
    borrowed = None
    for ref in sorted(p.wd_refs, key=lambda r: not r["is_active"]):
        ext = ref["external_id"]
        if p.qid and (ext == p.qid or resolved(wd, ext) is own and own is not None):
            if ref["source"] == "chronicle_centroid":
                return "centroid", None, None
            continue
        place = resolved(wd, ext)
        place_km = km_to_own(p.pt, place)
        at_place = place_km is not None and place_km <= SAME_KM
        if ref["source"] == "chronicle_centroid" and not at_place:
            return "centroid", None, None
        if ref["source"] == "wikidata_p625" and at_place:
            return "stale_qid", ext, "P625"
        if ref["source"] == "wikidata_place_of_association" and (at_place or borrowed is None):
            prop = next((pr for pr in ("P19", "P20", "P276", "P131") if ext in links.get(pr, [])), "other")
            borrowed = ("borrowed", ext, prop if p.qid else "unknown")
            if at_place:
                return borrowed
    return borrowed or ("unknown", None, None)


@dataclass
class Verdict:
    issues: list[str]
    origin: str
    source_qid: str | None
    prop: str | None
    action: str                    # replace | delete | null_location | keep | list | skip_excluded
    reason: str
    new: dict | None = None        # backfill_geo-style plan for a replacement


def is_institution(rec: dict | None) -> bool:
    p31 = set((rec or {}).get("p31") or [])
    return bool(p31 & INSTITUTION_CLASSES) and not p31 & (CITY_CLASSES | PALACE_CLASSES)


def site_like(p: Point, prop: str | None, place: dict | None) -> bool:
    """An event/site/work located (P276/P131) in a town or site rather than a country or a museum."""
    return ((p.group in SITE_GROUPS or p.type in SITE_TYPES) and prop in SITE_PROPS
            and place is not None and not is_area(place) and not is_institution(place))


def find_issues(p: Point, org: str, wd: dict, ohm: "OhmIndex") -> list[str]:
    issues = []
    own = resolved(wd, p.qid)
    own_km = km_to_own(p.pt, own)
    if abs(p.lon) > 180 or abs(p.lat) > 90:
        issues.append("lon_range")
    if p.cluster_n >= CLUSTER_MIN and org not in ("own_p625", "ohm_own"):
        issues.append(f"cluster:{p.cluster_n}")
    if org == "centroid":
        issues.append("centroid")
    if p.type in WIKIDATA_POINT_TYPES and own_km is not None and own_km > FAR_FROM_P625_KM:
        issues.append(f"far_from_p625:{own_km:.0f}km")
    if p.type in POLITY_TYPES or org == "ohm_own":
        if ohm.tagged(p):
            off = ohm.distance_outside(p)
            if off is not None:
                issues.append(f"outside_ohm:{off:.0f}km")
        elif (p.type in POLITY_TYPES and own_km is not None and org not in ("own_p625", "ohm_own")
              and own_km > OTHER_CONTINENT_KM):
            # A polity's P625 is only a centroid: it flags a point on another continent, never places one.
            issues.append(f"far_from_wikidata:{own_km:.0f}km")
    return issues


def load_ohm_cache(path: Path, refs: list[dict], offline: bool) -> tuple[dict, dict]:
    """backfill_geo.fetch_ohm, cached on disk (features keyed "type/id", label nodes by id)."""
    data = json.loads(path.read_text()) if path.exists() else {"elements": {}, "nodes": {}, "absent": []}
    elements = {(k.split("/")[0], int(k.split("/")[1])): v for k, v in data["elements"].items()}
    nodes = {int(k): tuple(v) for k, v in data["nodes"].items()}
    absent = set(data["absent"])
    missing = [r for r in refs if (r["external_type"], int(r["external_id"])) not in elements
               and f"{r['external_type']}/{r['external_id']}" not in absent]
    if missing and not offline:
        got, got_nodes = fetch_ohm(missing)
        elements.update(got)
        nodes.update(got_nodes)
        absent |= {f"{r['external_type']}/{r['external_id']}" for r in missing
                   if (r["external_type"], int(r["external_id"])) not in got}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"elements": {f"{t}/{i}": v for (t, i), v in elements.items()},
                                    "nodes": {str(k): list(v) for k, v in nodes.items()},
                                    "absent": sorted(absent)}))
    return elements, nodes


class OhmIndex:
    """An entity's QID-tagged OHM features, from backfill_geo's fetch."""

    def __init__(self, refs_by_entity: dict[str, list[dict]], elements: dict, nodes: dict):
        self.refs = refs_by_entity
        self.elements = elements
        self.nodes = nodes

    def tagged(self, p: Point) -> list[dict]:
        out = []
        for ref in self.refs.get(p.entity_id, []):
            el = self.elements.get((ref["external_type"], int(ref["external_id"])))
            if el is not None and p.qid and el.get("tags", {}).get("wikidata") == p.qid:
                out.append(el)
        return out

    def distance_outside(self, p: Point) -> float | None:
        """How far a polity's point lies outside its own OHM features, when too far."""
        els = self.tagged(p)
        if not els:
            return None
        best = None
        for el in els:
            if el.get("bounds"):
                d, limit = km_outside_bbox(p.pt, el["bounds"]), OUTSIDE_BBOX_KM
            elif el["type"] == "node":
                d, limit = km(p.pt, (el["lon"], el["lat"])), FAR_FROM_OHM_POINT_KM
            elif el.get("center"):
                d, limit = km(p.pt, (el["center"]["lon"], el["center"]["lat"])), FAR_FROM_OHM_POINT_KM
            else:
                continue
            ok = d <= limit
            if ok:
                return None
            best = d if best is None else min(best, d)
        return best

    def pick(self, p: Point, own_pt: tuple[float, float] | None):
        entity = {"entity_type": p.type, "wikidata_id": p.qid}
        return pick_ohm(entity, self.refs.get(p.entity_id, []), self.elements, self.nodes, own_pt)


def own_ohm_point(p: Point, own: dict | None, ohm: OhmIndex) -> tuple[dict, float, float, str] | None:
    """backfill_geo.pick_ohm, with the bbox centre taken across the 180th meridian, and a check
    against a mis-tagged feature (OHM's Sisak carries the National People's Congress's QID): a
    feature far from the entity's own Wikidata coordinate, or, without one, sharing no name
    with it, is not taken."""
    pick, _ = ohm.pick(p, one_site(own))
    if not pick:
        return None
    ref, (lon, lat, kind) = pick
    el = ohm.elements[(ref["external_type"], int(ref["external_id"]))]
    if kind == "bbox_centre" and crosses_antimeridian(el["bounds"]):
        lon, lat = bbox_centre(el["bounds"])
    own_km = km_to_own((lon, lat), own)
    if own_km is not None:
        if own_km > OTHER_CONTINENT_KM:
            return None
    elif not name_words(*ohm_names(el)) & name_words(p.name, (own or {}).get("label")):
        return None
    return ref, lon, lat, kind


def replacement(p: Point, wd: dict, ohm: OhmIndex) -> dict | None:
    """The entity's own point (OHM first, then P625 for point-like types), as a backfill_geo plan."""
    if not p.qid:
        return None
    own = resolved(wd, p.qid)
    own_pt = one_site(own)
    got = own_ohm_point(p, own, ohm)
    if got:
        ref, lon, lat, kind = got
        new = {"tier": OHM_TIER, "kind": kind, "lon": lon, "lat": lat, "ref": ref,
               "extid": f"{ref['external_type']}/{ref['external_id']}"}
    elif p.type in WIKIDATA_POINT_TYPES and own_pt:
        new = {"tier": WIKIDATA_TIER, "kind": "p625", "lon": own_pt[0], "lat": own_pt[1], "ref": None,
               "extid": p.qid}
    else:
        return None
    new.update({"start": p.start, "end": p.end, "years_from": "existing",
                "confidence": confidence(new["kind"], "existing"),
                "wd_km": round(km((new["lon"], new["lat"]), own_pt), 1) if own_pt else None})
    return new


def assess(p: Point, wd: dict, ohm: OhmIndex, excl: set[str], stories: set[str]) -> Verdict | None:
    org, src, prop = origin(p, wd)
    issues = find_issues(p, org, wd, ohm)
    if not issues:
        return None
    if is_excluded(p.entity_id, excl):
        return Verdict(issues, org, src, prop, "skip_excluded", "RULES.md exclusion")
    place = resolved(wd, src) if org == "borrowed" else None

    clear, reason = False, ""
    hard = [i for i in issues if not i.startswith("cluster")]
    if org in ("own_p625", "ohm_own") and not any(i.startswith(("far_from_p625", "outside_ohm", "lon_range"))
                                                  for i in issues):
        return Verdict(issues, org, src, prop, "keep", "the entity's own point")
    if "lon_range" in issues:
        clear, reason = True, "longitude outside -180..180"
    elif org == "centroid":
        clear, reason = True, "chronicle centroid: the mean of other entities' points"
    elif org == "borrowed":
        if site_like(p, prop, place) and not hard:
            return Verdict(issues, org, src, prop, "keep",
                           f"{p.group.lower()} located ({prop}) in {place.get('label') or src}: it happened there")
        what = {"P19": "birthplace", "P20": "place of death", "P276": "location", "P131": "admin area",
                "other": "work place / HQ / country of origin", "unknown": "a related place"}.get(prop, prop)
        clear, reason = True, f"borrowed from {(place or {}).get('label') or src} ({what})"
        if place and is_area(place):
            reason += ", a country/region centroid"
        elif place and is_institution(place):
            reason += ", the museum or institution that holds or hosts it"
    elif any(i.startswith("outside_ohm") for i in issues):
        clear, reason = True, "far outside the polity's own OHM feature"
    elif any(i.startswith("far_from_p625") for i in issues):
        reason = "far from its own Wikidata site"
    elif org == "derived":
        return Verdict(issues, org, src, prop, "keep", "located_at copy of a place's point (checked against the target)")
    elif org == "stale_qid":
        reason = f"P625 of {src}, a QID the entity no longer carries"
    elif any(i.startswith("far_from_wikidata") for i in issues):
        clear, reason = True, "polity on another continent from its own Wikidata coordinate"
    else:
        reason = "clustered; origin unknown"

    new = replacement(p, wd, ohm)
    if new and km((new["lon"], new["lat"]), (norm_lon(p.lon), p.lat)) <= SAME_KM and "lon_range" not in issues:
        return Verdict(issues, org, src, prop, "keep", "already at its own source")
    if new and org == "borrowed" and site_like(p, prop, place):
        # The entity's own Wikidata record says where it is (P276/P131); a P625 far from that is a
        # Wikidata contradiction (Battle of Nahavand), not a fix.
        conflict = km_to_own((new["lon"], new["lat"]), place)
        if conflict is not None and conflict > FAR_FROM_P625_KM:
            return Verdict(issues, org, src, prop, "list",
                           f"its P625 is {conflict:.0f} km from its own location ({prop}) {place.get('label')}")
    if org == "derived" and new:
        conflict = target_conflict(p, new, wd)
        if conflict:
            return Verdict(issues, org, src, prop, "list", f"{reason}; {conflict}")
    if p.kind == "location":
        if new or clear:
            return Verdict(issues, org, src, prop, "null_location",
                           reason + "; no map point, so only the admin location is cleared")
        return Verdict(issues, org, src, prop, "list", reason)
    if new:
        return Verdict(issues, org, src, prop, "replace", reason, new)
    if clear:
        if p.qid and p.qid in stories:
            return Verdict(issues, org, src, prop, "list", reason + "; used by a map story")
        return Verdict(issues, org, src, prop, "delete", reason)
    return Verdict(issues, org, src, prop, "list", reason)


def target_conflict(p: Point, new: dict | None, wd: dict) -> str | None:
    """Why a derived entity's own replacement point contradicts its located_at target, if it does.

    A QID'd place whose P625 lies far from the place it is located_at more likely carries a
    namesake's QID (West Park in Beijing holds West Park, Florida's) than a wrong link."""
    if not new:
        return None
    target = resolved(wd, p.target_qid)
    d = km_to_own((new["lon"], new["lat"]), target)
    limit = AREA_TARGET_KM if is_area(target) else FAR_FROM_P625_KM
    if d is None:
        return "its located_at target has no Wikidata coordinate to check its P625 against"
    if d > limit:
        return f"its P625 is {d:.0f} km from its located_at target {(target or {}).get('label') or p.target_qid}"
    return None


def assess_derived(p: Point, bad_points: dict[str, list[tuple[float, float]]],
                   target_points: dict[str, list[tuple[float, float]]], wd: dict, ohm: OhmIndex,
                   excl: set[str]) -> Verdict | None:
    """A located_at copy of a point this audit removes or moves, or of a point its target no
    longer has, is wrong too."""
    if p.created_by != "derive:located_at" or not p.target_id:
        return None
    if any(km(p.pt, b) <= SAME_KM for b in bad_points.get(p.target_id, [])):
        issue, reason = "derived_from_bad_point", "copy of its located_at target's point, which is wrong"
    elif not any(km(p.pt, t) <= SAME_KM for t in target_points.get(p.target_id, [])):
        issue, reason = "stale_copy", "copy of a point its located_at target no longer has"
    else:
        return None
    issues = [f"{issue}{':cluster' if p.cluster_n >= CLUSTER_MIN else ''}"]
    if is_excluded(p.entity_id, excl):
        return Verdict(issues, "derived", p.target_id, "located_at", "skip_excluded", "RULES.md exclusion")
    new = replacement(p, wd, ohm)
    conflict = target_conflict(p, new, wd)
    if conflict:
        return Verdict(issues, "derived", p.target_id, "located_at", "list", f"{reason}; {conflict}")
    if new:
        return Verdict(issues, "derived", p.target_id, "located_at", "replace", reason, new)
    return Verdict(issues, "derived", p.target_id, "located_at", "delete", reason)


def plan(points: list[Point], wd: dict, ohm: OhmIndex, excl: set[str], stories: set[str]) -> list[tuple[Point, Verdict]]:
    out: list[tuple[Point, Verdict]] = []
    bad: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for p in points:
        v = assess(p, wd, ohm, excl, stories)
        if v is None:
            continue
        out.append((p, v))
        if v.action in ("replace", "delete", "null_location"):
            bad[p.entity_id].append(p.pt)
    for p in points:
        v = assess_location_mismatch(p, bad, wd, excl)
        if v is not None:
            out.append((p, v))
            if v.action == "sync_location":
                bad[p.entity_id].append(p.loc_pt)
    # A derived copy is judged by its target, whatever the first pass said of it.
    target_points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for p in points:
        target_points[p.entity_id].append(p.pt)
        if p.loc_pt:
            target_points[p.entity_id].append(p.loc_pt)
    by_id = {(p.entity_id, p.gp_id): i for i, (p, v) in enumerate(out) if v.action != "sync_location"}
    for p in points:
        v = assess_derived(p, bad, target_points, wd, ohm, excl)
        if v is None:
            continue
        i = by_id.get((p.entity_id, p.gp_id))
        if i is None:
            out.append((p, v))
        else:
            v.issues = out[i][1].issues + v.issues
            out[i] = (p, v)
    return out


def assess_location_mismatch(p: Point, bad: dict, wd: dict, excl: set[str]) -> Verdict | None:
    """An admin location left on an old (centroid, borrowed) point after the map point was set from
    the entity's own source: backfill_geo fills a location only when its geom is NULL."""
    if (p.kind != "period" or p.loc_pt is None or p.loc_method == "human_assigned" or p.entity_id in bad
            or p.created_by == "derive:located_at"):
        return None
    gap = km(p.loc_pt, p.pt)
    if gap <= LOCATION_GAP_KM:
        return None
    org = origin(p, wd)[0]
    if org not in ("own_p625", "ohm_own"):
        return None
    loc_own = km_to_own(p.loc_pt, resolved(wd, p.qid))
    if loc_own is not None and loc_own <= SAME_KM:
        return None  # two own sources (OHM and P625) that differ a little; both stand
    issues = [f"location_differs:{gap:.0f}km"]
    if is_excluded(p.entity_id, excl):
        return Verdict(issues, org, None, None, "skip_excluded", "RULES.md exclusion")
    new = {"tier": "mirror", "kind": "location", "extid": p.gp_id, "lon": p.lon, "lat": p.lat}
    return Verdict(issues, org, None, None, "sync_location",
                   f"admin location {gap:.0f} km from the map point, which is the entity's own", new)


# ── output ──────────────────────────────────────────────────────────────────
PLAN_FIELDS = ["entity_id", "name", "type", "qid", "row", "geometry_period_id", "created_by", "lon", "lat",
               "cluster_n", "origin", "source_qid", "source_label", "prop", "issues", "action", "reason",
               "new_tier", "new_kind", "new_source", "new_lon", "new_lat", "moved_km"]


def plan_row(p: Point, v: Verdict, wd: dict) -> dict:
    src = resolved(wd, v.source_qid) if v.source_qid and v.source_qid.startswith("Q") else None
    lon, lat = p.loc_pt if v.action == "sync_location" else p.pt
    row = {"entity_id": p.entity_id, "name": p.name, "type": p.type, "qid": p.qid or "",
           "row": "location" if v.action == "sync_location" else p.kind,
           "geometry_period_id": p.gp_id or "", "created_by": p.created_by, "lon": f"{lon:.5f}",
           "lat": f"{lat:.5f}", "cluster_n": p.cluster_n, "origin": v.origin, "source_qid": v.source_qid or "",
           "source_label": (src or {}).get("label", ""), "prop": v.prop or "", "issues": " ".join(v.issues),
           "action": v.action, "reason": v.reason}
    if v.new:
        row.update({"new_tier": v.new["tier"], "new_kind": v.new["kind"], "new_source": v.new["extid"],
                    "new_lon": f"{v.new['lon']:.5f}", "new_lat": f"{v.new['lat']:.5f}",
                    "moved_km": f"{km((v.new['lon'], v.new['lat']), (norm_lon(lon), lat)):.0f}"})
    return row


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ── apply ───────────────────────────────────────────────────────────────────
PERIOD_COLS = ["geometry_period_id", "entity_id", "period_type", "start_year", "end_year", "geom",
               "territory_geom", "description", "provenance_mode", "relationship_id", "source_event_id",
               "created_by", "created_at", "updated_at", "confidence"]
REF_COLS = ["geo_ref_id", "entity_id", "external_id", "temporal_start", "temporal_end", "temporal_start_year",
            "temporal_end_year", "external_tags", "source_meta", "match_score", "is_active", "created_at",
            "updated_at", "provider", "external_type", "match_role", "retrieval_method", "geometry_period_id"]
LOC_COLS = ["location_id", "entity_id", "location_name", "geom", "territory_geom", "location_method",
            "location_confidence", "is_primary", "notes", "created_at", "updated_at"]
GEOM_COLS = {"geom", "territory_geom"}
JSON_COLS = {"external_tags", "source_meta"}


def _select(table: str, cols: list[str], where: str) -> str:
    exprs = [f"encode(ST_AsEWKB({c}), 'hex')" if c in GEOM_COLS else f"{c}::text" for c in cols]
    return f"SELECT {', '.join(exprs)} FROM {table} WHERE {where}"


def snapshot(cur, eid: str) -> dict:
    """Every row an entity's point lives in, as text (geometry as EWKB hex)."""
    snap: dict[str, Any] = {}
    for name, table, cols, where in (
            ("periods", "geometry_periods", PERIOD_COLS, "entity_id = %s"),
            ("refs", "entity_geo_refs", REF_COLS, "entity_id = %s"),
            ("locations", "entity_locations", LOC_COLS, "entity_id = %s AND is_primary")):
        cur.execute(_select(table, cols, where), (eid,))
        snap[name] = {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    cur.execute("SELECT primary_geo_ref_id::text FROM entities WHERE entity_id = %s", (eid,))
    snap["primary_geo_ref_id"] = cur.fetchone()[0]
    return snap


def lit(col: str, v: Any) -> str:
    if v is None:
        return "NULL"
    if col in GEOM_COLS:
        return f"'{v}'::geometry"
    s = "'" + str(v).replace("'", "''") + "'"
    return s + "::jsonb" if col in JSON_COLS else s


def rollback_sql(eid: str, before: dict, after: dict) -> list[str]:
    """Guarded inverse of one entity's change, ordered so no FK cascade fires."""
    out: list[str] = [f"-- {eid}"]
    # 1. Re-create removed periods with their original ids.
    for pid, row in before["periods"].items():
        if pid not in after["periods"]:
            out.append(f"INSERT INTO geometry_periods ({', '.join(PERIOD_COLS)}) VALUES "
                       f"({', '.join(lit(c, row[c]) for c in PERIOD_COLS)}) ON CONFLICT DO NOTHING;")
    # 2. Refs back to how they were (period link, provenance).
    for rid, row in before["refs"].items():
        now = after["refs"].get(rid)
        if now is None:
            out.append(f"INSERT INTO entity_geo_refs ({', '.join(REF_COLS)}) VALUES "
                       f"({', '.join(lit(c, row[c]) for c in REF_COLS)}) ON CONFLICT DO NOTHING;")
            continue
        changed = [c for c in REF_COLS if row[c] != now[c]]
        if changed:
            sets = ", ".join(f"{c} = {lit(c, row[c])}" for c in changed)
            out.append(f"UPDATE entity_geo_refs SET {sets} WHERE geo_ref_id = '{rid}' AND "
                       f"geometry_period_id IS NOT DISTINCT FROM {lit('geometry_period_id', now['geometry_period_id'])};")
    # 3. The entity's primary ref, before a ref it may point at is removed.
    if before["primary_geo_ref_id"] != after["primary_geo_ref_id"]:
        out.append(f"UPDATE entities SET primary_geo_ref_id = {lit('', before['primary_geo_ref_id'])} "
                   f"WHERE entity_id = '{eid}' AND primary_geo_ref_id IS NOT DISTINCT FROM "
                   f"{lit('', after['primary_geo_ref_id'])};")
    # 4. Refs and periods this run added.
    for rid, now in after["refs"].items():
        if rid not in before["refs"]:
            out.append(f"DELETE FROM entity_geo_refs WHERE geo_ref_id = '{rid}' AND geometry_period_id "
                       f"IS NOT DISTINCT FROM {lit('geometry_period_id', now['geometry_period_id'])};")
    for pid, now in after["periods"].items():
        if pid not in before["periods"]:
            out.append(f"DELETE FROM geometry_periods WHERE geometry_period_id = '{pid}' AND geom = "
                       f"{lit('geom', now['geom'])};")
    # 5. The admin location.
    for lid, row in before["locations"].items():
        now = after["locations"].get(lid)
        if now is None:
            out.append(f"INSERT INTO entity_locations ({', '.join(LOC_COLS)}) VALUES "
                       f"({', '.join(lit(c, row[c]) for c in LOC_COLS)}) ON CONFLICT DO NOTHING;")
            continue
        changed = [c for c in LOC_COLS if row[c] != now[c]]
        if changed:
            sets = ", ".join(f"{c} = {lit(c, row[c])}" for c in changed)
            out.append(f"UPDATE entity_locations SET {sets} WHERE location_id = '{lid}' AND "
                       f"geom IS NOT DISTINCT FROM {lit('geom', now['geom'])};")
    for lid, now in after["locations"].items():
        if lid not in before["locations"]:
            out.append(f"DELETE FROM entity_locations WHERE location_id = '{lid}' AND "
                       f"geom IS NOT DISTINCT FROM {lit('geom', now['geom'])};")
    return out


class Changed(Exception):
    """A row changed since it was read; the entity is skipped."""


def apply_one(cur, p: Point, v: Verdict) -> None:
    pt_sql = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)"
    if v.action == "sync_location":
        # LocationResolutionMethod values, as backfill_geo.apply_plan writes them.
        method = "ohm_nominatim" if p.created_by == OHM_TIER else "wikidata"
        cur.execute(f"""
            UPDATE entity_locations SET geom = {pt_sql}, location_method = %s, updated_at = now()
            WHERE location_id = %s AND is_primary AND ST_DWithin(geom, {pt_sql}, 1e-7)
              AND EXISTS (SELECT 1 FROM geometry_periods WHERE geometry_period_id = %s
                          AND ST_DWithin(geom, {pt_sql}, 1e-7))""",
                    (p.lon, p.lat, method, p.loc_id, *p.loc_pt, p.gp_id, p.lon, p.lat))
        if cur.rowcount != 1:
            raise Changed("location or period changed")
        return
    if p.kind == "location":
        cur.execute(f"UPDATE entity_locations SET geom = NULL, updated_at = now() "
                    f"WHERE location_id = %s AND is_primary AND ST_DWithin(geom, {pt_sql}, 1e-7)",
                    (p.loc_id, p.lon, p.lat))
        if cur.rowcount != 1:
            raise Changed("location moved")
        cur.execute("SELECT 1 FROM geometry_periods WHERE entity_id = %s LIMIT 1", (p.entity_id,))
        if cur.fetchone():
            raise Changed("gained a map point")
        return

    # Unlink refs tied to the period first: the FK would cascade-delete them.
    cur.execute("""
        SELECT 1 FROM entity_geo_refs t JOIN entity_geo_refs o
          ON o.entity_id = t.entity_id AND o.provider = t.provider AND o.external_type = t.external_type
         AND o.external_id = t.external_id AND o.geometry_period_id IS NULL
        WHERE t.geometry_period_id = %s LIMIT 1""", (p.gp_id,))
    if cur.fetchone():
        raise Changed("an untied twin of a tied ref exists")
    cur.execute("UPDATE entity_geo_refs SET geometry_period_id = NULL, updated_at = now() "
                "WHERE geometry_period_id = %s", (p.gp_id,))
    cur.execute(f"DELETE FROM geometry_periods WHERE geometry_period_id = %s AND entity_id = %s "
                f"AND ST_DWithin(geom, {pt_sql}, 1e-7)", (p.gp_id, p.entity_id, p.lon, p.lat))
    if cur.rowcount != 1:
        raise Changed("period changed")
    # The admin location goes with the map point when it sits on the same spot (never a human's).
    cur.execute(f"UPDATE entity_locations SET geom = NULL, updated_at = now() "
                f"WHERE entity_id = %s AND is_primary AND territory_geom IS NULL "
                f"AND location_method IS DISTINCT FROM 'human_assigned' "
                f"AND ST_DWithin(geom::geography, {pt_sql}::geography, %s)",
                (p.entity_id, norm_lon(p.lon), p.lat, SAME_KM * 1000))
    if v.action == "delete":
        return
    cur.execute("SELECT 1 FROM geometry_periods WHERE entity_id = %s LIMIT 1", (p.entity_id,))
    if cur.fetchone():
        raise Changed("entity has another period")
    new = dict(v.new)
    if new["start"] is None:
        raise Changed("period without a start year")
    row = {"name": p.name, "primary_geo_ref_id": p.primary_geo_ref_id, "has_wikidata_point": False}
    apply_plan(cur, {p.entity_id: new}, {p.entity_id: row})
    if new["tier"] == WIKIDATA_TIER:
        # A reused ref of the entity's own QID may still say it was a chronicle centroid.
        cur.execute("""
            UPDATE entity_geo_refs
            SET source_meta = coalesce(source_meta, '{}'::jsonb)
                    || jsonb_build_object('source', 'wikidata_p625', 'replaced_source', source_meta->>'source'),
                match_score = 0.90, updated_at = now()
            WHERE entity_id = %s AND provider = 'wikidata' AND external_id = %s
              AND geometry_period_id IS NOT NULL
              AND coalesce(source_meta->>'source', '') <> 'wikidata_p625'""", (p.entity_id, p.qid))


def pg_dump(out: Path, tables: list[str]) -> None:
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
           *[a for t in tables for a in ("-t", t)], "history-mapped"]
    with out.open("wb") as fh:
        subprocess.run(cmd, stdout=fh, check=True)


def apply_all(conn, todo: list[tuple[Point, Verdict]], out_dir: Path, wd: dict) -> list[dict]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dump = out_dir / f"pre-apply-{stamp}.dump"
    print(f"Backing up geometry_periods, entity_locations, entity_geo_refs, entities -> {dump}")
    pg_dump(dump, ["geometry_periods", "entity_locations", "entity_geo_refs", "entities"])
    cur = conn.cursor()
    applied: list[dict] = []
    rollback: list[str] = [
        "-- Rollback for pipeline/audit_points.py --apply: guarded inverses, per entity.",
        "-- Afterwards re-project the same entities' timelines (ProjectEntityTimelineAction::rebuildForEntity).",
        "BEGIN;"]
    before_rows: list[dict] = []
    by_entity: dict[str, list[tuple[Point, Verdict]]] = defaultdict(list)
    for p, v in todo:
        by_entity[p.entity_id].append((p, v))
    for i, (eid, items) in enumerate(by_entity.items()):
        cur.execute("SAVEPOINT pt")
        before = snapshot(cur, eid)
        try:
            for p, v in items:
                apply_one(cur, p, v)
        except Changed as exc:
            cur.execute("ROLLBACK TO SAVEPOINT pt")
            for p, v in items:
                applied.append({**plan_row(p, v, wd), "result": f"skipped: {exc}"})
            continue
        after = snapshot(cur, eid)
        cur.execute("RELEASE SAVEPOINT pt")
        rollback.extend(rollback_sql(eid, before, after))
        before_rows.append({"entity_id": eid, "before": before, "after": after})
        new_ids = [pid for pid in after["periods"] if pid not in before["periods"]]
        for p, v in items:
            applied.append({**plan_row(p, v, wd), "result": "applied", "new_geometry_period_id": " ".join(new_ids)})
        if (i + 1) % 1000 == 0:
            print(f"   {i + 1}/{len(by_entity)} entities", flush=True)
    rollback.append("COMMIT;")
    conn.commit()
    (out_dir / "rollback.sql").write_text("\n".join(rollback) + "\n", encoding="utf-8")
    with (out_dir / f"rows-before-after-{stamp}.jsonl").open("w", encoding="utf-8") as fh:
        for rec in before_rows:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return applied


def check_rollback(out_dir: Path, applied: list[dict]) -> str:
    """Run rollback.sql inside a transaction that is rolled back; check the old periods return."""
    sql = (out_dir / "rollback.sql").read_text(encoding="utf-8")
    sql = sql.replace("\nCOMMIT;\n", "\n")
    old = [r["geometry_period_id"] for r in applied
           if r["result"] == "applied" and r["action"] in ("replace", "delete")]
    new = [x for r in applied if r["result"] == "applied" for x in r.get("new_geometry_period_id", "").split()]
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        cur.execute(sql.replace("BEGIN;", "", 1))
        cur.execute("SELECT count(*) FROM geometry_periods WHERE geometry_period_id = ANY(%s::uuid[])", (old,))
        back = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM geometry_periods WHERE geometry_period_id = ANY(%s::uuid[])", (new,))
        left = cur.fetchone()[0]
        conn.rollback()
    return f"rollback test: {back}/{len(old)} old periods restored, {left}/{len(new)} new periods left (rolled back)"


def rebuild_timelines(entity_ids: list[str]) -> str:
    """Re-project each touched entity's timeline (it copies the period geometry), one PHP process."""
    php = ("$a = app(App\\Actions\\Timeline\\ProjectEntityTimelineAction::class); $n = 0; "
           "foreach (array_filter(array_map('trim', file('php://stdin'))) as $id) "
           "{ $a->rebuildForEntity($id); $n++; } echo \"rebuilt $n entity timelines\", PHP_EOL;")
    r = subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", "tinker", f"--execute={php}"],
                       input="\n".join(entity_ids) + "\n", text=True, capture_output=True, check=True)
    return (r.stdout.strip().splitlines() or ["(no output)"])[-1]


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the planned changes (default: dry run)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--offline", action="store_true", help="Wikidata from the cache only")
    ap.add_argument("--no-ohm", action="store_true", help="skip the OHM fetch (scope 3 and OHM replacements off)")
    ap.add_argument("--sample", type=int, default=30, help="planned changes printed for a spot-check")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    points = load_points(cur)
    print(f"{len(points)} points ({sum(p.kind == 'period' for p in points)} map, "
          f"{sum(p.kind == 'location' for p in points)} admin-only)")

    qids = ({p.qid for p in points if p.qid} | {p.target_qid for p in points if p.target_qid}
            | {r["external_id"] for p in points for r in p.wd_refs})
    print(f"Wikidata: {len(qids)} items", flush=True)
    wd = fetch_geo(qids, args.out_dir / "cache", offline=args.offline)

    ohm = OhmIndex({}, {}, {})
    if not args.no_ohm:
        with_qid = sorted({uuid.UUID(p.entity_id) for p in points if p.qid})
        refs = load_ohm_refs(cur, with_qid)
        all_refs = [r for rs in refs.values() for r in rs]
        print(f"OHM: {len(all_refs)} features for {len(refs)} entities", flush=True)
        elements, nodes = load_ohm_cache(args.out_dir / "cache" / "ohm.json", all_refs, args.offline)
        ohm = OhmIndex(refs, elements, nodes)

    planned = plan(points, wd, ohm, excluded_ids(), story_qids())
    rows = [plan_row(p, v, wd) for p, v in planned]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "planned.csv", rows, PLAN_FIELDS)

    print("\nActions:")
    for (action, org), n in sorted(Counter((v.action, v.origin) for _, v in planned).items()):
        print(f"   {action:14s} {org:10s} {n}")
    todo = [(p, v) for p, v in planned if v.action in ("replace", "delete", "null_location", "sync_location")]
    print(f"Changes: {len(todo)} ({Counter(v.action for _, v in todo)})  plan: {args.out_dir / 'planned.csv'}")
    rnd = random.Random(20261101)
    for p, v in rnd.sample(todo, min(args.sample, len(todo))):
        r = plan_row(p, v, wd)
        print(f" - {r['action']:13s} {p.name[:40]:40s} {p.type:22s} {p.qid or '-':11s} "
              f"({r['lon']},{r['lat']}) {v.origin}/{v.prop or ''} {r['source_label'][:20]} -> "
              f"{(r.get('new_lon', '') + ',' + r.get('new_lat', '')) if v.new else ''}  [{r['issues']}] {v.reason[:60]}")

    if args.apply:
        applied = apply_all(conn, todo, args.out_dir, wd)
        write_csv(args.out_dir / "applied.csv", applied, PLAN_FIELDS + ["result", "new_geometry_period_id"])
        print(Counter(r["result"].split(":")[0] for r in applied))
        print(check_rollback(args.out_dir, applied))
        touched = sorted({r["entity_id"] for r in applied if r["result"] == "applied"})
        print(rebuild_timelines(touched))
    else:
        print("\nDry run: re-run with --apply to write.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
