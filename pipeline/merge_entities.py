#!/usr/bin/env python3
"""Merge duplicate entities that denote the same real-world thing.

The free-model batch sometimes split one subject into two rows — e.g. "Italy" the
country ended up as a `city` row (carrying ALL the real relationships: Rome
capital_of Italy, Marco Polo born_in Italy, …) that resolved to a *wrong* QID,
plus a separate `political_entity` row with the *correct* QID (Q38) but zero
relationships. The atlas then shows two "Italy"s.

This merges them: for each name it keeps the row with the MOST relationships (the
one actually wired into the graph) and folds the duplicates into it —

  • re-points relationships (source & target) with dedup + self-loop removal,
  • re-points chronicle_entry_entities (RESTRICT FK) with dedup,
  • deletes the loser (CASCADE cleans its geo/temporal/timeline/aliases).

The surviving row keeps its entity_id, so nothing it's wired to breaks. Its
QID/type are usually still the wrong ones from the relation-rich row — fix those
afterwards with `reresolve_entities` (pin the right QID, e.g. Italy=Q38).

Dry-run by default; --apply writes in one transaction.

    pipeline/.venv/bin/python3 -m pipeline.merge_entities Italy England
    pipeline/.venv/bin/python3 -m pipeline.merge_entities --apply Italy England
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"


def rel_count(cur, eid: str) -> int:
    cur.execute("SELECT COUNT(*) FROM relationships WHERE source_entity_id=%s OR target_entity_id=%s", (eid, eid))
    return cur.fetchone()[0]


def merge(cur, survivor: str, loser: str) -> None:
    # Relationships: drop loser rels that would collide with an existing survivor
    # rel, re-point the rest, then drop any self-loops the merge created.
    cur.execute("""
        DELETE FROM relationships l
        WHERE (l.source_entity_id=%(loser)s OR l.target_entity_id=%(loser)s)
          AND EXISTS (
            SELECT 1 FROM relationships s
            WHERE s.relationship_type=l.relationship_type
              AND (CASE WHEN l.source_entity_id=%(loser)s THEN %(surv)s ELSE l.source_entity_id END)=s.source_entity_id
              AND (CASE WHEN l.target_entity_id=%(loser)s THEN %(surv)s ELSE l.target_entity_id END)=s.target_entity_id)
    """, {"loser": loser, "surv": survivor})
    cur.execute("UPDATE relationships SET source_entity_id=%s WHERE source_entity_id=%s", (survivor, loser))
    cur.execute("UPDATE relationships SET target_entity_id=%s WHERE target_entity_id=%s", (survivor, loser))
    cur.execute("DELETE FROM relationships WHERE source_entity_id=%s AND target_entity_id=%s", (survivor, survivor))

    # chronicle_entry_entities (RESTRICT): dedup within an entry, then re-point.
    cur.execute("""
        DELETE FROM chronicle_entry_entities l
        WHERE l.entity_id=%(loser)s
          AND EXISTS (SELECT 1 FROM chronicle_entry_entities s
                      WHERE s.entity_id=%(surv)s AND s.entry_id=l.entry_id)
    """, {"loser": loser, "surv": survivor})
    cur.execute("UPDATE chronicle_entry_entities SET entity_id=%s WHERE entity_id=%s", (survivor, loser))

    # entity_timeline_entries reference entity three ways (CASCADE/SET NULL on the
    # primary). Re-point the secondary refs so we don't null useful links.
    cur.execute("UPDATE entity_timeline_entries SET location_entity_id=%s WHERE location_entity_id=%s", (survivor, loser))
    cur.execute("UPDATE entity_timeline_entries SET related_entity_id=%s WHERE related_entity_id=%s", (survivor, loser))

    # Delete the loser — CASCADE removes its geo_refs/temporal_ranges/aliases/tags/
    # timeline primary rows.
    cur.execute("DELETE FROM entities WHERE entity_id=%s", (loser,))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", nargs="+", help="entity names whose duplicate rows should be merged")
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    actions: list[tuple] = []

    for name in args.names:
        cur.execute("SELECT entity_id, entity_type::text, wikidata_id FROM entities WHERE name=%s", (name,))
        rows = cur.fetchall()
        if len(rows) < 2:
            print(f"  {name}: {len(rows)} row(s) — nothing to merge")
            continue
        ranked = sorted(rows, key=lambda r: rel_count(cur, r[0]), reverse=True)
        survivor = ranked[0]
        for loser in ranked[1:]:
            actions.append((name, survivor, loser))

    print("\n" + "=" * 90)
    print(f"MERGE PLAN ({len(actions)})" + ("  — DRY RUN" if not args.apply else "  — APPLYING"))
    print("=" * 90)
    for name, surv, loser in actions:
        print(f"{name:14s} keep {str(surv[0])[:8]} ({surv[1]}, {surv[2]}, {rel_count(cur, surv[0])} rels)"
              f"  ⨉ drop {str(loser[0])[:8]} ({loser[1]}, {loser[2]}, {rel_count(cur, loser[0])} rels)")

    if args.apply and actions:
        try:
            for _, surv, loser in actions:
                merge(cur, surv[0], loser[0])
            conn.commit()
            print(f"\nMerged {len(actions)} duplicate(s).")
        except Exception:
            conn.rollback()
            print("\nROLLED BACK on error.")
            raise
    elif not args.apply:
        print("\nDry run — re-run with --apply to write. Then fix survivor QID/type via reresolve_entities.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
