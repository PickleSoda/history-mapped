"""Resolve the identity audit's S1 rows ("class contradicts type") from a
hand-reviewed plan (2026-11-01 cleanup).

Each S1 row was read by hand and given one decision in ``planned.csv``:

  retype     the QID is right and ``entity_type`` is wrong: set the new type
             (and its ``entity_group``, which the map and API filter on);
  set_qid    the type is right and the QID names something else; the audit's
             C3 search found one unique, certain item not held by another row;
  clear_qid  the type is right and the QID is wrong, with no certain
             replacement: the audit's way (old id into
             ``attributes._rejected_wikidata_id``, ``verification_status`` to
             ``needs_review``, flag ``identity_audit:qid_cleared``);
  leave      no change (listed with the reason).

Every write is guarded on the value in the plan (``... WHERE pk = .. AND col =
old``), so a row another writer changed since is skipped, not overwritten.
All writes go in one transaction. ``--apply`` first pg_dumps ``entities``
into the output folder, then writes ``applied.csv`` and ``rollback.sql``
(guarded inverses of exactly what was applied). ``--test-rollback`` runs
``rollback.sql`` inside a transaction, checks that every applied row is back
to its old values, and rolls back.

  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.s1_types            # dry run
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.s1_types --apply
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.s1_types --test-rollback
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from pipeline.audit.apply import backup
from pipeline.audit.common import REPO, connect, write_csv

OUT = REPO / "output" / "audit" / "s1-types-20261101"
FLAG = "identity_audit:qid_cleared"
DECISIONS = ("retype", "set_qid", "clear_qid", "leave")
APPLIED_FIELDS = ["ts", "entity_id", "name", "decision", "column", "old", "new", "status", "reason"]

# entity_type -> entity_group (api/app/Enums/EntityType.php::group)
GROUPS = {
    **dict.fromkeys(["political_entity", "dynasty", "person", "military_unit", "diplomatic_relationship",
                     "social_class"], "POLITY"),
    **dict.fromkeys(["city", "infrastructure_monument", "extraction_infra", "educational_institution"], "PLACE"),
    **dict.fromkeys(["event_war", "event_battle", "event_treaty", "event_rebellion", "event_natural_disaster",
                     "event_tech_adoption", "event_legal_reform", "migration", "epidemic_disease"], "EVENT"),
    **dict.fromkeys(["trade_route", "natural_resource", "currency_monetary_system"], "ECONOMY"),
    **dict.fromkeys(["cultural_work", "intellectual_movement", "archaeological_culture", "language",
                     "religious_text", "legal_code", "religious_movement", "technology"], "CULTURE"),
}
QID_RE = re.compile(r"^Q[1-9]\d*$")


def load_plan(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        plan = list(csv.DictReader(fh))
    for p in plan:
        d = p["decision"]
        if d not in DECISIONS:
            raise SystemExit(f"{p['entity_id']}: unknown decision {d!r}")
        if d == "retype" and p["new_type"] not in GROUPS:
            raise SystemExit(f"{p['entity_id']}: {p['new_type']!r} is not one of the 30 types")
        if d == "set_qid" and not QID_RE.match(p["new_qid"]):
            raise SystemExit(f"{p['entity_id']}: bad new_qid {p['new_qid']!r}")
    return plan


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def _current(cur, eid: str, lock: bool):
    cur.execute("SELECT entity_type::text, entity_group::text, wikidata_id, verification_status::text, attributes, "
                "updated_at FROM entities WHERE entity_id = %s" + (" FOR UPDATE" if lock else ""), (eid,))
    return cur.fetchone()


def run(conn, plan: list[dict[str, str]], *, apply: bool) -> tuple[list[dict[str, Any]], list[str]]:
    """Check (and with ``apply``, write) every non-leave line. Returns the log
    and the rollback statements (newest last)."""
    cur = conn.cursor()
    log: list[dict[str, Any]] = []
    rollback: list[str] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    def entry(p, column, old, new, status="applied"):
        log.append({"ts": ts, "entity_id": p["entity_id"], "name": p["name"], "decision": p["decision"],
                    "column": column, "old": old, "new": new, "status": status, "reason": p["reason"]})

    for p in plan:
        if p["decision"] == "leave":
            continue
        eid = p["entity_id"]
        got = _current(cur, eid, apply)
        if not got:
            entry(p, "-", None, None, "skipped: row gone")
            continue
        etype, group, qid, status, attrs, updated = got
        attrs = attrs or {}
        old_qid = p["old_qid"] or None
        if etype != p["old_type"] or qid != old_qid:
            entry(p, "-", f"{p['old_type']}/{old_qid}", f"{etype}/{qid}", "skipped: row changed since the plan")
            continue
        upd = _lit(str(updated)) if updated else "NULL"
        if p["decision"] == "retype":
            new, new_group = p["new_type"], GROUPS[p["new_type"]]
            if apply:
                cur.execute("UPDATE entities SET entity_type = %s::entity_type, entity_group = %s::entity_group, "
                            "updated_at = now() WHERE entity_id = %s AND entity_type = %s::entity_type",
                            (new, new_group, eid, etype))
            entry(p, "entity_type", etype, new)
            if new_group != group:
                entry(p, "entity_group", group, new_group)
            rollback.append(f"UPDATE entities SET entity_type = {_lit(etype)}, entity_group = {_lit(group)}, "
                            f"updated_at = {upd} WHERE entity_id = {_lit(eid)} AND entity_type = {_lit(new)} "
                            f"AND entity_group = {_lit(new_group)};")
        elif p["decision"] == "set_qid":
            new = p["new_qid"]
            cur.execute("SELECT entity_id::text FROM entities WHERE wikidata_id = %s AND entity_id <> %s LIMIT 1",
                        (new, eid))
            holder = cur.fetchone()
            if holder:
                entry(p, "wikidata_id", qid, new, f"skipped: {new} is on row {holder[0]}")
                continue
            if attrs.get("_rejected_wikidata_id") == new:
                entry(p, "wikidata_id", qid, new, f"skipped: {new} was rejected for this row")
                continue
            if apply:
                cur.execute("UPDATE entities SET wikidata_id = %s, updated_at = now() WHERE entity_id = %s "
                            "AND wikidata_id IS NOT DISTINCT FROM %s", (new, eid, qid))
            entry(p, "wikidata_id", qid, new)
            rollback.append(f"UPDATE entities SET wikidata_id = {_lit(qid)}, updated_at = {upd} "
                            f"WHERE entity_id = {_lit(eid)} AND wikidata_id = {_lit(new)};")
        elif p["decision"] == "clear_qid":
            prev_rej = attrs.get("_rejected_wikidata_id")
            had_flags = "validation_flags" in attrs
            flags = list(attrs.get("validation_flags") or [])
            if apply:
                cur.execute("UPDATE entities SET wikidata_id = NULL, updated_at = now() WHERE entity_id = %s "
                            "AND wikidata_id = %s", (eid, qid))
                cur.execute("UPDATE entities SET attributes = attributes || jsonb_build_object("
                            "'_rejected_wikidata_id', %s::text) WHERE entity_id = %s", (qid, eid))
            entry(p, "wikidata_id", qid, None)
            entry(p, "attributes._rejected_wikidata_id", prev_rej, qid)
            # inverses (applied newest-first): rejected id, flag, status, QID
            if prev_rej is None:
                rollback.append(f"UPDATE entities SET attributes = attributes - '_rejected_wikidata_id' "
                                f"WHERE entity_id = {_lit(eid)} AND attributes->>'_rejected_wikidata_id' = {_lit(qid)};")
            else:
                rollback.append(f"UPDATE entities SET attributes = jsonb_set(attributes, '{{_rejected_wikidata_id}}', "
                                f"to_jsonb({_lit(prev_rej)}::text)) WHERE entity_id = {_lit(eid)} "
                                f"AND attributes->>'_rejected_wikidata_id' = {_lit(qid)};")
            if FLAG not in flags:
                if apply:
                    cur.execute("UPDATE entities SET attributes = jsonb_set(attributes, '{validation_flags}', "
                                "coalesce(attributes->'validation_flags', '[]'::jsonb) || to_jsonb(%s::text)) "
                                "WHERE entity_id = %s", (FLAG, eid))
                entry(p, "attributes.validation_flags", json.dumps(flags), json.dumps([*flags, FLAG]))
                if had_flags:
                    rollback.append(f"UPDATE entities SET attributes = jsonb_set(attributes, '{{validation_flags}}', "
                                    f"(attributes->'validation_flags') - {_lit(FLAG)}) WHERE entity_id = {_lit(eid)} "
                                    f"AND attributes->'validation_flags' ? {_lit(FLAG)};")
                else:
                    rollback.append(f"UPDATE entities SET attributes = attributes - 'validation_flags' "
                                    f"WHERE entity_id = {_lit(eid)} AND attributes->'validation_flags' = "
                                    f"{_lit(json.dumps([FLAG]))}::jsonb;")
            if status != "needs_review":
                if apply:
                    cur.execute("UPDATE entities SET verification_status = 'needs_review' WHERE entity_id = %s "
                                "AND verification_status = %s::verification_status", (eid, status))
                entry(p, "verification_status", status, "needs_review")
                rollback.append(f"UPDATE entities SET verification_status = {_lit(status)} "
                                f"WHERE entity_id = {_lit(eid)} AND verification_status = 'needs_review';")
            rollback.append(f"UPDATE entities SET wikidata_id = {_lit(qid)}, updated_at = {upd} "
                            f"WHERE entity_id = {_lit(eid)} AND wikidata_id IS NULL;")
    return log, rollback


def write_outputs(out: Path, log: list[dict[str, Any]], rollback: list[str]) -> None:
    """Append this batch to applied.csv and put its inverses on top of rollback.sql."""
    applied = out / "applied.csv"
    previous: list[dict[str, Any]] = []
    if applied.exists():
        with applied.open(encoding="utf-8") as fh:
            previous = list(csv.DictReader(fh))
    write_csv(applied, previous + log, APPLIED_FIELDS)
    rb = out / "rollback.sql"
    old_body = rb.read_text().split("\\set ON_ERROR_STOP on\n", 1)[-1] if rb.exists() else ""
    n = len({l["entity_id"] for l in log if l["status"] == "applied"})
    batch = (f"-- batch {log[0]['ts'] if log else ''}: {n} entities\nBEGIN;\n" + "\n".join(reversed(rollback))
             + "\nCOMMIT;\n")
    rb.write_text(
        "-- Rollback of the S1 type/QID fixes of 2026-11-01 (generated by pipeline/audit/s1_types.py;\n"
        "-- newest batch first).\n"
        f"-- Run: docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped -d history-mapped "
        f"-f - < {rb.relative_to(REPO)}\n"
        "-- Every statement is guarded on the value written; rows changed since are left alone.\n"
        "\\set ON_ERROR_STOP on\n" + batch + old_body)


def test_rollback(conn, out: Path) -> None:
    """Run rollback.sql in a transaction, compare with the old values, roll back."""
    with (out / "applied.csv").open(encoding="utf-8") as fh:
        applied = [r for r in csv.DictReader(fh) if r["status"] == "applied"]
    sql = (out / "rollback.sql").read_text()
    stmts = [s for s in sql.split("\n") if s.startswith("UPDATE ")]
    conn.read_only = False
    cur = conn.cursor()
    try:
        for s in stmts:
            cur.execute(s)
        bad = 0
        for r in applied:
            col = r["column"]
            cur.execute("SELECT entity_type::text, entity_group::text, wikidata_id, verification_status::text, "
                        "attributes FROM entities WHERE entity_id = %s", (r["entity_id"],))
            etype, group, qid, status, attrs = cur.fetchone()
            attrs = attrs or {}
            now = {"entity_type": etype, "entity_group": group, "wikidata_id": qid, "verification_status": status,
                   "attributes._rejected_wikidata_id": attrs.get("_rejected_wikidata_id"),
                   "attributes.validation_flags": json.dumps(list(attrs.get("validation_flags") or []))}[col]
            if (now or "") != (r["old"] or ""):
                bad += 1
                print(f"  not restored: {r['entity_id']} {col}: now {now!r}, old {r['old']!r}")
        print(f"rollback test: {len(stmts)} statements, {len(applied)} applied values, {bad} not restored")
    finally:
        conn.rollback()
        conn.read_only = True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", type=Path, default=OUT / "planned.csv")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--test-rollback", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated decisions to run (default: all)")
    args = ap.parse_args(argv)
    conn = connect(read_only=True)
    if args.test_rollback:
        test_rollback(conn, args.out)
        return 0
    plan = load_plan(args.plan)
    if args.only:
        keep = set(args.only.split(","))
        plan = [p for p in plan if p["decision"] in keep]
    if not args.apply:
        log, _ = run(conn, plan, apply=False)
        conn.rollback()
    else:
        path = backup(args.out, ["entities"])
        print(f"backup: {path}")
        conn.rollback()
        conn.read_only = False
        try:
            log, rollback = run(conn, plan, apply=True)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        write_outputs(args.out, log, rollback)
    from collections import Counter
    print(Counter(p["decision"] for p in plan))
    print(Counter((l["decision"], l["status"].split(":")[0]) for l in log if l["column"] in
                  ("entity_type", "wikidata_id", "-")))
    for l in log:
        if l["status"] != "applied":
            print(f"  {l['status']}: {l['name']} ({l['entity_id'][:8]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
