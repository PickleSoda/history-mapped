#!/usr/bin/env python3
"""OHM ref audit: judge the OHM links that were made by name only.

The geo backfill (pipeline/backfill_geo.py) accepts an OHM feature only when its
`wikidata` tag is the entity's QID. The refs it rejects with ohm:qid_mismatch
are old name-only matches (Nominatim), and many are wrong: "Poland" is a node in
North Dakota. Wrong refs feed more than map points: the tiles' ohm_osm_id, the
SPA's OHM highlight and click resolver, map-story outlines, and whether the map
serves an entity's point or its polygon (MapEntitiesAction).

The set is recomputed with backfill_geo's own functions (load_state,
load_ohm_refs, fetch_ohm, pick_ohm): every active OHM ref of an entity with a
QID and no map point whose feature fails the QID check (scope `unplaced`), plus
the name-only (Nominatim) refs of placed entities that fail it (scope `placed`).
Each ref gets a verdict:

  WRONG   the feature carries another item's `wikidata` tag (not a redirect of
          the entity's QID); or it is untagged and clearly another thing: none
          of its names (name, name:*, official/alt/old names) matches a name of
          the entity (its name, its aliases bar the one the link was made by,
          its Wikidata label and aliases) or it only adds a word of another kind
          ('Ganja River'); it is a river, road or railway; it lies more than
          50 km from the entity's own P625 (point-like types) or 1,000 km from a
          polity's capital and P625; or its OHM dates miss the entity's.
  OK      untagged, a name matches exactly, and a point-like entity's P625 is
          within 10 km, or a polity's dates overlap and its capital or P625
          falls in the feature's bbox.
  UNSURE  anything else, and WRONG evidence that may come from a wrong entity QID
          (the QID lacks the entity's name, or its dates contradict the entity
          where the feature agrees), another item sharing the entity's name at
          its place, or the same place in another era. Listed, never acted on.

Dry run by default: writes verdicts.csv. --apply deactivates the WRONG refs that
carry no geometry period (is_active=false, source_meta.deactivated_by and a
reason), each write guarded on the values read, in one transaction, after a
pg_dump of entity_geo_refs and with rollback.sql written first. A deactivated
ref that was an entity's primary_geo_ref_id is replaced by the entity's best
remaining active ref, else NULL.

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit_ohm_refs           # dry run
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit_ohm_refs --apply   # write
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline import backfill_geo as bg
from pipeline.agent.tools.disambiguation import _name_tokens, names_compatible, names_equal
from pipeline.audit.dates import wd_bounds
from pipeline.audit.wd import SPARQL, WikidataClient

TAG = "ohm_ref_audit_20261101"
OUT_DIR = _REPO_ROOT / "output" / "audit" / "ohm-refs-20261101"
COMPOSE = ["docker", "compose", "-f", str(_REPO_ROOT / "docker" / "docker-compose.yml")]

POLITY_TYPES = frozenset({"political_entity"})
OK_KM = 10            # an untagged point this close to the entity's own P625 is the same place
WRONG_KM = bg.MAX_DISAGREE_KM   # 50: further than this it is another place
POLITY_FAR_KM = 1000  # a polity's feature this far from both its capital and its P625
DATE_SLACK = 10       # years: OHM dates are often a mapper's round guess
OVERPASS_PAUSE = 2.0  # seconds between live Overpass requests

# OHM name keys that name the feature itself (not its etymology, source or note).
_NAME_KEY = re.compile(r"^(name|official_name|alt_name|old_name|short_name|int_name|loc_name|"
                       r"historic_name|long_name|reg_name|nat_name)(:[a-z]{2,3}(-[A-Za-z]+)?)?$")
_YEAR = re.compile(r"^\s*~?\s*(-?)0*(\d{1,4})")


# ── Overpass, cached per element ─────────────────────────────────────────────
class CachedOverpass:
    """Stands in for backfill_geo.overpass: answers `{kw}(id:...);{out}` queries
    from a per-element cache and asks OHM only for the ids it has never seen
    (a deleted feature is cached as missing). fetch_ohm's batching is kept."""

    _Q = re.compile(r"^\[out:json\]\[timeout:\d+\];(node|way|rel)\(id:([\d,]+)\);(.+)$")

    def __init__(self, cache_dir: Path, live=None, pause: float = OVERPASS_PAUSE):
        self.path = cache_dir / "ohm-elements.jsonl"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.live = live or bg.overpass
        self.pause = pause
        self.requests = 0
        self.cache: dict[str, dict | None] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a line cut short by an interrupted run
                self.cache[rec["k"]] = rec["el"]

    def __call__(self, query: str) -> list[dict]:
        m = self._Q.match(query)
        if not m:
            return self.live(query)
        kw, ids, out = m.group(1), [int(x) for x in m.group(2).split(",")], m.group(3)
        key = lambda i: f"{kw}/{i}/{out}"  # noqa: E731
        todo = [i for i in ids if key(i) not in self.cache]
        if todo:
            if self.requests:
                time.sleep(self.pause)
            got = {el["id"]: el for el in self.live(f"[out:json][timeout:240];{kw}(id:{','.join(map(str, todo))});{out}")}
            self.requests += 1
            with self.path.open("a", encoding="utf-8") as fh:
                for i in todo:
                    self.cache[key(i)] = got.get(i)
                    fh.write(json.dumps({"k": key(i), "el": got.get(i)}, ensure_ascii=False) + "\n")
        return [self.cache[key(i)] for i in ids if self.cache[key(i)] is not None]


def fetch_cached(refs: list[dict], cache_dir: Path) -> tuple[dict, dict, int]:
    """backfill_geo.fetch_ohm through the per-element cache: (elements, nodes, live requests)."""
    cached = CachedOverpass(cache_dir)
    original, bg.overpass = bg.overpass, cached
    try:
        elements, nodes = bg.fetch_ohm(refs)
    finally:
        bg.overpass = original
    return elements, nodes, cached.requests


# ── the audit set ────────────────────────────────────────────────────────────
_REF_EXTRA = """
    SELECT r.geo_ref_id, r.retrieval_method::text AS retrieval_method, r.geometry_period_id,
           r.source_meta, r.updated_at, r.external_tags->>'name' AS stored_name,
           r.source_meta->>'display_name' AS display_name
    FROM entity_geo_refs r WHERE r.geo_ref_id = ANY(%s)
"""


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_audit_set(cur) -> tuple[dict[str, dict], list[dict]]:
    """Entities (by id) and their active OHM refs to judge, each ref tagged with its scope.

    `unplaced`: every active OHM ref of an entity with a QID and no map point
    (backfill_geo.load_state + load_ohm_refs, exactly the backfill's input).
    `placed`: the name-only (Nominatim) refs of the other entities with a QID.
    The QID check itself needs the live feature, so it happens after the fetch."""
    no_point, _ = bg.load_state(cur)
    entities: dict[str, dict] = {}
    for r in no_point:
        if r["wikidata_id"]:
            entities.setdefault(str(r["entity_id"]), {**r, "scope": "unplaced"})
    refs_by_entity = bg.load_ohm_refs(cur, list(entities))

    cur.execute("""
        SELECT DISTINCT ON (e.entity_id) e.entity_id, e.name, e.entity_type::text AS entity_type, e.wikidata_id,
               t.start_year, t.end_year, e.primary_geo_ref_id
        FROM entities e
        JOIN entity_geo_refs r ON r.entity_id = e.entity_id AND r.provider = 'ohm' AND r.is_active
                              AND r.retrieval_method = 'nominatim'
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        WHERE e.wikidata_id IS NOT NULL AND e.wikidata_id <> '' AND NOT (e.entity_id::text = ANY(%s))
        ORDER BY e.entity_id, t.is_primary DESC NULLS LAST
    """, (list(entities),))
    placed = {str(r["entity_id"]): {**r, "scope": "placed"} for r in _rows(cur)}
    placed_refs = bg.load_ohm_refs(cur, list(placed))
    entities.update(placed)

    refs = [{**ref, "entity_id": str(ref["entity_id"]), "geo_ref_id": str(ref["geo_ref_id"])}
            for refs in (refs_by_entity, placed_refs) for rs in refs.values() for ref in rs]
    cur.execute(_REF_EXTRA, ([r["geo_ref_id"] for r in refs],))
    extra = {str(x["geo_ref_id"]): x for x in _rows(cur)}
    out = []
    for ref in refs:
        x = extra[ref["geo_ref_id"]]
        scope = entities[ref["entity_id"]]["scope"]
        if scope == "placed" and x["retrieval_method"] != "nominatim":
            continue  # a placed entity's Overpass refs were matched by QID
        out.append({**ref, **x, "geo_ref_id": ref["geo_ref_id"], "scope": scope,
                    "geometry_period_id": str(x["geometry_period_id"]) if x["geometry_period_id"] else None})
    return entities, out


def fails_qid_check(entity: dict, ref: dict, elements: dict, nodes: dict) -> str:
    """backfill_geo.pick_ohm on this one ref: '' when the feature passes the
    QID-tag rule, else the backfill's reason (ohm:qid_mismatch / ohm:not_in_ohm)."""
    pick, reason = bg.pick_ohm(entity, [ref], elements, nodes, None)
    if pick is not None or reason == "ohm:sprawling_relation":
        return ""
    return reason


def load_entity_context(cur, entity_ids: list[str]) -> dict[str, dict]:
    """Per entity: aliases, map-point state, other active refs, polygon periods."""
    ctx: dict[str, dict] = {e: {"aliases": [], "active_refs": [], "polygon_periods": 0, "point_periods": 0}
                            for e in entity_ids}
    cur.execute("SELECT entity_id::text, name FROM entity_aliases WHERE entity_id::text = ANY(%s)", (entity_ids,))
    for eid, name in cur.fetchall():
        ctx[eid]["aliases"].append(name)
    cur.execute("""
        SELECT entity_id::text,
               COUNT(*) FILTER (WHERE territory_geom IS NOT NULL OR GeometryType(geom) NOT IN ('POINT', 'MULTIPOINT')),
               COUNT(*) FILTER (WHERE GeometryType(geom) IN ('POINT', 'MULTIPOINT'))
        FROM geometry_periods WHERE entity_id::text = ANY(%s) GROUP BY 1
    """, (entity_ids,))
    for eid, poly, pts in cur.fetchall():
        ctx[eid]["polygon_periods"], ctx[eid]["point_periods"] = poly, pts
    cur.execute("""
        SELECT entity_id::text, geo_ref_id::text, provider::text, external_type::text, external_id,
               match_role::text, retrieval_method::text, geometry_period_id::text, external_tags->>'wikidata'
        FROM entity_geo_refs WHERE is_active AND entity_id::text = ANY(%s)
    """, (entity_ids,))
    for eid, *rest in cur.fetchall():
        ctx[eid]["active_refs"].append(dict(zip(
            ("geo_ref_id", "provider", "external_type", "external_id", "match_role", "retrieval_method",
             "geometry_period_id", "tag_qid"), rest)))
    return ctx


def load_periods(cur, period_ids: list[str]) -> dict[str, dict]:
    """What a ref's geometry period holds: type, provenance, geometry kind, years."""
    if not period_ids:
        return {}
    cur.execute("""
        SELECT geometry_period_id::text, period_type, provenance_mode, created_by, start_year, end_year,
               GeometryType(geom) AS geom_type, territory_geom IS NOT NULL AS has_territory,
               (SELECT COUNT(*) FROM geometry_periods o WHERE o.entity_id = gp.entity_id) AS entity_periods
        FROM geometry_periods gp WHERE geometry_period_id::text = ANY(%s)
    """, (period_ids,))
    return {r["geometry_period_id"]: r for r in _rows(cur)}


# ── Wikidata: names, redirects, P625 and capitals ────────────────────────────
def _coords(literal: str) -> tuple[float, float] | None:
    """(lon, lat) of a WDQS 'Point(lon lat)' on Earth (other globes start with '<')."""
    if not literal or not literal.startswith("Point("):
        return None
    try:
        return bg.parse_pt(literal)
    except (ValueError, IndexError):
        return None


def wd_geo(client: WikidataClient, qids: list[str], cache_dir: Path, batch: int = 150) -> dict[str, dict]:
    """{qid: {"p625": [(lon, lat)...], "capitals": [(lon, lat)...]}} from the query
    service through wd.py's rate-limited client, cached per QID."""
    path = cache_dir / "wd-geo.jsonl"
    cache: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cache[rec["qid"]] = rec
    todo = sorted({q for q in qids if q and q not in cache})
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        query = ("SELECT ?item ?coord ?capcoord WHERE { VALUES ?item { " + " ".join(f"wd:{q}" for q in chunk)
                 + " } OPTIONAL { ?item wdt:P625 ?coord } "
                 + "OPTIONAL { ?item p:P36/ps:P36 ?cap . ?cap wdt:P625 ?capcoord } }")
        rows = client._get(SPARQL, {"query": query, "format": "json"}, timeout=120).json()["results"]["bindings"]
        got = {q: {"qid": q, "p625": [], "capitals": []} for q in chunk}
        for b in rows:
            q = b["item"]["value"].rsplit("/", 1)[-1]
            for key, field in (("coord", "p625"), ("capcoord", "capitals")):
                pt = _coords(b.get(key, {}).get("value", ""))
                if q in got and pt and list(pt) not in got[q][field]:
                    got[q][field].append(list(pt))
        with path.open("a", encoding="utf-8") as fh:
            for rec in got.values():
                fh.write(json.dumps(rec) + "\n")
        cache.update(got)
        print(f"   Wikidata P625/P36 {min(i + batch, len(todo))}/{len(todo)}", flush=True)
    return {q: {"p625": [tuple(p) for p in cache[q]["p625"]], "capitals": [tuple(p) for p in cache[q]["capitals"]]}
            for q in qids if q in cache}


# ── judging one ref ──────────────────────────────────────────────────────────
def ohm_names(tags: dict) -> list[str]:
    """The feature's own names: name, name:*, official/alt/old/short names (';' splits)."""
    out: list[str] = []
    for key in sorted(tags, key=lambda k: (k != "name", k)):
        if _NAME_KEY.match(key):
            for part in str(tags[key]).split(";"):
                part = part.strip()
                if part and part not in out:
                    out.append(part)
    return out


def tag_qids(tags: dict) -> list[str]:
    return [q.strip() for q in str(tags.get("wikidata") or "").split(";") if q.strip()]


def ohm_year(value: Any) -> int | None:
    """Year of an OHM date tag: '1871', '1871-01-18', '-0480', '~1200'; None otherwise."""
    m = _YEAR.match(str(value or ""))
    if not m:
        return None
    return int(m.group(2)) * (-1 if m.group(1) == "-" else 1)


def year_gap(entity: dict, tags: dict) -> int | None:
    """Years between the entity's span and the feature's (0 = overlap); None when
    either side is undated or the feature's dates are inverted. An open end is
    open; an event without an end year is a point."""
    e_start, e_end = entity.get("start_year"), entity.get("end_year")
    if e_start is None and e_end is None:
        return None
    if e_end is None and str(entity.get("entity_type", "")).startswith("event_"):
        e_end = e_start
    o_start, o_end = ohm_year(tags.get("start_date")), ohm_year(tags.get("end_date"))
    if (o_start is None and o_end is None) or (o_start is not None and o_end is not None and o_start > o_end):
        return None
    inf = float("inf")
    lo = max(e_start if e_start is not None else -inf, o_start if o_start is not None else -inf)
    hi = min(e_end if e_end is not None else inf, o_end if o_end is not None else inf)
    return int(max(0, lo - hi))


def feature_bbox(el: dict) -> tuple[float, float, float, float] | None:
    """(minlon, minlat, maxlon, maxlat): a relation's bounds, a node's or way centre's point."""
    if el["type"] == "node":
        return el["lon"], el["lat"], el["lon"], el["lat"]
    if el["type"] == "way":
        c = el.get("center")
        return (c["lon"], c["lat"], c["lon"], c["lat"]) if c else None
    b = el.get("bounds")
    return (b["minlon"], b["minlat"], b["maxlon"], b["maxlat"]) if b else None


def bbox_km(bbox: tuple[float, float, float, float], pt: tuple[float, float]) -> float:
    """Distance from a point to a bbox (0 inside)."""
    lon = min(max(pt[0], bbox[0]), bbox[2])
    lat = min(max(pt[1], bbox[1]), bbox[3])
    return bg.km((lon, lat), pt)


# Words that qualify a name without making it another thing ('Town of Johnstown',
# 'Sigtuna stad', 'Old Kaskaskia').
_GENERIC = frozenset({"city", "town", "township", "village", "municipality", "borough", "commune", "stad", "stadt",
                      "ville", "ciudad", "citta", "cidade", "old", "of", "the", "de", "di", "da", "du", "del",
                      "dei", "della", "la", "le", "el", "al"})
# Words that make an extended name another kind of thing ('Ganja River', 'Kisumu–Kakamega
# Road', 'Howard University Hospital', 'Pulau Kasi').
_OTHER_KIND = frozenset({
    "river", "rio", "fiume", "riviere", "fluss", "cayi", "jogi", "wenz", "kill", "creek", "brook", "abhainn",
    "krueng", "rivera", "canal", "basin", "bay", "gulf", "lake", "island", "isla", "pulau", "rock", "point",
    "road", "street", "rue", "rua", "via", "highway", "avenue", "lane", "drive", "row", "parade", "bridge",
    "airport", "station", "hospital", "clinic", "museum", "bunker", "park", "memorial", "camp", "warehouse",
    "headquarters", "center", "centre", "pavilion", "store", "chapel", "cathedral", "cattedrale", "campus",
    "delegation", "consulate", "stones", "gleisbauhof", "rastplatz", "kruithuis", "civic", "veterans"})
# For anything but a polity, a polity or admin unit named after it is another thing too
# ('Nghe An Province' for a city, 'Omagh Rural District').
_UNIT_KIND = frozenset({"kingdom", "empire", "khanate", "sultanate", "emirate", "duchy", "principality",
                        "republic", "province", "provincia", "district", "prefecture", "department", "region",
                        "governorate", "oblast", "county", "canton", "tribes"})


# A river, road or railway is another thing for anything that isn't itself one
# (the Prüm river for the town of Prüm).
_LINEAR_KEYS = ("waterway", "highway", "railway")
_LINEAR_TYPES = frozenset({"infrastructure_monument", "extraction_infra", "trade_route", "natural_resource"})


def name_match(entity_names: list[str], feature_names: list[str], *, polity: bool = False) -> str:
    """How the feature's names relate to the entity's.

    'exact'    some pair is the same name after normalising case, accents, punctuation;
    'partial'  some pair is compatible (a whole-word run of the other, regnal markers
               equal) and the feature's name adds only generic words: 'La Rochelle'
               for 'Siege of La Rochelle', 'Town of Johnstown' for 'Johnstown';
    'extended' the feature's name adds words of its own, none of another kind of
               thing: 'Free Imperial City of Augsburg', 'New York Stock Exchange Building';
    'none'     no compatible pair, or each adds a word of another kind ('Ganja River');
    'unnamed'  the feature has no name."""
    if not feature_names:
        return "unnamed"
    entity_names = [n for n in entity_names if n and n.strip()]
    if any(names_equal(a, b) for a in entity_names for b in feature_names):
        return "exact"
    other = _OTHER_KIND if polity else _OTHER_KIND | _UNIT_KIND
    best = "none"
    for a in entity_names:
        ta = set(_name_tokens(a))
        for b in feature_names:
            if not names_compatible(a, b):
                continue
            extra = set(_name_tokens(b)) - ta - _GENERIC
            if not extra:
                return "partial"
            if not extra & other:
                best = "extended"
    return best


def classify(entity: dict, el: dict, nodes: dict, names: list[str], geo: dict, *,
             same_item, tag_names, qid_trusted: bool = True) -> dict:
    """Verdict for one ref whose feature failed the QID-tag rule.

    ``names``      the entity's names: its name, its aliases (not the one the link
                   was made by) and its QID's Wikidata label and aliases;
    ``geo``        {"p625": [(lon, lat)], "capitals": [(lon, lat)]} of the entity's QID;
    ``same_item``  q -> whether tag QID q is the entity's item (itself or a redirect);
    ``tag_names``  q -> (status, [label, *aliases]) of tag QID q ('missing' = deleted);
    ``qid_trusted`` whether the entity's QID looks like its own: it carries the
                   entity's name, and its dates don't contradict the entity's where the
                   feature's agree. When not, the QID may be the wrong one (others own
                   QID fixes), so evidence drawn from it (tag, P625, capital) can't
                   condemn the ref alone.
    """
    tags = el.get("tags") or {}
    etype = entity["entity_type"]
    point_like, polity = etype in bg.WIKIDATA_POINT_TYPES, etype in POLITY_TYPES
    fnames = ohm_names(tags)
    nm = name_match(names, fnames, polity=polity)
    gap = year_gap(entity, tags)
    bbox = feature_bbox(el)
    pt = bg.ohm_point(el, nodes)
    p625, anchors = geo.get("p625", []), geo.get("p625", []) + geo.get("capitals", [])
    km_p625 = min((bbox_km(bbox, p) for p in p625), default=None) if bbox else None
    km_pt = min((bg.km(pt[:2], p) for p in p625), default=None) if pt else None
    km_anchor = min((bbox_km(bbox, a) for a in anchors), default=None) if bbox else None
    tagged = tag_qids(tags)
    out = {"verdict": "UNSURE", "reasons": [], "feature_names": fnames, "name_match": nm, "year_gap": gap,
           "km_p625": None if km_p625 is None else round(km_p625, 1),
           "km_anchor": None if km_anchor is None else round(km_anchor, 1),
           "tag": ";".join(tagged), "tag_label": "; ".join((tag_names(q)[1] or [""])[0] for q in tagged)}

    def done(verdict: str, *reasons: str) -> dict:
        out["verdict"], out["reasons"] = verdict, [*out["reasons"], *reasons]
        return out

    near_enough = ((km_p625 is None or km_p625 <= WRONG_KM) if point_like else
                   (km_anchor is None or km_anchor <= POLITY_FAR_KM) if polity else True)
    # At the entity's own place: a point within OK_KM of its P625, or a compact
    # feature around it; for a polity, its capital or P625 inside the feature.
    compact = bbox is not None and bg.km(bbox[:2], bbox[2:]) <= WRONG_KM
    at_place = ((km_pt is not None and km_pt <= OK_KM and (pt[2] != "bbox_centre" or compact))
                or (km_p625 == 0 and compact)) if point_like else (
                polity and el["type"] == "relation" and km_anchor == 0)

    # 1. Tagged with another item.
    if any(same_item(q) for q in tagged):
        return done("OK", "tag_redirects_to_entity_qid")
    live = [q for q in tagged if tag_names(q)[0] != "missing"]
    if live:
        if not qid_trusted:
            return done("UNSURE", "other_qid_tag", "entity_qid_suspect")
        shares = any(names_equal(a, (tag_names(q)[1] or [""])[0]) for q in live for a in names if a)
        if shares and near_enough and (gap is None or gap <= DATE_SLACK):
            # Same name, same place and era, another item: a duplicate item, or
            # the entity's own QID is the wrong one. Not clearly another thing.
            return done("UNSURE", "other_qid_tag", "tag_item_shares_name_and_place")
        return done("WRONG", "other_qid_tag")
    if tagged:
        out["reasons"].append("tag_qid_deleted")  # then judged as untagged

    # 2. Untagged and clearly another thing.
    own = []      # the entity's own record against the feature
    via_qid = []  # evidence drawn from the entity's QID
    if nm == "none" or (nm == "extended" and not at_place):
        own.append("name_mismatch")
    linear = next((k for k in _LINEAR_KEYS if k in tags), None)
    if linear and etype not in _LINEAR_TYPES and not set(_name_tokens(entity["name"])) & _OTHER_KIND:
        own.append(f"feature_is_{linear}")  # unless the entity is itself one: 'Cato Street', 'Orange River'

    if gap is not None and gap > DATE_SLACK:
        own.append("dates_disjoint")
    if point_like and km_p625 is not None and km_p625 > WRONG_KM:
        via_qid.append(f"far_from_p625>{WRONG_KM}km")
    if polity and km_anchor is not None and km_anchor > POLITY_FAR_KM:
        via_qid.append(f"far_from_capital_and_p625>{POLITY_FAR_KM}km")
    if own or via_qid:
        if not own and not qid_trusted:
            return done("UNSURE", *via_qid, "entity_qid_suspect")
        if (own == ["dates_disjoint"] and not via_qid and nm == "exact" and point_like
                and km_pt is not None and km_pt <= OK_KM):
            # The same place in another era (Phayao's 1338-1899 node for a row dated from 1977).
            return done("UNSURE", "dates_disjoint", "same_place_other_era")
        return done("WRONG", *own, *via_qid)

    # 3. Untagged and plausibly the same: OK only on positive evidence.
    why = []
    if nm != "exact":
        why.append(f"name_{nm}")
    if point_like:
        if not p625:
            why.append("no_p625")
        elif not at_place:
            why.append(f"p625_{OK_KM}-{WRONG_KM}km")
        elif el["type"] == "relation" and not compact:
            why.append(f"relation_wider_than_{WRONG_KM}km")  # a province named after the city
    elif polity:
        if el["type"] != "relation" or not el.get("bounds"):
            why.append(f"polity_on_{el['type']}")
        elif not anchors:
            why.append("no_capital_or_p625")
        elif km_anchor != 0:
            why.append("capital_and_p625_outside_bbox")
        if gap is None:
            why.append("dates_unknown")
        elif gap > 0:
            why.append("dates_adjacent")
    else:
        why.append(f"type_not_judged:{etype}")
    if why:
        return done("UNSURE", *why)
    return done("OK", "name+p625" if point_like else "name+dates+bbox")


# ── the whole audit ──────────────────────────────────────────────────────────
def audit(cur, out_dir: Path, client: WikidataClient | None = None) -> tuple[list[dict], dict]:
    """Verdicts for every ref in the set that fails the QID check, and run stats."""
    entities, refs = load_audit_set(cur)
    print(f"{len(refs)} active OHM refs to check "
          f"({Counter(r['scope'] for r in refs)['unplaced']} on unplaced entities); fetching OHM…")
    elements, nodes, live = fetch_cached(refs, out_dir / "cache")
    stats: dict[str, Any] = {"refs_checked": len(refs), "overpass_requests": live, "not_in_ohm": Counter(),
                             "passes_qid": Counter()}
    failing = []
    for ref in refs:
        reason = fails_qid_check(entities[ref["entity_id"]], ref, elements, nodes)
        if reason == "ohm:qid_mismatch":
            failing.append(ref)
        elif reason == "ohm:not_in_ohm":
            stats["not_in_ohm"][ref["scope"]] += 1
        else:
            stats["passes_qid"][ref["scope"]] += 1

    eids = sorted({r["entity_id"] for r in failing})
    ctx = load_entity_context(cur, eids)
    periods = load_periods(cur, [r["geometry_period_id"] for r in failing if r["geometry_period_id"]])

    client = client or WikidataClient(out_dir / "cache")
    ent_qids = {entities[e]["wikidata_id"] for e in eids}
    tags = {q for r in failing for q in tag_qids((elements[(r["external_type"], int(r["external_id"]))].get("tags") or {}))}
    print(f"Wikidata: {len(ent_qids)} entity QIDs, {len(tags)} tag QIDs…")
    client.get_entities(ent_qids | tags, progress=True)
    resolved = {q: client.resolved(q)[0] for q in ent_qids | tags}
    geo = wd_geo(client, sorted({resolved[q] for q in ent_qids}), out_dir / "cache")

    def rec(q: str) -> dict:
        return client.resolved(q)[1] or {}

    def wd_names(q: str) -> list[str]:
        r = rec(q)
        return [n for n in (r.get("label") or "", *(r.get("aliases") or [])) if n]

    cur.execute("SELECT wikidata_id, string_agg(name, ' | ') FROM entities WHERE wikidata_id = ANY(%s) GROUP BY 1",
                (sorted(tags),))
    tag_owner = dict(cur.fetchall())
    story_qids = map_story_qids()

    rows = []
    for ref in failing:
        e = entities[ref["entity_id"]]
        el = elements[(ref["external_type"], int(ref["external_id"]))]
        own = rec(e["wikidata_id"])
        aliases = clean_aliases(ctx[ref["entity_id"]]["aliases"], ref.get("display_name"))
        names = [e["name"], *aliases, *wd_names(e["wikidata_id"])]
        eq = resolved.get(e["wikidata_id"], e["wikidata_id"])
        v = classify(e, el, nodes, names, geo.get(eq, {}),
                     same_item=lambda q: resolved.get(q, q) == eq,
                     tag_names=lambda q: (rec(q).get("status", "missing"), wd_names(q)),
                     qid_trusted=any(names_compatible(a, b) for a in (e["name"], *aliases)
                                     for b in wd_names(e["wikidata_id"]))
                     and not qid_dates_disagree(e, own, el.get("tags") or {}))
        deps = ref_dependencies(ref, e, ctx[ref["entity_id"]], periods, story_qids)
        rows.append({
            "verdict": v["verdict"], "reasons": "+".join(v["reasons"]), "scope": ref["scope"],
            "geo_ref_id": ref["geo_ref_id"], "entity_id": ref["entity_id"], "entity_name": e["name"],
            "entity_type": e["entity_type"], "qid": e["wikidata_id"], "wd_label": own.get("label", ""),
            "start_year": e["start_year"], "end_year": e["end_year"],
            "ohm": f"{ref['external_type']}/{ref['external_id']}", "match_role": ref["match_role"],
            "retrieval": ref["retrieval_method"], "ohm_name": (v["feature_names"] or [""])[0],
            "ohm_names": " | ".join(v["feature_names"][:8]), "ohm_tag": v["tag"], "ohm_tag_label": v["tag_label"],
            "ohm_tag_entity": tag_owner.get(v["tag"], ""),
            "ohm_start": (el.get("tags") or {}).get("start_date", ""), "ohm_end": (el.get("tags") or {}).get("end_date", ""),
            "name_match": v["name_match"], "year_gap": v["year_gap"], "km_p625": v["km_p625"],
            "km_capital_or_p625": v["km_anchor"], "nominatim": ref.get("display_name") or "",
            **deps, "_ref": ref, "_active_refs": ctx[ref["entity_id"]]["active_refs"],
            "_polygon_periods": ctx[ref["entity_id"]]["polygon_periods"],
        })
    return rows, stats


def qid_dates_disagree(entity: dict, own: dict, tags: dict) -> bool:
    """The entity's start year misses its QID's by over 50 years while the feature's
    start agrees with it: Trinidad (Cuba, 1514) carrying Trinidad, Colorado's QID."""
    start = entity.get("start_year")
    wd_start = wd_bounds(entity["entity_type"], own.get("dates") or {})[0]
    feature_start = ohm_year(tags.get("start_date"))
    return (start is not None and wd_start is not None and feature_start is not None
            and abs(start - wd_start[0]) > 50 and abs(start - feature_start) <= DATE_SLACK)


def clean_aliases(aliases: list[str], display_name: str | None) -> list[str]:
    """The entity's aliases minus the name its Nominatim link was made by: the
    name-only linker stored that name as an alias too ('Fifth Street' for the
    Fifth French Republic), so it can't vouch for the link."""
    matched = (display_name or "").split(",")[0].strip()
    return [a for a in aliases if not (matched and names_equal(a, matched))]


def map_story_qids() -> set[str]:
    """QIDs named anywhere in the published map stories (their OHM outlines read active refs)."""
    out: set[str] = set()
    for path in (_REPO_ROOT / "api" / "resources" / "map-stories").glob("*.json"):
        out |= set(re.findall(r'"(Q[1-9]\d*)"', path.read_text(encoding="utf-8")))
    return out


def ref_dependencies(ref: dict, entity: dict, ctx: dict, periods: dict, story_qids: set[str]) -> dict:
    """What reads this ref besides the backfill: its geometry period, the entity's
    primary_geo_ref_id, and map-story outlines (relations and ways only)."""
    gp = periods.get(ref["geometry_period_id"] or "")
    return {
        "geometry_period": "" if not gp else (
            f"{gp['period_type']}/{gp['geom_type'] or '-'}{'+territory' if gp['has_territory'] else ''} "
            f"{gp['start_year']}..{gp['end_year'] or ''} by {gp['created_by'] or gp['provenance_mode']} "
            f"(1 of {gp['entity_periods']})"),
        "is_primary_geo_ref": str(entity.get("primary_geo_ref_id") or "") == ref["geo_ref_id"],
        "other_active_ohm_refs": sum(1 for r in ctx["active_refs"]
                                     if r["provider"] == "ohm" and r["geo_ref_id"] != ref["geo_ref_id"]),
        "entity_has_map_point": bool(ctx["polygon_periods"] or ctx["point_periods"]),
        "effects": "map_story_outline" if (ref["external_type"] in ("relation", "way")
                                           and entity["wikidata_id"] in story_qids) else "",
    }


# ── output ───────────────────────────────────────────────────────────────────
FIELDS = ["verdict", "reasons", "action", "scope", "geo_ref_id", "entity_id", "entity_name", "entity_type", "qid",
          "wd_label", "start_year", "end_year", "ohm", "match_role", "retrieval", "ohm_name", "ohm_names", "ohm_tag",
          "ohm_tag_label", "ohm_tag_entity", "ohm_start", "ohm_end", "name_match", "year_gap", "km_p625",
          "km_capital_or_p625", "nominatim", "geometry_period", "is_primary_geo_ref", "new_primary_geo_ref",
          "other_active_ohm_refs", "entity_has_map_point", "effects"]


def plan_actions(rows: list[dict]) -> None:
    """Set each row's action: deactivate a WRONG ref without a geometry period;
    hold one that has (its period was imported from the wrong feature and stays
    on the map). A deactivated primary_geo_ref_id moves to the entity's best
    remaining QID-consistent ref (``replacement_ref``), else NULL. Also notes what
    the tiles and the map lose: the entity's last active OHM link (its
    ohm_osm_id, the SPA's highlight and click resolver), after which the map
    serves its polygon instead of its point (MapEntitiesAction's ohmExists)."""
    leaving = {r["geo_ref_id"] for r in rows if r["verdict"] == "WRONG" and not r["geometry_period"]}
    for r in rows:
        r["new_primary_geo_ref"] = ""
        if r["verdict"] != "WRONG":
            r["action"] = "none"
            continue
        if r["geometry_period"]:
            r["action"] = "held:geometry_period"
            continue
        r["action"] = "deactivate"
        if r["is_primary_geo_ref"]:
            r["new_primary_geo_ref"] = replacement_ref(r["_active_refs"], r["qid"], leaving) or "NULL"
        if not any(x["provider"] == "ohm" and x["geo_ref_id"] not in leaving for x in r["_active_refs"]):
            effects = ["loses_ohm_link"] + (["map_serves_polygon_not_point"] if r["_polygon_periods"] else [])
            r["effects"] = "+".join(effects + ([r["effects"]] if r["effects"] else []))


def replacement_ref(active_refs: list[dict], qid: str, leaving: set[str]) -> str | None:
    """The entity's best remaining active ref that agrees with its QID: an OHM ref
    tagged with it, else its own Wikidata ref; one backing a map period first."""
    def rank(r: dict) -> tuple | None:
        if r["geo_ref_id"] in leaving:
            return None
        if r["provider"] == "ohm" and r["tag_qid"] == qid:
            kind = 0
        elif r["provider"] == "wikidata" and r["external_id"] == qid:
            kind = 1
        else:
            return None
        return (r["geometry_period_id"] is None, kind, r["match_role"] != "primary", r["geo_ref_id"])
    ranked = sorted((k, r["geo_ref_id"]) for r in active_refs if (k := rank(r)) is not None)
    return ranked[0][1] if ranked else None


def write_verdicts(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    order = {"WRONG": 0, "UNSURE": 1, "OK": 2}
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (order[r["verdict"]], r["reasons"], r["entity_name"])):
            w.writerow(r)


# ── apply ────────────────────────────────────────────────────────────────────
def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False, sort_keys=True).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def backup(out_dir: Path) -> Path:
    """pg_dump entity_geo_refs (schema + data, custom format) before any write."""
    path = out_dir / f"entity_geo_refs-{time.strftime('%Y%m%d-%H%M%S')}.dump"
    with path.open("wb") as fh:
        proc = subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-d", "history-mapped",
                               "-Fc", "--no-owner", "-t", "public.entity_geo_refs"],
                              stdout=fh, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or path.stat().st_size == 0:
        raise SystemExit(f"pg_dump failed: {proc.stderr.decode()[:500]}")
    return path


def rollback_sql(rows: list[dict], backup_path: Path) -> str:
    """Statements that undo the deactivations, each guarded on this audit's own mark."""
    lines = [f"-- Rollback of {TAG} (generated {time.strftime('%Y-%m-%d %H:%M')}).",
             "-- Run: docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped "
             f"-f - < {OUT_DIR.relative_to(_REPO_ROOT)}/rollback.sql",
             "-- Each statement touches only a row this audit changed and nobody changed since.",
             f"-- Full table backup: pg_restore --data-only -t entity_geo_refs {backup_path.name}",
             "\\set ON_ERROR_STOP on", "BEGIN;"]
    for r in rows:
        if r["action"] != "deactivate":
            continue
        ref = r["_ref"]
        lines.append(
            f"UPDATE entity_geo_refs SET is_active = true, source_meta = {_lit(ref['source_meta'])}, "
            f"updated_at = {_lit(str(ref['updated_at']) if ref['updated_at'] else None)} "
            f"WHERE geo_ref_id = {_lit(r['geo_ref_id'])} AND NOT is_active AND source_meta->>'deactivated_by' = {_lit(TAG)};")
        if r["is_primary_geo_ref"]:
            new = None if r["new_primary_geo_ref"] == "NULL" else r["new_primary_geo_ref"]
            lines.append(
                f"UPDATE entities SET primary_geo_ref_id = {_lit(r['geo_ref_id'])} WHERE entity_id = {_lit(r['entity_id'])} "
                f"AND primary_geo_ref_id IS NOT DISTINCT FROM {_lit(new)};")
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def apply(conn, rows: list[dict]) -> Counter:
    """Deactivate the planned refs in one transaction; every write is guarded on the
    values the audit read (still active, same feature and period, unchanged since,
    and the entity still carries the QID it was judged against)."""
    done: Counter = Counter()
    cur = conn.cursor()
    try:
        cur.execute("SET LOCAL lock_timeout = '15s'")
        for r in rows:
            if r["action"] != "deactivate":
                continue
            ref = r["_ref"]
            cur.execute("""
                UPDATE entity_geo_refs g
                SET is_active = false, updated_at = now(),
                    source_meta = COALESCE(g.source_meta, '{}'::jsonb) || jsonb_build_object(
                        'deactivated_by', %(tag)s::text, 'deactivated_reason', %(reason)s::text,
                        'deactivated_at', to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
                WHERE g.geo_ref_id = %(id)s AND g.is_active AND g.provider = 'ohm'
                  AND g.entity_id = %(eid)s AND g.external_type::text = %(type)s AND g.external_id = %(ext)s
                  AND g.geometry_period_id IS NULL AND g.updated_at IS NOT DISTINCT FROM %(updated)s
                  AND EXISTS (SELECT 1 FROM entities e WHERE e.entity_id = g.entity_id
                              AND e.wikidata_id IS NOT DISTINCT FROM %(qid)s)
            """, {"tag": TAG, "reason": f"{r['verdict']}: {r['reasons']}", "id": r["geo_ref_id"],
                  "eid": r["entity_id"], "type": ref["external_type"], "ext": ref["external_id"],
                  "updated": ref["updated_at"], "qid": r["qid"]})
            if cur.rowcount != 1:
                r["action"] = "skipped:changed_since_read"
                done["skipped"] += 1
                continue
            done["deactivated"] += 1
            if r["is_primary_geo_ref"]:
                new = None if r["new_primary_geo_ref"] == "NULL" else r["new_primary_geo_ref"]
                cur.execute("UPDATE entities SET primary_geo_ref_id = %s WHERE entity_id = %s AND primary_geo_ref_id = %s",
                            (new, r["entity_id"], r["geo_ref_id"]))
                done["primary_repointed" if new else "primary_cleared"] += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="deactivate the WRONG refs (default: dry run)")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="output directory")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    conn = psycopg.connect(bg.DSN)
    cur = conn.cursor()
    rows, stats = audit(cur, args.out)
    conn.rollback()  # end the read transaction
    plan_actions(rows)
    write_verdicts(args.out / "verdicts.csv", rows)

    print("\n" + "=" * 72)
    print("OHM REF AUDIT" + ("  (APPLYING)" if args.apply else "  (DRY RUN)"))
    print("=" * 72)
    print(f"Refs checked: {stats['refs_checked']}; pass the QID rule: {dict(stats['passes_qid'])}; "
          f"feature gone from OHM: {dict(stats['not_in_ohm'])}; Overpass requests: {stats['overpass_requests']}")
    print(f"Fail the QID rule: {len(rows)}")
    for (scope, verdict), n in sorted(Counter((r["scope"], r["verdict"]) for r in rows).items()):
        print(f"   {scope:9s} {verdict:7s} {n}")
    print("Reasons:")
    for (verdict, reason), n in Counter((r["verdict"], r["reasons"]) for r in rows).most_common():
        print(f"   {verdict:7s} {reason:58s} {n}")
    print("Actions:", dict(Counter(r["action"] for r in rows)))
    print("Primary replacements:", dict(Counter("NULL" if r["new_primary_geo_ref"] == "NULL" else "repoint"
                                               for r in rows if r["new_primary_geo_ref"])))
    print("Effects of the deactivations:", dict(Counter(r["effects"] or "-" for r in rows if r["action"] == "deactivate")))
    ok_unplaced = [r for r in rows if r["verdict"] == "OK" and not r["entity_has_map_point"]]
    print(f"OK refs on entities with no map point: {len(ok_unplaced)} refs, "
          f"{len({r['entity_id'] for r in ok_unplaced})} entities")
    print(f"Verdicts: {args.out / 'verdicts.csv'}")

    if args.apply:
        path = backup(args.out)
        (args.out / "rollback.sql").write_text(rollback_sql(rows, path), encoding="utf-8")
        print(f"\nBackup {path.name} and rollback.sql written; applying in one transaction…")
        done = apply(conn, rows)
        write_verdicts(args.out / "verdicts.csv", rows)
        print(f"  committed: {dict(done)}")
    else:
        print("\nDry run: re-run with --apply to deactivate the WRONG refs.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
