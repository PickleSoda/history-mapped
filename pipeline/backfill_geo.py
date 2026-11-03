#!/usr/bin/env python3
"""Geo backfill: give a map point to entities that have none.

A point comes only from the entity's own record, never from a neighbour:

  1. ohm            The OHM feature the entity is linked to (an active
                    entity_geo_refs row, provider ohm), accepted only when the
                    feature's `wikidata` tag is the entity's QID: a node's
                    position, a way's centre, or a relation's admin_centre or
                    label node. A relation's bbox centre is used only when the
                    relation is compact, because a sprawling empire's lands at
                    sea. The period is tied to that ref
                    (entity_geo_refs.geometry_period_id), so the point is OHM's:
                    re-fetch it rather than hand-editing it.             [high]
  2. wikidata_p625  The entity's own Wikidata coordinate, where OHM gave none,
                    for point-like types only, because a polity's or war's P625
                    is a country centroid. A later run replaces it with an OHM
                    point once the entity gets an OHM link.              [high]

Borrowing a related place's coordinate (birth place, located-in) was removed:
it put the Cold War in the Amazon and the Kingdom of Serbia at Vienna. Name-only
OHM matches without the QID tag are skipped for the same reason ("Poland" was a
node in North Dakota). So is an OHM point more than 50 km from the entity's own
Wikidata site (Nanning's QID tags a node named Liuzhou). Relationship inference
and OSM Nominatim stay out too (bare ancient names hit modern hamlets).

The map reads geometry_periods only, filtered by start_year (NULL shows at every
year), so a point needs a start year: the entity's own range, else the OHM ref's,
else the span the atlas itself attests: the first to the last year of the
entity's dated relationships (low confidence ones aside), left open for a city
Wikidata gives a population and no end date. That span is a lower
bound, never a founding or end date, so it goes on the period only (with a
description saying so, confidence medium) and not into entity_temporal_ranges.
Wikidata had no usable start date for ~5k of these (pipeline/backfill_dates.py).
Dry run by default; --apply writes in a single transaction. Either way the plan
is written to --out as CSV. Every period this writes has created_by
'geo-backfill:ohm' or 'geo-backfill:wikidata_p625'.

    pipeline/.venv/bin/python3 -m pipeline.backfill_geo            # dry run
    pipeline/.venv/bin/python3 -m pipeline.backfill_geo --apply    # write
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg
import requests

from pipeline.agent.tools.wikidata import fetch_entity_meta

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
OHM_OVERPASS = "https://overpass-api.openhistoricalmap.org/api/interpreter"
USER_AGENT = "history-mapped/1.0 (https://github.com/PickleSoda/history-mapped)"

OHM_TIER = "geo-backfill:ohm"
WIKIDATA_TIER = "geo-backfill:wikidata_p625"

# Types whose Wikidata P625 is a site. For polities, wars, cultures and the like
# it is a country or region centroid, so it neither places them nor vouches for
# an OHM point.
WIKIDATA_POINT_TYPES = frozenset({
    "city", "infrastructure_monument", "educational_institution", "extraction_infra",
    "event_battle", "event_treaty", "event_natural_disaster", "cultural_work",
})
MAX_DISAGREE_KM = 50
# Types whose Wikidata population figure (and no end date) means they still exist.
LIVING_TYPES = frozenset({"city"})
ATTESTED_NOTE = ("Years attested in the atlas (from its first dated relationship; to its last, "
                 "unless the place still exists), not a founding or end date.")
MAX_BBOX_KM = 1500

# Lower is better: a real node beats a computed centre.
KIND_RANK = {"node": 0, "admin_centre": 0, "label": 1, "way_centre": 1, "bbox_centre": 2}
KIND_CONFIDENCE = {"bbox_centre": "medium"}
# Why an entity's OHM refs gave no point, from least to most informative.
OHM_REASONS = ("ohm:not_in_ohm", "ohm:qid_mismatch", "ohm:sprawling_relation",
               "ohm:disagrees_with_wikidata")


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lon, lat) points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


def parse_pt(wkt: str) -> tuple[float, float]:
    nums = wkt.replace("Point(", "").replace(")", "").split()
    return (float(nums[0]), float(nums[1]))


def ohm_point(el: dict, nodes: dict[int, tuple[float, float]]) -> tuple[float, float, str] | None:
    """(lon, lat, kind) for an Overpass element, or None for a sprawling relation."""
    if el["type"] == "node":
        return el["lon"], el["lat"], "node"
    if el["type"] == "way":
        c = el.get("center")
        return (c["lon"], c["lat"], "way_centre") if c else None
    for role in ("admin_centre", "label"):
        for m in el.get("members", []):
            if m["type"] == "node" and m["role"] == role and m["ref"] in nodes:
                return (*nodes[m["ref"]], role)
    b = el.get("bounds")
    # A relation across the 180th meridian (Fiji, Tuvalu) gets a ~360°-wide bbox whose
    # corners are close, so it looks compact and its centre lands near 0° in the Atlantic.
    if b and b["maxlon"] - b["minlon"] > 180:
        return None
    if b and km((b["minlon"], b["minlat"]), (b["maxlon"], b["maxlat"])) <= MAX_BBOX_KM:
        return (b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2, "bbox_centre"
    return None


def ref_span(ref: dict) -> int:
    start, end = ref["temporal_start_year"], ref["temporal_end_year"]
    if start is None:
        return 0
    return (end if end is not None else date.today().year) - start


def pick_ohm(entity: dict, refs: list[dict], elements: dict, nodes: dict,
             wd_point: tuple[float, float] | None) -> tuple[tuple[dict, tuple[float, float, str]] | None, str]:
    """The best (ref, point) among an entity's OHM refs, or None and the reason."""
    best, best_key, reason = None, None, 0
    for ref in refs:
        el = elements.get((ref["external_type"], int(ref["external_id"])))
        if el is None:
            continue
        if el.get("tags", {}).get("wikidata") != entity["wikidata_id"]:
            reason = max(reason, 1)
            continue
        pt = ohm_point(el, nodes)
        if pt is None:
            reason = max(reason, 2)
            continue
        if (wd_point and entity["entity_type"] in WIKIDATA_POINT_TYPES
                and km(pt[:2], wd_point) > MAX_DISAGREE_KM):
            reason = max(reason, 3)
            continue
        key = (KIND_RANK[pt[2]], ref["match_role"] != "primary", -ref_span(ref))
        if best_key is None or key < best_key:
            best, best_key = (ref, pt), key
    return best, "" if best else OHM_REASONS[reason]


def period_years(entity: dict, ref: dict | None = None) -> tuple[int, int | None] | None:
    """(start, end) of the point's period, or None if it would show at every year.

    The entity's own range comes first: one point stands for the whole entity,
    while an OHM ref is often a slice of it (one border period, a few days for
    some British Empire relations) or a mapper's placeholder year.
    """
    if entity["start_year"] is not None:
        return entity["start_year"], entity["end_year"]
    if ref is not None and ref["temporal_start_year"] is not None:
        return ref["temporal_start_year"], ref["temporal_end_year"]
    return None


def confidence(kind: str, years_from: str) -> str:
    return "medium" if years_from == "attested" else KIND_CONFIDENCE.get(kind, "high")


def point_years(entity: dict, ref: dict | None = None,
                living: bool = False) -> tuple[int, int | None, str] | None:
    """period_years, else the attested span; with where the years came from.

    A place that still stands stays on the map from its first attested year on,
    rather than flashing up for the one year (1348 for Carcassonne) it is cited.
    """
    years = period_years(entity, ref)
    if years is not None:
        return *years, "entity" if entity["start_year"] is not None else "ohm_ref"
    if entity.get("attested_start") is not None:
        return entity["attested_start"], None if living else entity["attested_end"], "attested"
    return None


def overpass(query: str) -> list[dict]:
    for attempt in range(5):
        r = requests.post(OHM_OVERPASS, data={"data": query}, timeout=300,
                          headers={"User-Agent": USER_AGENT})
        if r.status_code in (429, 502, 503, 504):
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["elements"]
    r.raise_for_status()
    raise RuntimeError(f"OHM Overpass kept answering {r.status_code}")


def fetch_ohm(refs: list[dict]) -> tuple[dict, dict]:
    """Elements keyed by (type, id), and the positions of relations' admin_centre/label nodes."""
    ids: dict[str, set[int]] = defaultdict(set)
    for ref in refs:
        ids[ref["external_type"]].add(int(ref["external_id"]))
    elements: dict[tuple[str, int], dict] = {}
    # Nodes need the body for their position; relations need it for members.
    for kind, kw, out, chunk in (("node", "node", "out;", 500), ("way", "way", "out tags center;", 500),
                                 ("relation", "rel", "out body bb;", 100)):
        todo = sorted(ids[kind])
        for i in range(0, len(todo), chunk):
            q = f"[out:json][timeout:240];{kw}(id:{','.join(map(str, todo[i:i + chunk]))});{out}"
            for el in overpass(q):
                elements[(el["type"], el["id"])] = el
            print(f"   OHM {kind}s {min(i + chunk, len(todo))}/{len(todo)}", flush=True)
    wanted = sorted({m["ref"] for el in elements.values() if el["type"] == "relation"
                     for m in el.get("members", [])
                     if m["type"] == "node" and m["role"] in ("admin_centre", "label")})
    nodes: dict[int, tuple[float, float]] = {}
    for i in range(0, len(wanted), 500):
        for el in overpass(f"[out:json][timeout:240];node(id:{','.join(map(str, wanted[i:i + 500]))});out skel;"):
            nodes[el["id"]] = (el["lon"], el["lat"])
    return elements, nodes


def load_state(cur) -> tuple[list[dict], int]:
    """Entities with no map geometry (or only our own Wikidata point), and the located count."""
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text AS entity_type, e.wikidata_id,
               t.start_year, t.end_year, e.primary_geo_ref_id,
               a.attested_start, a.attested_end,
               EXISTS (SELECT 1 FROM geometry_periods gp
                       WHERE gp.entity_id = e.entity_id AND gp.created_by = %(wd)s) AS has_wikidata_point
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        LEFT JOIN LATERAL (
            SELECT MIN(r.start_year) AS attested_start,
                   MAX(COALESCE(r.end_year, r.start_year)) AS attested_end
            FROM relationships r
            WHERE (r.source_entity_id = e.entity_id OR r.target_entity_id = e.entity_id)
              AND r.start_year IS NOT NULL AND r.confidence IS DISTINCT FROM 'low'
        ) a ON t.start_year IS NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM geometry_periods gp
            WHERE gp.entity_id = e.entity_id
              AND (gp.geom IS NOT NULL OR gp.territory_geom IS NOT NULL)
              AND gp.created_by IS DISTINCT FROM %(wd)s)
        ORDER BY e.entity_id
    """, {"wd": WIKIDATA_TIER})
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.execute("SELECT COUNT(DISTINCT entity_id) FROM geometry_periods "
                "WHERE geom IS NOT NULL OR territory_geom IS NOT NULL")
    return rows, cur.fetchone()[0]


def load_ohm_refs(cur, entity_ids: list) -> dict[str, list[dict]]:
    cur.execute("""
        SELECT geo_ref_id, entity_id, external_type::text AS external_type, external_id,
               match_role::text AS match_role, temporal_start_year, temporal_end_year
        FROM entity_geo_refs
        WHERE provider = 'ohm' AND is_active AND external_id ~ '^[0-9]+$'
          AND entity_id = ANY(%s)
    """, (entity_ids,))
    cols = [d[0] for d in cur.description]
    out: dict[str, list[dict]] = defaultdict(list)
    for r in cur.fetchall():
        ref = dict(zip(cols, r))
        out[str(ref["entity_id"])].append(ref)
    return out


def plan_points(no_point: list[dict], refs_by_entity: dict, elements: dict, nodes: dict,
                meta: dict) -> tuple[dict[str, dict], Counter, Counter, dict[str, list[str]]]:
    """Planned points, why OHM refs were rejected, why entities stay unplaced, samples."""
    planned: dict[str, dict] = {}
    rejected: Counter = Counter()
    skipped: Counter = Counter()
    samples: dict[str, list[str]] = defaultdict(list)

    def sample(reason: str, e: dict) -> None:
        if len(samples[reason]) < 6:
            samples[reason].append(f"{e['name'][:34]} ({e['entity_type']}, {e['wikidata_id']})")

    def skip(reason: str, e: dict) -> None:
        skipped[reason] += 1
        sample(reason, e)

    for e in no_point:
        eid, qid = str(e["entity_id"]), e["wikidata_id"]
        if not qid:
            skipped["no_qid"] += 1
            continue
        m = meta.get(qid, {})
        wd = parse_pt(m["coordinates"]) if m.get("coordinates") else None

        living = e["entity_type"] in LIVING_TYPES and m.get("populated") and not m.get("end_date")
        refs = refs_by_entity.get(eid, [])
        if refs:
            pick, reason = pick_ohm(e, refs, elements, nodes, wd)
            if pick:
                ref, (lon, lat, kind) = pick
                years = point_years(e, ref, living)
                if years is None:
                    skip("no_start_year", e)
                    continue
                planned[eid] = {"tier": OHM_TIER, "kind": kind, "lon": lon, "lat": lat,
                                "start": years[0], "end": years[1], "years_from": years[2],
                                "ref": ref, "extid": f"{ref['external_type']}/{ref['external_id']}",
                                "confidence": confidence(kind, years[2]),
                                "wd_km": round(km((lon, lat), wd), 1) if wd else None}
                continue
            # The entity's own Wikidata site below may still place it.
            rejected[reason] += 1
            sample(reason, e)

        if e["has_wikidata_point"]:
            continue  # placed by an earlier run, and OHM has nothing better yet
        if e["entity_type"] not in WIKIDATA_POINT_TYPES:
            skipped["area_type_without_ohm_point"] += 1
            continue
        if wd is None:
            skipped["no_coordinate"] += 1
            continue
        years = point_years(e, living=living)
        if years is None:
            skip("no_start_year", e)
            continue
        planned[eid] = {"tier": WIKIDATA_TIER, "kind": "p625", "lon": wd[0], "lat": wd[1],
                        "start": years[0], "end": years[1], "years_from": years[2],
                        "ref": None, "extid": qid,
                        "confidence": confidence("p625", years[2]), "wd_km": 0.0}
    return planned, rejected, skipped, samples


def write_plan(path: Path, planned: dict, id2row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entity_id", "name", "type", "qid", "tier", "kind", "source", "lon", "lat",
                    "start_year", "end_year", "years_from", "km_from_wikidata"])
        for eid, p in planned.items():
            r = id2row[eid]
            w.writerow([eid, r["name"], r["entity_type"], r["wikidata_id"], p["tier"], p["kind"],
                        p["extid"], f"{p['lon']:.5f}", f"{p['lat']:.5f}", p["start"], p["end"], p["years_from"], p["wd_km"]])


def apply_plan(cur, planned: dict, id2row: dict) -> None:
    for eid, p in planned.items():
        row = id2row[eid]
        ohm = p["tier"] == OHM_TIER
        if ohm and row["has_wikidata_point"]:
            cur.execute("""
                UPDATE entity_geo_refs SET geometry_period_id = NULL
                WHERE geometry_period_id IN (SELECT geometry_period_id FROM geometry_periods
                                             WHERE entity_id = %s AND created_by = %s)
            """, (eid, WIKIDATA_TIER))
            cur.execute("DELETE FROM geometry_periods WHERE entity_id = %s AND created_by = %s",
                        (eid, WIKIDATA_TIER))

        cur.execute("""
            INSERT INTO geometry_periods
                (entity_id, period_type, start_year, end_year, provenance_mode, geom,
                 confidence, created_by, description, created_at, updated_at)
            VALUES (%s, 'territory', %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s::confidence_level, %s, %s, now(), now())
            RETURNING geometry_period_id
        """, (eid, p["start"], p["end"], "ohm_import" if ohm else "manual",
              p["lon"], p["lat"], p["confidence"], p["tier"],
              ATTESTED_NOTE if p["years_from"] == "attested" else None))
        period_id = cur.fetchone()[0]

        if ohm:
            ref_id = p["ref"]["geo_ref_id"]
            cur.execute("UPDATE entity_geo_refs SET geometry_period_id = %s, updated_at = now() "
                        "WHERE geo_ref_id = %s", (period_id, ref_id))
        else:
            # Reuse the entity's own Wikidata ref; never repoint another provider's.
            cur.execute("""
                UPDATE entity_geo_refs SET geometry_period_id = %s, updated_at = now()
                WHERE geo_ref_id = (SELECT geo_ref_id FROM entity_geo_refs
                                    WHERE entity_id = %s AND provider = 'wikidata' AND external_id = %s
                                    ORDER BY created_at LIMIT 1)
                RETURNING geo_ref_id
            """, (period_id, eid, p["extid"]))
            hit = cur.fetchone()
            if hit:
                ref_id = hit[0]
            else:
                cur.execute("""
                    INSERT INTO entity_geo_refs
                        (entity_id, external_id, is_active, provider, external_type, match_role,
                         retrieval_method, match_score, source_meta, geometry_period_id,
                         created_at, updated_at)
                    VALUES (%s, %s, true, 'wikidata', 'qid', 'fallback', 'rest', 0.90,
                            '{"source": "wikidata_p625"}'::jsonb, %s, now(), now())
                    RETURNING geo_ref_id
                """, (eid, p["extid"], period_id))
                ref_id = cur.fetchone()[0]

        # Mirror onto the canonical primary location (what the admin editor reads).
        # An OHM point also replaces this script's own earlier Wikidata point.
        # LocationResolutionMethod values (the app throws on others); OHM is 'ohm_nominatim',
        # as in HydrateEntityGeometryFromGeoRefAction.
        method = "ohm_nominatim" if ohm else "wikidata"
        cur.execute("""
            UPDATE entity_locations
            SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326), location_method = %s, updated_at = now()
            WHERE entity_id = %s AND is_primary AND territory_geom IS NULL
              AND (geom IS NULL OR %s)
        """, (p["lon"], p["lat"], method, eid, ohm and row["has_wikidata_point"]))
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO entity_locations
                    (entity_id, location_name, geom, location_method, is_primary, created_at, updated_at)
                SELECT %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, true, now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM entity_locations WHERE entity_id = %s AND is_primary)
            """, (eid, row["name"], p["lon"], p["lat"], method, eid))

        if row["primary_geo_ref_id"] is None or (ohm and row["has_wikidata_point"]):
            cur.execute("UPDATE entities SET primary_geo_ref_id = %s WHERE entity_id = %s", (ref_id, eid))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write points (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap entities (smoke test)")
    ap.add_argument("--out", type=Path,
                    default=Path(f"output/audit/geo-backfill-{date.today():%Y%m%d}/planned.csv"),
                    help="CSV of the planned points")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    no_point, located = load_state(cur)
    if args.limit:
        no_point = no_point[: args.limit]
    id2row = {str(r["entity_id"]): r for r in no_point}
    print(f"{len(no_point)} entities without a map point ({located} already located)\n")

    with_qid = [r for r in no_point if r["wikidata_id"]]
    refs_by_entity = load_ohm_refs(cur, [r["entity_id"] for r in with_qid])
    all_refs = [ref for refs in refs_by_entity.values() for ref in refs]
    print(f"Fetching {len(all_refs)} OHM features for {len(refs_by_entity)} linked entities…")
    elements, nodes = fetch_ohm(all_refs)
    qids = sorted({r["wikidata_id"] for r in with_qid})
    print(f"Fetching Wikidata coords for {len(qids)} QIDs…")
    meta = fetch_entity_meta(qids)

    planned, rejected, skipped, samples = plan_points(no_point, refs_by_entity, elements, nodes, meta)
    write_plan(args.out, planned, id2row)

    # ── Report ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("GEO BACKFILL" + ("  (APPLYING)" if args.apply else "  (DRY RUN)"))
    print("=" * 72)
    # An entity whose only point is ours from Wikidata is both located and reloaded here.
    missing = sum(1 for r in no_point if not r["has_wikidata_point"])
    total = located + missing
    print(f"Points to add: {len(planned)} / {missing} missing   (plan: {args.out})")
    for (tier, kind), n in sorted(Counter((p["tier"], p["kind"]) for p in planned.values()).items()):
        print(f"   {tier:28s} {kind:13s} {n}")
    print("Years from: " + ", ".join(f"{k} {n}" for k, n in
                                     Counter(p["years_from"] for p in planned.values()).most_common()))
    print("By type:")
    for t, n in Counter(id2row[eid]["entity_type"] for eid in planned).most_common(12):
        print(f"   {t:28s} {n}")
    print("OHM links rejected (the entity's Wikidata site may still place it):")
    for reason, n in rejected.most_common():
        print(f"   {reason:28s} {n}")
    print("Not placed:")
    for reason, n in skipped.most_common():
        print(f"   {reason:28s} {n}")
    print(f"Coverage: {located}/{total} ({100 * located // total}%) → "
          f"{located + len(planned)}/{total} ({100 * (located + len(planned)) // total}%)\n")
    for reason in (*OHM_REASONS, "no_start_year"):
        if samples.get(reason):
            print(f"── {reason}: " + "; ".join(samples[reason]))

    if args.apply:
        print("\nApplying in a single transaction…")
        try:
            apply_plan(cur, planned, id2row)
            conn.commit()
            print(f"  committed {len(planned)} points.")
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
    else:
        print("\nDry run: re-run with --apply to write.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
