#!/usr/bin/env python3
"""Wikidata geo backfill: give a real map point to entities that have none.

After the QID repair, entities resolved to the correct Wikidata item, so a real
coordinate is available for most. This places a point ONLY from the entity's own
Wikidata coordinate — never from a neighbour:

  1. wikidata_p625        — the entity's own coordinate (exact).            [high]
  2. wikidata_place_assoc — the coordinate of its birth/death/work place.   [medium]

Relationship inference ("place an entity at a related entity's location") was
removed deliberately: it is confusing on the map (an entity appears wherever its
neighbours are) and produced conflicting duplicate points. OHM is not re-run here
(it's the pipeline's first try for new runs); OSM Nominatim is excluded (bare
ancient names hit modern hamlets — "Caffa"→Lombardy).

Each point is confidence-tagged. Dry-run by default; --apply writes (single
transaction). --limit N caps for a smoke test.

    pipeline/.venv/bin/python3 -m pipeline.backfill_geo            # dry run
    pipeline/.venv/bin/python3 -m pipeline.backfill_geo --apply    # write
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline.agent.tools.wikidata import fetch_entity_meta

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"

# (provider, external_type, retrieval_method, match_role, match_score, confidence)
TIER_META = {
    "wikidata_p625":        ("wikidata", "qid", "rest", "fallback", 0.90, "high"),
    "wikidata_place_assoc": ("wikidata", "qid", "rest", "fallback", 0.60, "medium"),
}


def load_state(cur):
    """Return no_point rows + located count (for the coverage report)."""
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text, e.wikidata_id,
               t.start_year, t.end_year,
               (SELECT g.geo_ref_id FROM entity_geo_refs g
                WHERE g.entity_id = e.entity_id
                ORDER BY (g.source_meta->>'source' = 'chronicle_centroid') DESC NULLS LAST
                LIMIT 1) AS geo_ref_id,
               e.primary_geo_ref_id
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        LEFT JOIN geometry_periods gp ON gp.entity_id = e.entity_id
        WHERE gp.entity_id IS NULL
    """)
    cols = [d[0] for d in cur.description]
    no_point = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute("SELECT COUNT(DISTINCT entity_id) FROM geometry_periods WHERE geom IS NOT NULL")
    located = cur.fetchone()[0]
    return no_point, located


def parse_pt(wkt):
    nums = wkt.replace("Point(", "").replace(")", "").split()
    return (float(nums[0]), float(nums[1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write points (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap entities (smoke test)")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    no_point, located = load_state(cur)
    if args.limit:
        no_point = no_point[: args.limit]
    print(f"{len(no_point)} entities without a map point ({located} already located)\n")

    qids = sorted({r["wikidata_id"] for r in no_point if r["wikidata_id"]})
    print(f"Fetching Wikidata coords for {len(qids)} QIDs…")
    meta: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        meta.update(fetch_entity_meta(qids[i:i + 50]))
    place_qids = sorted({m["location_qid"] for m in meta.values()
                         if m.get("location_qid") and not m.get("coordinates")})
    place_meta: dict[str, dict] = {}
    for i in range(0, len(place_qids), 50):
        place_meta.update(fetch_entity_meta(place_qids[i:i + 50]))

    planned: dict[str, dict] = {}  # entity_id -> {lon,lat,tier,detail,extid}
    for r in no_point:
        qid = r["wikidata_id"]
        if not qid:
            continue
        m = meta.get(qid, {})
        if m.get("coordinates"):
            lon, lat = parse_pt(m["coordinates"])
            planned[str(r["entity_id"])] = {"lon": lon, "lat": lat, "tier": "wikidata_p625",
                                            "extid": qid, "detail": "P625"}
        elif m.get("location_qid") and place_meta.get(m["location_qid"], {}).get("coordinates"):
            lon, lat = parse_pt(place_meta[m["location_qid"]]["coordinates"])
            planned[str(r["entity_id"])] = {"lon": lon, "lat": lat, "tier": "wikidata_place_assoc",
                                            "extid": m["location_qid"], "detail": f"place {m['location_qid']}"}

    # A point is only time-placeable if its entity has a start year: the map filters
    # geometry by geometry_periods.start_year/end_year (NULL end = ongoing), so a
    # point on a date-less entity renders at EVERY year. Drop those.
    id2row = {str(r["entity_id"]): r for r in no_point}
    skipped = [eid for eid in list(planned) if id2row[eid]["start_year"] is None]
    for eid in skipped:
        del planned[eid]

    # ── Report ──────────────────────────────────────────────────────────────
    by_tier = Counter(p["tier"] for p in planned.values())
    print("\n" + "=" * 72)
    print("GEO BACKFILL" + ("  (DRY RUN)" if not args.apply else "  (APPLYING)"))
    print("=" * 72)
    print(f"Points to add: {len(planned)} / {len(no_point)} missing  "
          f"({len(skipped)} skipped — no start year, would be always-on)")
    for tier in ("wikidata_p625", "wikidata_place_assoc"):
        print(f"   {tier:24s} {by_tier.get(tier, 0)}")
    total = located + len(no_point)
    print(f"Coverage: {located}/{total} ({100*located//total}%) → "
          f"{located + len(planned)}/{total} ({100*(located + len(planned))//total}%)\n")
    for tier in ("wikidata_p625", "wikidata_place_assoc"):
        items = [(eid, p) for eid, p in planned.items() if p["tier"] == tier]
        if not items:
            continue
        print(f"── {tier} (showing {min(10, len(items))}/{len(items)}) ──")
        for eid, p in items[:10]:
            print(f"   {id2row[eid]['name'][:30]:30s} {p['detail'][:20]:20s} ({p['lon']:.2f}, {p['lat']:.2f})")
        print()

    # ── Apply ─────────────────────────────────────────────────────────────
    if args.apply:
        print("Applying in a single transaction…")
        try:
            for eid, p in planned.items():
                row = id2row[eid]
                prov, ext_type, retr, role, score, conf = TIER_META[p["tier"]]
                # start_year is non-NULL (filtered); end_year mirrors the entity's
                # range (NULL = ongoing) so the map-by-year filter bounds the point.
                cur.execute("""
                    INSERT INTO geometry_periods
                        (entity_id, period_type, start_year, end_year, provenance_mode, geom,
                         confidence, created_by, created_at, updated_at)
                    VALUES (%s, 'territory', %s, %s, 'manual',
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s::confidence_level,
                            %s, now(), now())
                """, (eid, row["start_year"], row["end_year"], p["lon"], p["lat"],
                      conf, f"geo-backfill:{p['tier']}"))

                # Mirror the own coordinate onto the canonical primary location
                # (entity_locations) — what the admin editor and entity:backfill read.
                cur.execute("""
                    UPDATE entity_locations
                    SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        location_method = 'wikidata', updated_at = now()
                    WHERE entity_id = %s AND is_primary = true
                      AND geom IS NULL AND territory_geom IS NULL
                """, (p["lon"], p["lat"], eid))
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO entity_locations
                            (entity_id, location_name, geom, location_method, is_primary, created_at, updated_at)
                        SELECT %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'wikidata', true, now(), now()
                        WHERE NOT EXISTS (
                            SELECT 1 FROM entity_locations WHERE entity_id=%s AND is_primary=true)
                    """, (eid, row["name"], p["lon"], p["lat"], eid))

                src_meta = f'{{"source": "{p["tier"]}", "detail": "{p["detail"]}"}}'
                if row["geo_ref_id"]:
                    cur.execute("""
                        UPDATE entity_geo_refs
                        SET provider=%s::geo_ref_provider, external_type=%s::geo_ref_external_type,
                            match_role=%s::geo_ref_match_role, retrieval_method=%s::geo_ref_retrieval_method,
                            external_id=%s, match_score=%s, is_active=true,
                            source_meta=%s::jsonb, updated_at=now()
                        WHERE geo_ref_id=%s
                    """, (prov, ext_type, role, retr, p["extid"], score, src_meta, row["geo_ref_id"]))
                    ref_id = row["geo_ref_id"]
                else:
                    cur.execute("""
                        INSERT INTO entity_geo_refs
                            (entity_id, external_id, is_active, provider, external_type,
                             match_role, retrieval_method, match_score, source_meta, created_at, updated_at)
                        VALUES (%s, %s, true, %s::geo_ref_provider, %s::geo_ref_external_type,
                                %s::geo_ref_match_role, %s::geo_ref_retrieval_method, %s, %s::jsonb, now(), now())
                        RETURNING geo_ref_id
                    """, (eid, p["extid"], prov, ext_type, role, retr, score, src_meta))
                    ref_id = cur.fetchone()[0]

                if row["primary_geo_ref_id"] is None:
                    cur.execute("UPDATE entities SET primary_geo_ref_id=%s WHERE entity_id=%s", (ref_id, eid))
            conn.commit()
            print(f"  committed {len(planned)} points.")
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
    else:
        print("Dry run — re-run with --apply to write.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
