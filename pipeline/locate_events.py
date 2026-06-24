#!/usr/bin/env python3
"""Give event-type entities a map location.

Events (battles, wars, treaties, rebellions, disasters, epidemics, migrations,
tech-adoption, legal-reform) often have no geometry, so they never appear on the
map. Most have a Wikidata QID with either a coordinate of their own (P625 — a
battle's site) or a "location" place to borrow from. This sets the CANONICAL
primary location (entity_locations.geom) for each such event, using:

  1. the event's own P625 coordinate, else
  2. the coordinate of its associated place (P276/P19/…), else
  3. nothing — reported for hand-location.

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

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
EVENT_TYPES = (
    "event_war", "event_battle", "event_treaty", "event_rebellion",
    "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease",
)


def real_coord(meta: dict, place_cache: dict) -> tuple[str | None, str]:
    if meta.get("coordinates"):
        return meta["coordinates"], "wikidata_p625"
    loc = meta.get("location_qid")
    if loc:
        if loc not in place_cache:
            place_cache.update(fetch_entity_meta([loc]))
        if place_cache.get(loc, {}).get("coordinates"):
            return place_cache[loc]["coordinates"], "place_of_event"
    return None, ""


# Relationship types that point an event AT a place — strongest signal first.
_PLACE_RELS = ("located_at", "fought_at", "part_of", "occurred_in", "contains",
               "capital_of", "controlled_by", "participated_in", "caused", "resulted_from")


def inferred_coord(cur, eid: str) -> tuple[str | None, str, int | None]:
    """Borrow a located neighbour's coordinate (+ its relationship year). Prefers a
    place/polity counterpart and a place-ish relationship, so 'End of Apartheid'
    lands on South Africa, 'Spartacus Revolt' on Rome — 'some kind of location'."""
    cur.execute("""
        SELECT ST_AsText(el.geom), o.name, o.entity_type::text, r.relationship_type::text,
               r.start_year, r.end_year
        FROM relationships r
        JOIN entities o ON o.entity_id = CASE WHEN r.source_entity_id=%(e)s THEN r.target_entity_id ELSE r.source_entity_id END
        JOIN entity_locations el ON el.entity_id=o.entity_id AND el.is_primary AND el.geom IS NOT NULL
        WHERE (r.source_entity_id=%(e)s OR r.target_entity_id=%(e)s)
          -- only borrow from a concrete place — never a person/concept, whose
          -- location is itself often a wrong-namesake guess (Omar Khayyam→Canada).
          AND o.entity_type::text IN ('city','political_entity','infrastructure_monument',
                                      'event_battle','educational_institution')
        ORDER BY
          (o.entity_type::text IN ('city','infrastructure_monument','event_battle')) DESC,
          array_position(%(rels)s::text[], r.relationship_type::text) NULLS LAST
        LIMIT 1
    """, {"e": eid, "rels": list(_PLACE_RELS)})
    row = cur.fetchone()
    if not row:
        return None, "", None
    wkt, oname, otype, rtype, rsy, rey = row
    return wkt, f"rel:{rtype}->{oname[:18]}", (rsy or rey)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--types", default=",".join(EVENT_TYPES))
    args = ap.parse_args()
    types = tuple(t.strip() for t in args.types.split(","))

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
    place_cache: dict[str, dict] = {}

    located, need_hand = [], []
    for eid, name, etype, qid, sy, ey in rows:
        meta = meta_by_qid.get(qid, {}) if qid else {}
        wkt, src = real_coord(meta, place_cache) if meta else (None, "")
        year = sy or ey or era_year(meta.get("start_date")) or era_year(meta.get("end_date"))
        if not wkt:
            # Fall back to a located neighbour (works for the abstract events that
            # have no coordinate of their own but relate to a place/polity).
            wkt, src, rel_year = inferred_coord(cur, eid)
            if year is None:
                year = rel_year
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
