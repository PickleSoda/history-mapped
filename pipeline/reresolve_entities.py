#!/usr/bin/env python3
"""Targeted in-place re-resolution of specific committed entities.

Why this exists (and not a pipeline re-run): re-running a transcript only updates
the entities the LLM happens to re-extract that run — extraction varies, so stale
rows (wrong QID/type/date, e.g. the Roman entities pinned to 753 BCE) get left
behind. This script instead iterates the ACTUAL committed rows by name, and for
each one:

  1. Re-resolves the Wikidata QID with the patched resolver (P31 type-check +
     sitelink popularity + era), so "Forum" lands on the Roman Forum rather than
     the generic concept, "Italy" on the country rather than a stray namesake.
  2. Re-derives entity_type (+ group) from the corrected QID's P31 ("Italy" city →
     political_entity), its coordinates (P625 / place-of-association), and its
     dates (Wikidata-authoritative, OVERWRITING the bad ones — this is the whole
     point, unlike repair_committed_data which only fills gaps).
  3. UPDATEs the row by entity_id — so entity_id is preserved and every
     relationship pointing at it survives.

Dry-run by default (prints a before/after table, writes nothing). --apply writes
in one transaction. Pass entity names as args, else a built-in known-broken set.

    pipeline/.venv/bin/python3 -m pipeline.reresolve_entities Italy England Norway
    pipeline/.venv/bin/python3 -m pipeline.reresolve_entities --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline.agent.tools.wikidata import (
    search_wikidata_by_name, fetch_entity_meta, _rank_candidates,
)
from pipeline.agent.tools.disambiguation import (
    EXPECTED_P31, rerank_by_type, rerank_by_era, era_year, is_ambiguous,
)
from pipeline.agent.graph.nodes.commit_writer import ENTITY_TYPE_TO_GROUP

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
# Accept a QID *change* only above this score — a vague name ("Pyramids",
# "Senate") otherwise grabs a stray namesake, which is worse than leaving it.
RERESOLVE_ACCEPT = 0.6

# Creative-work / not-a-real-thing P31s. A place/polity/person/monument/event that
# re-resolves to one of these (e.g. "Pyramids" → a painting named Pyramids) is a
# bad match — reject the QID change and keep the old one rather than corrupt it.
_CREATIVE_OR_BOGUS_P31 = {
    "Q3305213", "Q860861", "Q179700", "Q482994", "Q7366", "Q134556", "Q11424",
    "Q7889", "Q105543609", "Q2188189", "Q4167410", "Q16521", "Q202444", "Q101352",
}
_REAL_THING_GROUPS = {"PLACE", "POLITY", "EVENT", "ECONOMY"}

# Entities reported broken (free-model QIDs/types/dates). Default target set.
DEFAULT_TARGETS = [
    "Pyramids", "England", "Italy", "Norway", "Lebanon", "Kiev", "Medieval Universities",
    "Forum", "Senate", "Patricians", "Plebeians", "Roman military", "ancient Rome",
]

# ── P31 (Wikidata "instance of") → our entity_type ──────────────────────────
# Built by inverting EXPECTED_P31 and adding the place/monument/education classes
# it doesn't carry. First matching P31 in an entity's list wins, so order the
# entity's P31s by Wikidata's own priority (already the case).
_EXTRA_P31_TO_TYPE: dict[str, str] = {
    # infrastructure_monument
    "Q4989906": "infrastructure_monument", "Q570116": "infrastructure_monument",
    "Q811979": "infrastructure_monument", "Q12518": "infrastructure_monument",
    "Q16970": "infrastructure_monument", "Q44613": "infrastructure_monument",
    "Q23413": "infrastructure_monument", "Q16560": "infrastructure_monument",
    "Q57821": "infrastructure_monument", "Q2080521": "infrastructure_monument",
    "Q37152": "infrastructure_monument", "Q12516": "infrastructure_monument",
    "Q164992": "infrastructure_monument",
    # educational_institution
    "Q3918": "educational_institution", "Q875538": "educational_institution",
    "Q38723": "educational_institution", "Q2385804": "educational_institution",
    "Q9826": "educational_institution", "Q189004": "educational_institution",
    "Q3914": "educational_institution", "Q15936437": "educational_institution",
    # political_entity extras
    "Q7275": "political_entity", "Q15634554": "political_entity",
    "Q1307214": "political_entity", "Q1489259": "political_entity",
}


def _build_p31_to_type() -> dict[str, str]:
    out: dict[str, str] = {}
    # EXPECTED_P31 is entity_type -> {p31}; invert. On collision keep the first
    # (EXPECTED_P31 iteration order puts the more specific types first).
    for etype, p31s in EXPECTED_P31.items():
        for p in p31s:
            out.setdefault(p, etype)
    out.update(_EXTRA_P31_TO_TYPE)  # extras win — they're hand-curated
    return out


P31_TO_TYPE = _build_p31_to_type()


def derive_type(p31: list[str], current: str) -> str:
    """Map the candidate's P31 chain to one of our entity types; keep current when
    nothing maps confidently (so we never downgrade a good type to a guess)."""
    for p in p31:
        if p in P31_TO_TYPE:
            return P31_TO_TYPE[p]
    return current


def reresolve(name: str, type_hint: str, era: int | None) -> dict | None:
    """Best Wikidata candidate for a name via the patched resolver. Returns the top
    candidate (with _meta attached) regardless of score — the caller decides whether
    to accept the change. None only when the search yields nothing."""
    results = search_wikidata_by_name(name, limit=10)
    if not results:
        return None
    ranked = _rank_candidates(results, name, type_hint)
    meta = fetch_entity_meta([c["qid"] for c in ranked])
    rerank_by_type(ranked, type_hint, meta)
    if is_ambiguous(ranked) and era is not None:
        rerank_by_era(ranked, era, meta)
    if not ranked:
        return None
    top = ranked[0]
    top["_meta"] = meta.get(top["qid"], {})
    return top


def accept_change(cand: dict, current_group: str) -> bool:
    """Whether to trust a re-resolved QID enough to overwrite the old one."""
    if cand.get("score", 0) < RERESOLVE_ACCEPT:
        return False
    p31 = set(cand.get("_meta", {}).get("p31", []))
    if current_group in _REAL_THING_GROUPS and (p31 & _CREATIVE_OR_BOGUS_P31):
        return False  # a place/polity/event must not become a painting/album/taxon
    return True


def real_coord(qid: str, meta: dict, place_cache: dict) -> tuple[str | None, str]:
    if meta.get("coordinates"):
        return meta["coordinates"], "wikidata_p625"
    loc = meta.get("location_qid")
    if loc:
        if loc not in place_cache:
            place_cache.update(fetch_entity_meta([loc]))
        if place_cache.get(loc, {}).get("coordinates"):
            return place_cache[loc]["coordinates"], "wikidata_place_of_association"
    return None, ""


def wd_url(qid: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}"


def _plan(eid, ename, etype, egroup, old_qid, sy, ey, has_geom, settled_qid, meta, label, place_cache) -> dict:
    """Assemble one update plan from a settled QID + its Wikidata record.

    Date policy: overwrite from Wikidata ONLY when Wikidata has a date; otherwise
    KEEP the existing year. This fixes wrong dates the corrected QID knows about
    (Forum -753→-800) without nulling a correct one the QID happens to omit (the
    Giza pyramids genuinely date to ~2600 BCE even though Q13217298 has no P571).
    """
    new_type = derive_type(meta.get("p31", []), etype)
    new_group = ENTITY_TYPE_TO_GROUP.get(new_type, egroup)
    wkt, geo_src = real_coord(settled_qid, meta, place_cache)
    wd_sy, wd_ey = era_year(meta.get("start_date")), era_year(meta.get("end_date"))
    return {
        "entity_id": eid, "name": ename, "old_qid": old_qid, "new_qid": settled_qid,
        "new_label": label, "old_type": etype, "new_type": new_type, "new_group": new_group,
        "old_sy": sy, "old_ey": ey,
        "new_sy": wd_sy if wd_sy is not None else sy,
        "new_ey": wd_ey if wd_ey is not None else ey,
        "wkt": wkt, "geo_src": geo_src, "has_geom": has_geom,
        "desc": meta.get("description", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="*",
                    help="entity names to re-resolve; use 'Name=QID' to pin a QID for a "
                         "vague name the resolver can't disambiguate (e.g. 'Pyramids=Q13217298')")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()
    raw_targets = args.names or DEFAULT_TARGETS
    # Parse "Name=QID" overrides into {name: forced_qid}; plain names → auto-resolve.
    forced: dict[str, str] = {}
    targets: list[str] = []
    for t in raw_targets:
        if "=" in t:
            nm, q = t.split("=", 1)
            forced[nm.strip()] = q.strip()
            targets.append(nm.strip())
        else:
            targets.append(t)

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    place_cache: dict[str, dict] = {}
    plans: list[dict] = []

    for name in targets:
        cur.execute("""
            SELECT e.entity_id, e.name, e.entity_type::text, e.entity_group::text,
                   e.wikidata_id, t.start_year, t.end_year,
                   (gp.entity_id IS NOT NULL) AS has_geom
            FROM entities e
            LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
            LEFT JOIN geometry_periods gp ON gp.entity_id = e.entity_id
            WHERE e.name = %s
        """, (name,))
        rows = cur.fetchall()
        if not rows:
            print(f"  (no entity named {name!r})")
            continue
        for eid, ename, etype, egroup, qid, sy, ey, has_geom in rows:
            era = sy or ey
            forced_qid = forced.get(ename)
            if forced_qid:
                # Operator-pinned QID for a vague name — derive everything from it.
                settled_qid = forced_qid
                settled_meta = fetch_entity_meta([forced_qid]).get(forced_qid, {})
                label = settled_meta.get("label", ename) + " [pinned]"
                plans.append(_plan(eid, ename, etype, egroup, qid, sy, ey, has_geom,
                                   settled_qid, settled_meta, label, place_cache))
                continue
            cand = reresolve(ename, etype, era)
            # Settle on a QID: take the re-resolved one only when confident; else
            # keep the existing QID but still refresh its type/date/geo from its own
            # Wikidata record (so e.g. "Senate" keeps its QID yet loses the bad -753).
            if cand and cand["qid"] != qid and accept_change(cand, egroup):
                settled_qid, settled_meta, label = cand["qid"], cand["_meta"], cand.get("label", "")
            elif qid:
                settled_qid = qid
                settled_meta = fetch_entity_meta([qid]).get(qid, {})
                label = settled_meta.get("label", ename)
                if cand and cand["qid"] != qid:
                    label += " [kept old QID: low-confidence/bad match]"
            else:
                print(f"  [no QID and no confident match] {ename} ({etype})")
                continue
            plans.append(_plan(eid, ename, etype, egroup, qid, sy, ey, has_geom,
                               settled_qid, settled_meta, label, place_cache))

    # ── Report ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"RE-RESOLUTION PLAN ({len(plans)} entities)" + ("  — DRY RUN" if not args.apply else "  — APPLYING"))
    print("=" * 100)
    for p in plans:
        qid_chg = "" if p["old_qid"] == p["new_qid"] else f"  QID {p['old_qid']}→{p['new_qid']}"
        type_chg = "" if p["old_type"] == p["new_type"] else f"  TYPE {p['old_type']}→{p['new_type']}"
        date_chg = "" if (p["old_sy"], p["old_ey"]) == (p["new_sy"], p["new_ey"]) else \
            f"  DATE ({p['old_sy']},{p['old_ey']})→({p['new_sy']},{p['new_ey']})"
        geo = f"  GEO→{p['geo_src']}" if p["wkt"] else "  GEO→(none)"
        print(f"{p['name'][:22]:22s} {p['new_qid']:>9s} {p['new_label'][:24]:24s}{qid_chg}{type_chg}{date_chg}{geo}")

    if args.apply and plans:
        print("\nApplying…")
        try:
            for p in plans:
                cur.execute("""
                    UPDATE entities
                    SET wikidata_id=%s, entity_type=%s, entity_group=%s,
                        source_citations = jsonb_set(
                            jsonb_set(COALESCE(source_citations,'{}'::jsonb),'{wikidata_id}',to_jsonb(%s::text)),
                            '{wikidata_url}', to_jsonb(%s::text)),
                        updated_at=now()
                    WHERE entity_id=%s
                """, (p["new_qid"], p["new_type"], p["new_group"], p["new_qid"], wd_url(p["new_qid"]), p["entity_id"]))
                # Dates: overwrite (these rows are the broken ones). updateOrCreate.
                cur.execute("""
                    INSERT INTO entity_temporal_ranges (temporal_range_id, entity_id, range_type, start_year, end_year, start_date, end_date, is_primary, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, 'primary', %s, %s, %s, %s, true, now(), now())
                    ON CONFLICT (entity_id) WHERE is_primary DO UPDATE
                      SET start_year=EXCLUDED.start_year, end_year=EXCLUDED.end_year,
                          start_date=EXCLUDED.start_date, end_date=EXCLUDED.end_date, updated_at=now()
                """, (p["entity_id"], p["new_sy"], p["new_ey"],
                      str(p["new_sy"]) if p["new_sy"] is not None else None,
                      str(p["new_ey"]) if p["new_ey"] is not None else None))
                # Geo: write the CANONICAL primary location (entity_locations) — the
                # source the map + `entity:backfill` read. Updating only the derived
                # geometry_periods left the canonical location stale (e.g. "Italy"
                # still at Italy, Texas). Run `php artisan entity:backfill
                # --entity-id=<id>` afterwards to rebuild geometry_periods from this.
                if p["wkt"]:
                    pg_wkt = p["wkt"].replace("Point(", "POINT(")
                    cur.execute("""
                        INSERT INTO entity_locations (location_id, entity_id, geom, location_method, is_primary, created_at, updated_at)
                        VALUES (gen_random_uuid(), %s, ST_SetSRID(ST_GeomFromText(%s),4326), 'wikidata', true, now(), now())
                        ON CONFLICT (entity_id) WHERE is_primary DO UPDATE
                          SET geom=EXCLUDED.geom, location_method='wikidata', updated_at=now()
                    """, (p["entity_id"], pg_wkt))
                    # Keep the derived periods roughly in sync immediately (backfill
                    # will canonicalise them); harmless if it has none yet.
                    cur.execute("UPDATE geometry_periods SET geom=ST_SetSRID(ST_GeomFromText(%s),4326), updated_at=now() WHERE entity_id=%s",
                                (pg_wkt, p["entity_id"]))
            conn.commit()
            print(f"  committed {len(plans)} updates.")
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
    elif not args.apply:
        print("\nDry run — re-run with --apply to write.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
