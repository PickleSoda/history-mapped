#!/usr/bin/env python3
"""Give event-type entities a map location from their own Wikidata coordinate.

Events often have no geometry, so they never appear on the map. This sets the
CANONICAL primary location (entity_locations.geom) of a point-like event (a
battle, treaty or disaster: backfill_geo.WIKIDATA_POINT_TYPES) to its own P625,
the site. A war's or a migration's P625 is a region centroid, and a related
place's coordinate (P276, P19, a relationship's other end) is never borrowed,
so the rest are reported for hand-location. backfill_geo.py places events the
same way and tries their OHM feature first; this adds a missing year from the
event's own Wikidata dates.

The event's year comes from its temporal range (or Wikidata point-in-time). After
this, run `php artisan entity:backfill` to materialise the geometry_periods the
map renders.

Dry-run by default; --apply writes entity_locations (no geometry_periods — that's
backfill's job). --types limits to a comma-list of entity types.

    pipeline/.venv/bin/python3 -m pipeline.locate_events
    pipeline/.venv/bin/python3 -m pipeline.locate_events --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline.agent.tools.wikidata import fetch_entity_meta
from pipeline.agent.tools.disambiguation import era_year
from pipeline.backfill_geo import WIKIDATA_POINT_TYPES

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
EVENT_TYPES = (
    "event_war", "event_battle", "event_treaty", "event_rebellion",
    "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease",
)


def own_coord(meta: dict) -> str | None:
    """The event's own Wikidata coordinate (P625), nothing borrowed."""
    return meta.get("coordinates") or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--types", default=",".join(EVENT_TYPES))
    args = ap.parse_args()
    # Only point-like types: other events' P625 is a centroid.
    types = tuple(t.strip() for t in args.types.split(",") if t.strip() in WIKIDATA_POINT_TYPES)

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text, e.wikidata_id,
               t.start_year, t.end_year
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id=e.entity_id AND t.is_primary
        WHERE e.entity_type::text = ANY(%s)
          AND NOT EXISTS (SELECT 1 FROM geometry_periods gp
                          WHERE gp.entity_id=e.entity_id AND gp.geom IS NOT NULL)
        ORDER BY e.entity_type::text, e.name
    """, (list(types),))
    rows = cur.fetchall()
    print(f"{len(rows)} event entities without a map location\n")

    qids = [r[3] for r in rows if r[3]]
    meta_by_qid: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        meta_by_qid.update(fetch_entity_meta(qids[i:i + 50]))

    located, need_hand = [], []
    for eid, name, etype, qid, sy, ey in rows:
        meta = meta_by_qid.get(qid, {}) if qid else {}
        wkt = own_coord(meta)
        src = "wikidata_p625" if wkt else ""
        year = sy or ey or era_year(meta.get("start_date")) or era_year(meta.get("end_date"))
        if wkt and year is not None:
            located.append({"entity_id": eid, "name": name, "type": etype,
                            "wkt": wkt, "src": src, "year": year, "had_year": sy is not None})
        else:
            need_hand.append((name, etype, "no-coord" if not wkt else "no-year"))

    print(f"Auto-locatable: {len(located)}   |   need hand: {len(need_hand)}\n")
    by_src: dict[str, int] = {}
    for p in located:
        by_src[p["src"]] = by_src.get(p["src"], 0) + 1
    print("  by source:", by_src, "\n")
    for p in located[:20]:
        print(f"   {p['name'][:34]:34s} {p['type']:20s} {p['src']:16s} {p['wkt']}  y={p['year']}")
    if need_hand:
        print(f"\n── need hand-location ({len(need_hand)}) ──")
        for n, et, why in need_hand[:40]:
            print(f"   {n[:40]:40s} {et:22s} [{why}]")

    if args.apply and located:
        for p in located:
            pg = p["wkt"].replace("Point(", "POINT(")
            cur.execute("""
                INSERT INTO entity_locations (location_id, entity_id, geom, location_method, is_primary, created_at, updated_at)
                VALUES (gen_random_uuid(), %s, ST_SetSRID(ST_GeomFromText(%s),4326), 'wikidata', true, now(), now())
                ON CONFLICT (entity_id) WHERE is_primary DO UPDATE
                  SET geom=EXCLUDED.geom, location_method='wikidata', updated_at=now()
            """, (p["entity_id"], pg))
            # Backfill needs a year on the range to slice the period; fill if missing.
            if not p["had_year"]:
                cur.execute("""
                    INSERT INTO entity_temporal_ranges (temporal_range_id, entity_id, range_type, start_year, end_year, start_date, is_primary, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, 'primary', %s, %s, %s, true, now(), now())
                    ON CONFLICT (entity_id) WHERE is_primary DO UPDATE
                      SET start_year=COALESCE(entity_temporal_ranges.start_year, EXCLUDED.start_year),
                          start_date=COALESCE(entity_temporal_ranges.start_date, EXCLUDED.start_date), updated_at=now()
                """, (p["entity_id"], p["year"], p["year"], str(p["year"])))
        conn.commit()
        print(f"\nWrote {len(located)} event locations. Now run: php artisan entity:backfill")
    elif not args.apply:
        print("\nDry run — re-run with --apply, then entity:backfill.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
