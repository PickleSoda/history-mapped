#!/usr/bin/env python3
"""Multi-source geo backfill: give a real map point to entities that have none.

After the QID repair, 681/1070 entities had no point — many because the failed
batch resolved them to the wrong Wikidata entity (no coords → a fake "chronicle
centroid" with no geometry). The QIDs are now correct, so real coordinates are
available. This recovers them WITHOUT relying on Wikidata alone, in priority of
reliability ("Exact + graph"):

  1. wikidata_p625          — the entity's own coordinate (exact).            [high]
  2. wikidata_place_assoc   — the coordinate of its birth/death/work place.   [medium]
  3. relationship_inference — "assimilate to a located neighbor": place it at a
                              related entity that is ALREADY on the map (a battle
                              at its city, a person at their polity). Graph-grounded,
                              so it can't wander to a same-named modern village the
                              way a blind name-search does.                    [low]

OHM is intentionally NOT re-run here: it is the pipeline's first try for new runs,
and the entities still missing points are ones OHM already missed. OSM Nominatim is
excluded by choice (bare ancient names hit modern hamlets — "Caffa"→Lombardy).

Each point is confidence-tagged so the map can style approximate ones. Dry-run by
default; --apply writes (single transaction). --limit N caps for a smoke test.

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

# Relation types that imply the entity sits at/near the other end, best first. An
# unlocated entity inherits the coordinate of its highest-priority located neighbor.
LOCATION_RELATIONS = [
    "located_at", "capital_of", "fought_at", "born_in", "died_in", "resided_in",
    "built_by", "destroyed_by", "occurred_at", "part_of", "contains",
    "controlled_by", "passes_through", "stationed_at", "rules", "governed_by",
    "participated_in",
]
_REL_PRIORITY = {r: i for i, r in enumerate(LOCATION_RELATIONS)}

# Entity types for which relationship inference is unsafe: spatially-extended
# polities and abstract/non-point concepts legitimately relate to far-flung
# things, so inheriting a single neighbour's coordinate snaps them to the wrong
# place (e.g. "Papacy" → a related entity in Canada). These get a point only
# from their own coordinate (Wikidata P625 / place assoc), never from a neighbour.
INFERENCE_EXCLUDED_TYPES = {
    "political_entity", "dynasty",            # span territory, not a point
    "trade_route", "migration",              # linear / diffuse
    "intellectual_movement", "religious_movement",  # abstract movements
    "social_class", "language", "technology",       # abstract / non-spatial
    "legal_code", "currency_monetary_system",       # abstract instruments/systems
    "diplomatic_relationship",                       # a relation, not a place
}

# (provider, external_type, retrieval_method, match_role, match_score, confidence)
TIER_META = {
    "wikidata_p625":          ("wikidata", "qid",     "rest",   "fallback", 0.90, "high"),
    "wikidata_place_assoc":   ("wikidata", "qid",     "rest",   "fallback", 0.60, "medium"),
    "relationship_inference": ("custom",   "feature", "manual", "fallback", 0.40, "low"),
}


def load_state(cur):
    """Return (no_point rows, located {entity_id:(lon,lat)}, names {id:name})."""
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text, e.wikidata_id,
               t.start_year, t.end_year,
               (SELECT g.geo_ref_id FROM entity_geo_refs g
                WHERE g.entity_id = e.entity_id
                ORDER BY (g.source_meta->>'source' = 'chronicle_centroid') DESC NULLS LAST
                LIMIT 1) AS geo_ref_id,
               e.primary_geo_ref_id,
               EXISTS (
                   SELECT 1 FROM entity_locations el
                   WHERE el.entity_id = e.entity_id AND el.is_primary = true
                     AND (el.geom IS NOT NULL OR el.territory_geom IS NOT NULL)
               ) AS has_own_location
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        LEFT JOIN geometry_periods gp ON gp.entity_id = e.entity_id
        WHERE gp.entity_id IS NULL
    """)
    cols = [d[0] for d in cur.description]
    no_point = [dict(zip(cols, r)) for r in cur.fetchall()]

    cur.execute("""
        SELECT entity_id, ST_X(geom), ST_Y(geom)
        FROM geometry_periods WHERE geom IS NOT NULL
    """)
    located = {str(eid): (lon, lat) for eid, lon, lat in cur.fetchall()}

    cur.execute("SELECT entity_id, name FROM entities")
    names = {str(eid): n for eid, n in cur.fetchall()}
    return no_point, located, names


def best_neighbor(eid: str, located: dict, rels: dict, names: dict):
    """Highest-priority located neighbour of `eid`. Returns (coord, rtype, other_id)."""
    best = None  # (priority, rtype, other)
    for rtype, other in rels.get(eid, []):
        if other in located and rtype in _REL_PRIORITY and other != eid:
            cand = (_REL_PRIORITY[rtype], rtype, other)
            if best is None or cand[0] < best[0]:
                best = cand
    if best is None:
        return None
    _, rtype, other = best
    return located[other], rtype, other


def load_neighbor_rels(cur):
    """entity_id -> list of (rel_type, other_entity_id) over all relationships."""
    cur.execute("SELECT source_entity_id, target_entity_id, relationship_type::text FROM relationships")
    out: dict[str, list[tuple[str, str]]] = {}
    for src, tgt, rtype in cur.fetchall():
        out.setdefault(str(src), []).append((rtype, str(tgt)))
        out.setdefault(str(tgt), []).append((rtype, str(src)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write points (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap entities (smoke test)")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    no_point, located, names = load_state(cur)
    if args.limit:
        no_point = no_point[: args.limit]
    print(f"{len(no_point)} entities without a map point ({len(located)} already located)\n")

    # ── Tiers 1+2: Wikidata coordinate for the (now-correct) QID ─────────────
    qids = sorted({r["wikidata_id"] for r in no_point if r["wikidata_id"]})
    print(f"Fetching Wikidata coords for {len(qids)} QIDs…")
    meta: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        meta.update(fetch_entity_meta(qids[i:i + 50]))
    place_qids = sorted({m["location_qid"] for m in meta.values() if m.get("location_qid") and not m.get("coordinates")})
    place_meta: dict[str, dict] = {}
    for i in range(0, len(place_qids), 50):
        place_meta.update(fetch_entity_meta(place_qids[i:i + 50]))

    def parse_pt(wkt):
        # "Point(lon lat)" -> (lon, lat)
        nums = wkt.replace("Point(", "").replace(")", "").split()
        return (float(nums[0]), float(nums[1]))

    planned: dict[str, dict] = {}  # entity_id -> {lon,lat,tier,detail,...}
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
                                            "extid": m["location_qid"],
                                            "detail": f"place {m['location_qid']}"}

    rels = load_neighbor_rels(cur)

    # NOTE: we deliberately do NOT override a Wikidata coordinate from the graph.
    # An entity's own P625 is far more trustworthy than inferring from neighbours:
    # large/abstract entities ("Europe", "Holy Roman Empire") legitimately relate
    # to far-flung things, so any "neighbours disagree" heuristic snaps them to the
    # wrong continent. Relationship inference is used ONLY to place entities that
    # have no coordinate of their own. (Residual wrong-namesake P625s — e.g. the
    # political_entity "Babylon" → Babylon, NY — are a known, small tail.)

    # ── Tier 3: relationship inference for entities Wikidata couldn't place ───
    # Guarded: skip spatially-extended/abstract types (they snap to the wrong
    # continent) and entities that already have their own primary location — those
    # are placed authoritatively from their location by the app-side backfill
    # (App\Actions\Entity\BackfillGeometryPeriodsAction), not from a neighbour.
    located_now = dict(located)
    located_now.update({eid: (p["lon"], p["lat"]) for eid, p in planned.items()})
    inference_guarded = 0
    for r in no_point:
        eid = str(r["entity_id"])
        if eid in planned:
            continue
        if r["entity_type"] in INFERENCE_EXCLUDED_TYPES or r["has_own_location"]:
            inference_guarded += 1
            continue
        nb = best_neighbor(eid, located_now, rels, names)
        if nb:
            (lon, lat), rtype, other = nb
            planned[eid] = {"lon": lon, "lat": lat, "tier": "relationship_inference",
                            "extid": r["wikidata_id"] or "inferred",
                            "detail": f"{rtype} → {names.get(other, other)[:24]}"}

    # A point is only time-placeable if its entity has a start year: the map
    # filters geometry by geometry_periods.start_year/end_year (NULL end = ongoing),
    # so a point on a date-less entity renders at EVERY year (the "Nazi Germany in
    # 2017" bug). Drop those rather than add always-on noise.
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
          f"({len(skipped)} skipped — no start year, would be always-on; "
          f"{inference_guarded} skipped — guarded inference: own-location/abstract type)")
    for tier in ("wikidata_p625", "wikidata_place_assoc", "relationship_inference"):
        print(f"   {tier:24s} {by_tier.get(tier, 0)}")
    cov_before = len(located)
    cov_after = cov_before + len(planned)
    total = len(located) + len(no_point)
    print(f"Coverage: {cov_before}/{total} ({100*cov_before//total}%) → {cov_after}/{total} ({100*cov_after//total}%)\n")

    for tier in ("wikidata_p625", "wikidata_place_assoc", "relationship_inference"):
        items = [(eid, p) for eid, p in planned.items() if p["tier"] == tier]
        if not items:
            continue
        print(f"── {tier} (showing {min(10, len(items))}/{len(items)}) ──")
        for eid, p in items[:10]:
            print(f"   {id2row[eid]['name'][:30]:30s} {p['detail'][:34]:34s} ({p['lon']:.2f}, {p['lat']:.2f})")
        print()

    # ── Apply ─────────────────────────────────────────────────────────────
    if args.apply:
        print("Applying in a single transaction…")
        try:
            for eid, p in planned.items():
                row = id2row[eid]
                prov, ext_type, retr, role, score, conf = TIER_META[p["tier"]]
                # start_year is guaranteed non-NULL (date-less entities filtered
                # out above); end_year mirrors the entity's range (NULL = ongoing)
                # so the map-by-year filter bounds the point to the entity's life.
                cur.execute("""
                    INSERT INTO geometry_periods
                        (entity_id, period_type, start_year, end_year, provenance_mode, geom,
                         confidence, created_by, created_at, updated_at)
                    VALUES (%s, 'territory', %s, %s, 'manual',
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s::confidence_level,
                            %s, now(), now())
                """, (eid, row["start_year"], row["end_year"], p["lon"], p["lat"],
                      conf, f"geo-backfill:{p['tier']}"))

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
