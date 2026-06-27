#!/usr/bin/env python3
"""Detect mislocated entities: a geometry point that sits far from the entity's
own graph-neighbours is almost always a wrong-QID location (the political_entity
"Babylon" → Babylon, New York; "Eridu" → Florida), because its neighbours pin
the real region (Babylon's neighbours are all Near East).

Context-based, so it does NOT false-flag a correctly-resolved ancient place whose
coordinate already agrees with its neighbours (Sparta in Greece). Read-only — it
proposes nothing, just lists suspects with their bad point, QID, and the
neighbour region they should be near.

    pipeline/.venv/bin/python3 -m pipeline.detect_mislocated
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from statistics import median

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"

# Geographic types whose own coordinate must be meaningful (skip people/works,
# which are located via an approximate place-of-association).
GEO_TYPES = {
    "city", "political_entity", "infrastructure_monument", "extraction_infra",
    "educational_institution", "event_battle", "event_war", "event_treaty",
    "event_rebellion", "event_natural_disaster", "migration", "epidemic_disease",
    "archaeological_culture", "trade_route",
}
CONFLICT_KM = 3000.0   # point this far from the neighbour centroid = suspect
MIN_NEIGHBORS = 2


def haversine(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def main() -> int:
    conn = psycopg.connect(DSN)
    cur = conn.cursor()

    cur.execute("SELECT entity_id, name, entity_type::text, wikidata_id FROM entities")
    ent = {str(i): {"name": n, "type": t, "qid": q} for i, n, t, q in cur.fetchall()}

    # All geometry points per entity (an entity may have several after the backfills).
    cur.execute("SELECT entity_id, ST_X(geom), ST_Y(geom) FROM geometry_periods WHERE geom IS NOT NULL")
    pts: dict[str, list[tuple[float, float]]] = {}
    for eid, lon, lat in cur.fetchall():
        pts.setdefault(str(eid), []).append((lon, lat))

    # Each entity's representative location = median of its points (robust to a
    # single stray duplicate) — used only as a NEIGHBOUR anchor.
    rep: dict[str, tuple[float, float]] = {
        eid: (median(p[0] for p in ps), median(p[1] for p in ps)) for eid, ps in pts.items()
    }

    cur.execute("SELECT source_entity_id, target_entity_id FROM relationships")
    neigh: dict[str, set[str]] = {}
    for s, t in cur.fetchall():
        neigh.setdefault(str(s), set()).add(str(t))
        neigh.setdefault(str(t), set()).add(str(s))

    suspects = []
    for eid, ps in pts.items():
        meta = ent.get(eid)
        if not meta or meta["type"] not in GEO_TYPES:
            continue
        ncoords = [rep[o] for o in neigh.get(eid, ()) if o in rep and o != eid]
        if len(ncoords) < MIN_NEIGHBORS:
            continue
        ncen = (median(c[0] for c in ncoords), median(c[1] for c in ncoords))
        # Distance of each of the entity's points to the neighbour centroid;
        # flag the entity if ANY point is cross-region (that's the bad duplicate).
        far = [(p, haversine(p, ncen)) for p in ps]
        far = [(p, d) for p, d in far if d > CONFLICT_KM]
        if far:
            worst = max(far, key=lambda x: x[1])
            suspects.append({
                "name": meta["name"], "type": meta["type"], "qid": meta["qid"],
                "bad_point": worst[0], "dist_km": worst[1], "neighbor_centroid": ncen,
                "n_neighbors": len(ncoords), "n_points": len(ps),
            })

    suspects.sort(key=lambda s: s["dist_km"], reverse=True)
    print(f"{len(suspects)} mislocated suspects (point >{CONFLICT_KM:.0f} km from neighbour region)\n")
    print(f"{'name':28s} {'type':18s} {'qid':10s} {'bad point':>20s}  {'~km off':>8s}")
    print("-" * 92)
    for s in suspects:
        bp = f"({s['bad_point'][0]:.1f},{s['bad_point'][1]:.1f})"
        print(f"{s['name'][:28]:28s} {s['type'][:18]:18s} {str(s['qid'])[:10]:10s} {bp:>20s}  {s['dist_km']:8.0f}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
