#!/usr/bin/env python3
"""Repair committed pipeline data: verify Wikidata QIDs, fix wrong locations & dates.

The free-model batch left three defects in the DB (see the wrong-QID diagnosis):
  1. ~15% of entities resolved to the WRONG Wikidata entity (a person → a ship,
     a battle → an insect genus), which then poisoned their coordinates/dates.
  2. 282 "chronicle_centroid" geo points at confidence 0.2 — fake points dropped
     at the chronicle's average position because no real coordinate was found.
  3. Dates carried over from the wrong QID.

This pass repairs them IN PLACE (no full pipeline rerun), reusing the patched
resolver (P31 type-check + sitelink popularity):

  • Verify QIDs   — batch-fetch P31 for every QID; flag the high-precision-wrong
                    ones (a "person" that isn't human; anything that is a taxon,
                    given/family name, or disambiguation page).
  • Re-resolve    — search + type/era rerank to find the correct QID.
  • Fix locations — pull the real coordinate from the (corrected) QID; replace the
                    0.2 centroid with it, or DELETE the fake point when Wikidata
                    has no coordinate (better no point than a wrong one).
  • Fix dates     — refresh dates from a corrected QID; fix BCE/CE sign flips.

Dry-run by default — prints a full report and writes none. Pass --apply to write
(everything runs in a single transaction). --limit N caps entities for a quick
smoke test.

    pipeline/.venv/bin/python3 -m pipeline.repair_committed_data            # dry run
    pipeline/.venv/bin/python3 -m pipeline.repair_committed_data --apply    # write
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Allow running as a plain script (python pipeline/repair_committed_data.py) by
# putting the repo root on the path so `import pipeline.*` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline.agent.tools.wikidata import (
    search_wikidata_by_name,
    fetch_entity_meta,
    _rank_candidates,
)
from pipeline.agent.tools.disambiguation import (
    UNIVERSAL_BLOCK_P31,
    rerank_by_type,
    rerank_by_era,
    era_year,
    is_ambiguous,
)

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"

# P31 classes that are acceptable for a "person" entity beyond plain human (Q5):
# deities, mythical/legendary figures, prophets, biblical/saint figures — so we
# don't churn Jesus/Buddha/Muhammad-type entries that aren't tagged Q5.
ACCEPTABLE_PERSON_P31 = {
    "Q5",          # human
    "Q178885",     # deity
    "Q4271324",    # mythical character
    "Q3327521",    # fictional/legendary character (defensive)
    "Q13002315",   # legendary figure
    "Q1234713",    # theologian/prophet (defensive)
    "Q20643955",   # biblical figure (human biblical figure)
    "Q43229",      # (defensive; ignored if absent)
    "Q101352",     # NOTE: family name — handled as wrong below, kept out in practice
}
ACCEPTABLE_PERSON_P31.discard("Q101352")  # family name is never a person

# Minimum re-resolution score to accept a new QID (else we flag and keep old).
RERESOLVE_ACCEPT = 0.5


def is_wrong_qid(entity_type: str, p31: list[str]) -> tuple[bool, str]:
    """High-precision wrong-QID detector. Returns (is_wrong, reason).

    Deliberately conservative — only flags signals that are almost never a false
    positive, so we never churn a valid-but-unlisted city/event QID:
      • P31 in the universal blocklist (taxon, given/family name, disambiguation).
      • A 'person' whose P31 has no human/deity/legendary class — i.e. a ship,
        statuette, cognomen, settlement, school, encyclopedia article, …
    Entities with no P31 at all are kept (can't judge).
    """
    p31set = set(p31)
    if not p31set:
        return (False, "no-p31")
    if p31set & UNIVERSAL_BLOCK_P31:
        return (True, f"blocklisted:{next(iter(p31set & UNIVERSAL_BLOCK_P31))}")
    if entity_type == "person":
        if p31set & ACCEPTABLE_PERSON_P31:
            return (False, "ok-person")
        return (True, f"person-not-human:{p31[0]}")
    return (False, "kept")


def reresolve(name: str, entity_type: str, era: int | None) -> dict | None:
    """Re-run the patched resolver for one label. Returns the best candidate dict
    (qid/label/score/description) when score >= RERESOLVE_ACCEPT, else None."""
    results = search_wikidata_by_name(name, limit=10)
    if not results:
        return None
    ranked = _rank_candidates(results, name, entity_type)
    meta = fetch_entity_meta([c["qid"] for c in ranked])
    rerank_by_type(ranked, entity_type, meta)
    if is_ambiguous(ranked) and era is not None:
        rerank_by_era(ranked, era, meta)
    if ranked and ranked[0].get("score", 0) >= RERESOLVE_ACCEPT:
        return ranked[0]
    return None


def wikidata_url(qid: str) -> str:
    return f"https://www.wikidata.org/wiki/{qid}"


def real_coord_for(qid: str, meta: dict, place_cache: dict) -> tuple[str | None, str]:
    """Best real coordinate for a QID. Returns (wkt, source).

    Direct P625 first; else the coordinate of an associated place (birthplace,
    deathplace, work location, …). (None, '') when Wikidata has neither.
    """
    if not qid:
        return (None, "")
    coords = meta.get("coordinates")
    if coords:
        return (coords, "wikidata_p625")
    loc_qid = meta.get("location_qid")
    if loc_qid:
        if loc_qid not in place_cache:
            place_cache.update(fetch_entity_meta([loc_qid]))
        place = place_cache.get(loc_qid, {})
        if place.get("coordinates"):
            return (place["coordinates"], "wikidata_place_of_association")
    return (None, "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap entities processed (smoke test)")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()

    # ── Load committed state ────────────────────────────────────────────────
    cur.execute("""
        SELECT e.entity_id, e.name, e.entity_type::text, e.wikidata_id,
               e.primary_geo_ref_id,
               t.start_year, t.end_year, t.start_date, t.end_date,
               g.source_meta->>'source' AS geo_source, g.match_score AS geo_score,
               (gp.entity_id IS NOT NULL) AS has_geom
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id
        LEFT JOIN entity_geo_refs g ON g.entity_id = e.entity_id
        LEFT JOIN geometry_periods gp ON gp.entity_id = e.entity_id
        WHERE e.wikidata_id IS NOT NULL AND e.wikidata_id <> ''
        ORDER BY e.name
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if args.limit:
        rows = rows[: args.limit]
    print(f"Loaded {len(rows)} entities with a QID\n")

    # ── Phase 1: batch-verify all current QIDs ──────────────────────────────
    all_qids = sorted({r["wikidata_id"] for r in rows})
    print(f"Fetching P31/sitelinks/coords for {len(all_qids)} QIDs (batched)…")
    meta_by_qid: dict[str, dict] = {}
    for i in range(0, len(all_qids), 50):
        meta_by_qid.update(fetch_entity_meta(all_qids[i:i + 50]))
    print(f"  got metadata for {len(meta_by_qid)} QIDs\n")

    place_cache: dict[str, dict] = {}
    qid_fixes, geo_fixes, geo_deletes, date_fixes, flagged = [], [], [], [], []
    reason_counter: Counter = Counter()

    for r in rows:
        eid, name, etype = r["entity_id"], r["name"], r["entity_type"]
        old_qid = r["wikidata_id"]
        meta = meta_by_qid.get(old_qid, {})
        p31 = meta.get("p31", [])
        wrong, reason = is_wrong_qid(etype, p31)

        final_qid = old_qid
        final_meta = meta
        if wrong:
            reason_counter[reason.split(":")[0]] += 1
            # Era for the tie-break — fall back through the text dates to the
            # integer year columns, so a historical polity ("Austria" start_year
            # 976) isn't re-resolved to its modern state (Republic of Austria, 1918).
            era = (era_year(r["start_date"]) or era_year(r["end_date"])
                   or r["start_year"] or r["end_year"])
            cand = reresolve(name, etype, era)
            if cand and cand["qid"] != old_qid:
                final_qid = cand["qid"]
                final_meta = fetch_entity_meta([final_qid]).get(final_qid, {})
                qid_fixes.append({
                    "entity_id": eid, "name": name, "type": etype,
                    "old_qid": old_qid, "old_desc": meta.get("description", ""),
                    "new_qid": final_qid, "new_label": cand.get("label", ""),
                    "new_desc": cand.get("description", ""), "reason": reason,
                })
            else:
                flagged.append({"entity_id": eid, "name": name, "type": etype,
                                "qid": old_qid, "reason": reason,
                                "desc": meta.get("description", "")})

        # ── Geo: fix centroids and any entity whose QID we just corrected ────
        is_centroid = r["geo_source"] == "chronicle_centroid"
        if (is_centroid or final_qid != old_qid) and r["has_geom"]:
            wkt, src = real_coord_for(final_qid, final_meta, place_cache)
            if wkt:
                geo_fixes.append({"entity_id": eid, "name": name, "wkt": wkt,
                                  "src": src, "qid": final_qid,
                                  "was": r["geo_source"]})
            elif is_centroid:
                # No real coordinate exists → the centroid is pure noise; drop it.
                geo_deletes.append({"entity_id": eid, "name": name,
                                    "primary_geo_ref_id": r["primary_geo_ref_id"]})

        # ── Dates: refresh from corrected QID; fix BCE/CE sign flips ─────────
        wd_start_y = era_year(final_meta.get("start_date"))
        wd_end_y = era_year(final_meta.get("end_date"))
        cur_start_y, cur_end_y = r["start_year"], r["end_year"]
        new_start_y, new_end_y = cur_start_y, cur_end_y
        date_reason = []
        if final_qid != old_qid:
            # Re-resolved: only FILL dates that were missing — never overwrite a
            # committed date. The committed year reflects the transcript's context
            # (e.g. "Austria" in a 1683/1938 chronicle), whereas a corrected QID's
            # date can be a modern-state inception (Republic of Austria, 1918) that
            # would be a regression. Missing→filled is a clear win (Cicero, David).
            if cur_start_y is None and wd_start_y is not None:
                new_start_y = wd_start_y
            if cur_end_y is None and wd_end_y is not None:
                new_end_y = wd_end_y
            if (new_start_y, new_end_y) != (cur_start_y, cur_end_y):
                date_reason.append("requid-fill")
        else:
            # Same QID: only correct a pure sign flip (same magnitude, opposite sign).
            if cur_start_y is not None and wd_start_y is not None \
                    and cur_start_y != wd_start_y and abs(cur_start_y) == abs(wd_start_y):
                new_start_y = wd_start_y
                date_reason.append("signflip-start")
            if cur_end_y is not None and wd_end_y is not None \
                    and cur_end_y != wd_end_y and abs(cur_end_y) == abs(wd_end_y):
                new_end_y = wd_end_y
                date_reason.append("signflip-end")
        if date_reason:
            date_fixes.append({"entity_id": eid, "name": name,
                               "old": (cur_start_y, cur_end_y),
                               "new": (new_start_y, new_end_y),
                               "reason": ",".join(date_reason)})

    # ── Report ──────────────────────────────────────────────────────────────
    print("=" * 72)
    print("REPAIR PLAN" + ("  (DRY RUN — no writes)" if not args.apply else "  (APPLYING)"))
    print("=" * 72)
    print(f"Wrong QIDs detected:     {sum(reason_counter.values())}  {dict(reason_counter)}")
    print(f"  → re-resolved:         {len(qid_fixes)}")
    print(f"  → flagged (no fix):    {len(flagged)}")
    print(f"Location fixes:          {len(geo_fixes)} (real coord) + {len(geo_deletes)} (deleted fake centroid)")
    print(f"Date fixes:              {len(date_fixes)}")
    print()

    def sample(title, items, fmt, n=12):
        if not items:
            return
        print(f"── {title} (showing {min(n, len(items))}/{len(items)}) ──")
        for it in items[:n]:
            print("   " + fmt(it))
        print()

    sample("Re-resolved QIDs", qid_fixes,
           lambda x: f"{x['name'][:26]:26s} {x['old_qid']:>9s} ({x['old_desc'][:24]}) → {x['new_qid']:>9s} {x['new_label'][:20]} ({x['new_desc'][:24]})")
    sample("Flagged, kept (no confident match)", flagged,
           lambda x: f"{x['name'][:26]:26s} {x['qid']:>9s} [{x['reason']}] ({x['desc'][:30]})")
    sample("Location → real coord", geo_fixes,
           lambda x: f"{x['name'][:30]:30s} {x['was'] or '—':22s} → {x['src']:30s} {x['wkt']}")
    sample("Location deleted (fake centroid, no real coord)", geo_deletes,
           lambda x: f"{x['name'][:40]}")
    sample("Date fixes", date_fixes,
           lambda x: f"{x['name'][:30]:30s} {str(x['old']):>16s} → {str(x['new']):>16s} [{x['reason']}]")

    # ── Apply ───────────────────────────────────────────────────────────────
    if args.apply:
        print("Applying in a single transaction…")
        try:
            for x in qid_fixes:
                cur.execute("""
                    UPDATE entities
                    SET wikidata_id = %s,
                        source_citations = jsonb_set(
                            jsonb_set(COALESCE(source_citations, '{}'::jsonb),
                                      '{wikidata_id}', to_jsonb(%s::text)),
                            '{wikidata_url}', to_jsonb(%s::text)),
                        updated_at = now()
                    WHERE entity_id = %s
                """, (x["new_qid"], x["new_qid"], wikidata_url(x["new_qid"]), x["entity_id"]))
            for x in geo_fixes:
                cur.execute("""
                    UPDATE geometry_periods
                    SET geom = ST_SetSRID(ST_GeomFromText(%s), 4326), updated_at = now()
                    WHERE entity_id = %s
                """, (_wkt_pg(x["wkt"]), x["entity_id"]))
                cur.execute("""
                    UPDATE entity_geo_refs
                    SET source_meta = jsonb_set(COALESCE(source_meta, '{}'::jsonb),
                                                '{source}', to_jsonb(%s::text)),
                        match_score = 0.6, updated_at = now()
                    WHERE entity_id = %s
                """, (x["src"], x["entity_id"]))
            for x in geo_deletes:
                cur.execute("UPDATE entities SET primary_geo_ref_id = NULL WHERE entity_id = %s",
                            (x["entity_id"],))
                cur.execute("DELETE FROM entity_geo_refs WHERE entity_id = %s", (x["entity_id"],))
                cur.execute("DELETE FROM geometry_periods WHERE entity_id = %s", (x["entity_id"],))
            for x in date_fixes:
                cur.execute("""
                    UPDATE entity_temporal_ranges
                    SET start_year = %s, end_year = %s, updated_at = now()
                    WHERE entity_id = %s
                """, (x["new"][0], x["new"][1], x["entity_id"]))
            conn.commit()
            print("  committed.")
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
    else:
        print("Dry run complete. Re-run with --apply to write these changes.")

    conn.close()
    return 0


def _wkt_pg(wkt: str) -> str:
    """Normalise the WKT we built ('Point(lon lat)') for ST_GeomFromText."""
    return wkt.replace("Point(", "POINT(")


if __name__ == "__main__":
    raise SystemExit(main())
