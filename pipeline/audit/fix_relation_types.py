"""Fix relationships whose endpoint types cannot fit their relationship_type.

Works on the identity audit's C7 ``endpoint_type`` flags
(``output/audit/identity-20261031/relation-flags.csv``, rules in
``pipeline/audit/relations.py``). Self-contained so another slice can reuse it.

Steps (LOCAL dev DB only):

    # 1. plan: read the live rows, merge auto rules + a hand-written decisions file,
    #    validate every result against ENDPOINT_RULES, write <out>/planned.csv
    python -m pipeline.audit.fix_relation_types plan --prefixes 01234567 \
        --out output/audit/relfix-type-a-20261101 [--decisions FILE]

    # 2. apply: pg_dump relationships + chronicle_entries, then one guarded transaction;
    #    writes applied.csv, rollback.sql, before.jsonl, rebuild-ids.txt and tests the
    #    rollback inside a transaction that is rolled back
    python -m pipeline.audit.fix_relation_types apply --out DIR

    # 3. timeline:rebuild for every entity whose relationships changed
    python -m pipeline.audit.fix_relation_types rebuild --out DIR

Decisions file (default ``<out>/decisions.txt``), one line per relationship,
``#`` comments allowed::

    <relationship id or unique prefix>|<new source>|<new target>|<new type>|<note>
    <relationship id or unique prefix>|DEL|||<note>      # delete (last resort)
    <relationship id or unique prefix>|SKIP|||<note>     # leave it, list it

``new source`` / ``new target`` are ``S`` (the current source), ``T`` (the current
target) or an entity id / unique 8+ char prefix (re-point). So ``T|S|signed_by``
reverses a row, ``S|T|authored`` retypes it, ``S|<id>|victorious_at`` re-points the
target and retypes.

Auto rules (used only where the decisions file says nothing; review them):

* reverse the row when only the reversed pair fits, for the directional types in
  ``AUTO_SWAP_TYPES`` (signed_by stored treaty-last, authored stored text-first, ...);
* reverse an event-first ``participated_in/fought_at/defeated_at/victorious_at`` row
  whose reversed pair fits.

Everything else stays ``undecided`` and is not written.

Safety: rows touching an excluded entity (merge-review survivors/losers, the
user-decision prefixes) are skipped; every write is guarded on the values read;
a change that would duplicate another row (also for symmetric types in either
direction, and against the plan's own results) becomes a delete of the duplicate,
with its chronicle_entries.primary_relationship_id moved to the kept row; a
relationship that owns geometry_periods is never re-pointed or retyped.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.audit.common import COMPOSE, REPO, connect
from pipeline.audit.relations import endpoint_problem

FLAGS = REPO / "output" / "audit" / "identity-20261031" / "relation-flags.csv"
MERGE_VERDICTS = REPO / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_HOLD_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")

EVENTS = {"event_war", "event_battle", "event_treaty", "event_rebellion", "event_natural_disaster",
          "event_tech_adoption", "event_legal_reform", "migration", "epidemic_disease"}
SYMMETRIC = {"married_to", "allied_with", "at_war_with", "sibling_of", "trades_with"}
AUTO_SWAP_TYPES = {"signed_by", "violated_by", "guaranteed_by", "mediated_by", "enforced_by", "authored",
                   "commanded_by", "located_at", "minted_by", "born_in", "died_in", "assassinated_by",
                   "member_of_dynasty", "capital_of", "stationed_at"}
EVENT_ROLE_TYPES = {"participated_in", "fought_at", "defeated_at", "victorious_at"}

PLAN_FIELDS = ["relationship_id", "action", "origin", "reason", "duplicate_of", "chronicle_refs",
               "old_type", "old_source_id", "old_source_name", "old_source_type",
               "old_target_id", "old_target_name", "old_target_type",
               "new_type", "new_source_id", "new_source_name", "new_source_type",
               "new_target_id", "new_target_name", "new_target_type", "description"]
WRITE_ACTIONS = {"swap", "retype", "swap_retype", "repoint", "delete"}


# ---------------------------------------------------------------- loading

def select_ids(prefixes: str, flags: Path = FLAGS) -> list[str]:
    with flags.open() as f:
        return [r["relationship_id"] for r in csv.DictReader(f)
                if r["check"] == "endpoint_type" and r["severity"] == "high"
                and r["relationship_id"][0] in prefixes]


def excluded_entities() -> set[str]:
    out: set[str] = set()
    if MERGE_VERDICTS.exists():
        with MERGE_VERDICTS.open() as f:
            for r in csv.DictReader(f):
                out.update(x for x in (r.get("survivor_id"), r.get("loser_id")) if x)
    return out


def is_excluded(eid: str, excl: set[str]) -> bool:
    return eid in excl or eid.startswith(USER_HOLD_PREFIXES)


def load_entities(cur) -> dict[str, dict[str, Any]]:
    cur.execute("SELECT entity_id::text, name, entity_type::text FROM entities")
    return {eid: {"id": eid, "name": name, "type": ty} for eid, name, ty in cur.fetchall()}


def load_relationships(cur) -> dict[str, tuple[str, str, str]]:
    cur.execute("SELECT relationship_id::text, source_entity_id::text, target_entity_id::text, "
                "relationship_type::text FROM relationships")
    return {rid: (s, t, ty) for rid, s, t, ty in cur.fetchall()}


def load_details(cur, ids: list[str]) -> dict[str, dict[str, Any]]:
    cur.execute("""SELECT relationship_id::text, coalesce(description, ''), start_year, end_year
                   FROM relationships WHERE relationship_id = ANY(%s::uuid[])""", (ids,))
    out = {rid: {"description": d, "start": s, "end": e} for rid, d, s, e in cur.fetchall()}
    cur.execute("""SELECT primary_relationship_id::text, count(*) FROM chronicle_entries
                   WHERE primary_relationship_id = ANY(%s::uuid[]) GROUP BY 1""", (ids,))
    for rid, n in cur.fetchall():
        out[rid]["chron"] = n
    cur.execute("""SELECT relationship_id::text, count(*) FROM geometry_periods
                   WHERE relationship_id = ANY(%s::uuid[]) GROUP BY 1""", (ids,))
    for rid, n in cur.fetchall():
        out[rid]["geo"] = n
    return out


# ---------------------------------------------------------------- decisions

def parse_decisions(path: Path | None) -> list[list[str]]:
    if not path or not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = (line.split("|") + ["", "", "", ""])[:5]
        rows.append([p.strip() for p in parts])
    return rows


def resolve_prefix(token: str, universe: list[str], what: str) -> str:
    hits = [x for x in universe if x.startswith(token)]
    if len(hits) != 1:
        raise SystemExit(f"{what} prefix {token!r} matches {len(hits)} ids")
    return hits[0]


def auto_decision(src_type: str, tgt_type: str, rtype: str) -> tuple[str, str, str, str] | None:
    """('T','S',type,reason) when a mechanical reversal fits, else None."""
    if endpoint_problem(rtype, tgt_type, src_type) is not None:
        return None
    if rtype in AUTO_SWAP_TYPES:
        return ("T", "S", rtype, f"auto: {rtype} stored backwards")
    if rtype in EVENT_ROLE_TYPES and src_type in EVENTS and tgt_type not in EVENTS:
        return ("T", "S", rtype, f"auto: event-first {rtype} reversed")
    return None


def classify(old: tuple[str, str, str], new: tuple[str, str, str]) -> str:
    (os_, ot, oty), (ns, nt, nty) = old, new
    if (ns, nt) == (os_, ot):
        return "retype" if nty != oty else "noop"
    if (ns, nt) == (ot, os_):
        return "swap" if nty == oty else "swap_retype"
    return "repoint"


# ---------------------------------------------------------------- plan

def plan(out: Path, prefixes: str, decisions_path: Path | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    ids = select_ids(prefixes)
    excl = excluded_entities()
    conn = connect()
    cur = conn.cursor()
    ents = load_entities(cur)
    rels = load_relationships(cur)
    details = load_details(cur, [i for i in ids if i in rels])
    conn.close()

    manual: dict[str, list[str]] = {}
    for parts in parse_decisions(decisions_path):
        rid = resolve_prefix(parts[0], ids, "relationship")
        if rid in manual:
            raise SystemExit(f"two decisions for {rid}")
        manual[rid] = parts[1:]
    ent_ids = list(ents)

    def ent_token(tok: str, cur_src: str, cur_tgt: str) -> str:
        if tok == "S":
            return cur_src
        if tok == "T":
            return cur_tgt
        return tok if tok in ents else resolve_prefix(tok, ent_ids, "entity")

    rows: list[dict[str, Any]] = []
    for rid in ids:
        base = {"relationship_id": rid, "duplicate_of": "", "chronicle_refs": 0, "description": ""}
        if rid not in rels:
            rows.append({**base, "action": "skip", "origin": "", "reason": "relationship no longer exists"})
            continue
        s, t, ty = rels[rid]
        d = details.get(rid, {})
        base.update(chronicle_refs=d.get("chron", 0), description=d.get("description", "")[:200],
                    old_type=ty, old_source_id=s, old_source_name=ents[s]["name"], old_source_type=ents[s]["type"],
                    old_target_id=t, old_target_name=ents[t]["name"], old_target_type=ents[t]["type"])
        if endpoint_problem(ty, ents[s]["type"], ents[t]["type"]) is None:
            rows.append({**base, "action": "skip", "origin": "", "reason": "no longer flagged (already fixed)"})
            continue
        if rid in manual:
            ns_tok, nt_tok, nty, note = manual[rid]
            origin = "manual"
            if ns_tok == "DEL":
                rows.append({**base, "action": "delete", "origin": origin, "reason": note})
                continue
            if ns_tok == "SKIP":
                rows.append({**base, "action": "skip", "origin": origin, "reason": "listed: " + note})
                continue
            new = (ent_token(ns_tok, s, t), ent_token(nt_tok, s, t), nty)
        else:
            auto = auto_decision(ents[s]["type"], ents[t]["type"], ty)
            if not auto:
                rows.append({**base, "action": "skip", "origin": "", "reason": "undecided"})
                continue
            origin, note = "auto", auto[3]
            new = (ent_token(auto[0], s, t), ent_token(auto[1], s, t), auto[2])
        ns, nt, nty = new
        row = {**base, "origin": origin, "reason": note, "new_type": nty,
               "new_source_id": ns, "new_source_name": ents[ns]["name"], "new_source_type": ents[ns]["type"],
               "new_target_id": nt, "new_target_name": ents[nt]["name"], "new_target_type": ents[nt]["type"]}
        action = classify((s, t, ty), new)
        problem = endpoint_problem(nty, ents[ns]["type"], ents[nt]["type"])
        if nty not in ENUM_TYPES:
            row.update(action="skip", reason=f"invalid type {nty!r}; " + note)
        elif action == "noop":
            row.update(action="skip", reason="decision changes nothing; " + note)
        elif ns == nt:
            row.update(action="skip", reason="self-link; " + note)
        elif problem:
            row.update(action="skip", reason=f"still invalid ({problem}); " + note)
        elif d.get("geo") and (action != "swap" or ty == "located_at"):
            row.update(action="skip", reason="owns derived geometry_periods; " + note)
        else:
            row["action"] = action
        rows.append(row)

    # exclusions (old and new endpoints)
    for row in rows:
        if row["action"] in WRITE_ACTIONS:
            touched = {row.get("old_source_id"), row.get("old_target_id"),
                       row.get("new_source_id"), row.get("new_target_id")} - {None, ""}
            hit = [e for e in touched if is_excluded(e, excl)]
            if hit:
                row["reason"] = f"excluded entity {hit[0][:8]} (merge review / user decision); " + row["reason"]
                row["action"] = "skip"

    # duplicates: against the final state of the whole table, plan included
    final: dict[str, tuple[str, str, str]] = dict(rels)
    planned_rids = {r["relationship_id"] for r in rows if r["action"] in WRITE_ACTIONS}
    for row in rows:
        if row["action"] == "delete":
            final.pop(row["relationship_id"], None)
    claimed: dict[tuple[str, str, str], str] = {}
    for rid, trip in final.items():
        if rid not in planned_rids:
            claimed.setdefault(trip, rid)
    for row in rows:
        if row["action"] not in WRITE_ACTIONS or row["action"] == "delete":
            continue
        trip = (row["new_source_id"], row["new_target_id"], row["new_type"])
        keys = [trip] + ([(trip[1], trip[0], trip[2])] if trip[2] in SYMMETRIC else [])
        dup = next((claimed[k] for k in keys if k in claimed), None)
        if dup:
            row["duplicate_of"] = dup
            row["reason"] = f"duplicate of {dup[:8]} after fix; " + row["reason"]
            row["action"] = "delete"
        else:
            claimed[trip] = row["relationship_id"]

    with (out / "planned.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PLAN_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in PLAN_FIELDS})
    c = Counter(r["action"] for r in rows)
    print(f"planned {len(rows)} rows -> {out / 'planned.csv'}: {dict(c)}")
    sk = Counter(r["reason"].split(";")[0].split(":")[0] for r in rows if r["action"] == "skip")
    print("skip reasons:", dict(sk))


ENUM_TYPES: set[str] = set()


def _load_enum() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT unnest(enum_range(NULL::relationship_type))::text")
    ENUM_TYPES.update(r[0] for r in cur.fetchall())
    conn.close()


# ---------------------------------------------------------------- apply

def pg_dump(out: Path, tables: list[str]) -> Path:
    stamp = subprocess.run(["date", "+%Y%m%dT%H%M%S"], capture_output=True, text=True).stdout.strip()
    path = out / f"backup-{'-'.join(tables)}-{stamp}.sql.gz"
    cmd = COMPOSE + ["exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-d", "history-mapped"]
    for t in tables:
        cmd += ["-t", f"public.{t}"]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    with gzip.open(path, "wb") as f:
        f.write(proc.stdout)
    print(f"backup {path} ({len(proc.stdout) // 1024} KiB)")
    return path


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def _dollar(s: str) -> str:
    tag = "$rel$"
    assert tag not in s
    return f"{tag}{s}{tag}"


def apply(out: Path, dry_run: bool = False) -> None:
    """Apply planned.csv in one transaction. ``dry_run`` runs every write, then the
    generated rollback inside the same transaction, checks it, and rolls back."""
    rows = [r for r in csv.DictReader((out / "planned.csv").open()) if r["action"] in WRITE_ACTIONS]
    if not rows:
        print("nothing to apply")
        return
    if not dry_run:
        pg_dump(out, ["relationships", "chronicle_entries"])
    conn = connect(read_only=False)
    cur = conn.cursor()
    applied: list[dict[str, Any]] = []
    rollback_inserts: list[str] = []
    rollback_chron: list[str] = []
    rollback_updates: list[str] = []
    sfx = ".dry" if dry_run else ""
    before = open(out / f"before.jsonl{sfx}", "w")
    chron_moved = open(out / f"chronicle-moved.jsonl{sfx}", "w")
    done_updates: set[str] = set()
    ents_type = {}
    cur.execute("SELECT entity_id::text, entity_type::text FROM entities")
    ents_type.update(cur.fetchall())

    def snapshot(rid: str) -> dict[str, Any] | None:
        cur.execute("SELECT to_jsonb(r) FROM relationships r WHERE relationship_id = %s FOR UPDATE", (rid,))
        hit = cur.fetchone()
        return hit[0] if hit else None

    updates = [r for r in rows if r["action"] != "delete"]
    deletes = [r for r in rows if r["action"] == "delete"]
    for r in updates + deletes:
        rid = r["relationship_id"]
        old = (r["old_source_id"], r["old_target_id"], r["old_type"])
        rec = {"relationship_id": rid, "action": r["action"], "status": "", "detail": "",
               "old": "|".join(old), "new": "", "reason": r["reason"]}
        snap = snapshot(rid)
        if not snap or (snap["source_entity_id"], snap["target_entity_id"], snap["relationship_type"]) != old:
            rec.update(status="skipped", detail="row changed or gone since planning")
            applied.append(rec)
            continue
        before.write(json.dumps(snap) + "\n")
        if r["action"] == "delete":
            dup = r["duplicate_of"]
            if dup and dup in {x["relationship_id"] for x in updates} and dup not in done_updates:
                rec.update(status="skipped", detail=f"kept row {dup[:8]} was not updated")
                applied.append(rec)
                continue
            if dup:
                cur.execute("SELECT 1 FROM relationships WHERE relationship_id = %s", (dup,))
                if not cur.fetchone():
                    rec.update(status="skipped", detail=f"kept row {dup[:8]} is gone")
                    applied.append(rec)
                    continue
            cur.execute("""UPDATE chronicle_entries SET primary_relationship_id = %s
                           WHERE primary_relationship_id = %s RETURNING entry_id::text""", (dup or None, rid))
            moved = [x[0] for x in cur.fetchall()]
            for eid in moved:
                chron_moved.write(json.dumps({"entry_id": eid, "was": rid, "now": dup or None}) + "\n")
                rollback_chron.append(
                    f"UPDATE chronicle_entries SET primary_relationship_id = {_lit(rid)} "
                    f"WHERE entry_id = {_lit(eid)} AND primary_relationship_id IS NOT DISTINCT FROM {_lit(dup or None)};")
            cur.execute("""DELETE FROM relationships WHERE relationship_id = %s AND source_entity_id = %s
                           AND target_entity_id = %s AND relationship_type = %s""", (rid, *old))
            if cur.rowcount != 1:
                raise RuntimeError(f"delete of {rid} hit {cur.rowcount} rows")
            rollback_inserts.append(
                "INSERT INTO relationships SELECT * FROM jsonb_populate_record(NULL::relationships, "
                f"{_dollar(json.dumps(snap))}::jsonb) ON CONFLICT (relationship_id) DO NOTHING;")
            rec.update(status="applied", detail=f"chronicle refs moved: {len(moved)}"
                       + (f" to {dup[:8]}" if dup else " (cleared)"))
        else:
            new = (r["new_source_id"], r["new_target_id"], r["new_type"])
            problem = endpoint_problem(new[2], ents_type.get(new[0], "?"), ents_type.get(new[1], "?"))
            if problem:  # an entity was retyped since planning
                rec.update(status="skipped", detail=f"now invalid: {problem}")
                applied.append(rec)
                continue
            cur.execute("""UPDATE relationships SET source_entity_id = %s, target_entity_id = %s,
                               relationship_type = %s
                           WHERE relationship_id = %s AND source_entity_id = %s AND target_entity_id = %s
                             AND relationship_type = %s
                           RETURNING start_year, end_year""", (*new, rid, *old))
            got = cur.fetchone()
            if cur.rowcount != 1 or got != (snap["start_year"], snap["end_year"]):
                raise RuntimeError(f"update of {rid} did not behave: {got}")
            rollback_updates.append(
                f"UPDATE relationships SET source_entity_id = {_lit(old[0])}, target_entity_id = {_lit(old[1])}, "
                f"relationship_type = {_lit(old[2])} WHERE relationship_id = {_lit(rid)} "
                f"AND source_entity_id = {_lit(new[0])} AND target_entity_id = {_lit(new[1])} "
                f"AND relationship_type = {_lit(new[2])};")
            rec.update(status="applied", new="|".join(new))
            done_updates.add(rid)
        applied.append(rec)
    before.close()
    chron_moved.close()
    rollback = ["-- Rollback for fix_relation_types apply (guarded inverses).", "BEGIN;",
                *rollback_inserts, *rollback_chron, *rollback_updates, "COMMIT;"]
    (out / f"rollback.sql{sfx}").write_text("\n".join(rollback) + "\n")
    if dry_run:
        print("dry run:", dict(Counter((a["action"], a["status"]) for a in applied)))
        _check_rollback(cur, out / f"rollback.sql{sfx}", out / f"before.jsonl{sfx}",
                        out / f"chronicle-moved.jsonl{sfx}")
        conn.rollback()
        conn.close()
        return
    conn.commit()
    fields = ["relationship_id", "action", "status", "detail", "old", "new", "reason"]
    with (out / "applied.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(applied)
    ids: set[str] = set()
    plan_by = {r["relationship_id"]: r for r in rows}
    for a in applied:
        if a["status"] == "applied":
            p = plan_by[a["relationship_id"]]
            ids.update(x for x in (p["old_source_id"], p["old_target_id"], p.get("new_source_id"),
                                   p.get("new_target_id")) if x)
    (out / "rebuild-ids.txt").write_text("\n".join(sorted(ids)) + "\n")
    print("applied:", dict(Counter((a["action"], a["status"]) for a in applied)))
    print(f"entities to rebuild: {len(ids)}")
    rollback_test(out)
    conn.close()


def _check_rollback(cur, sql_path: Path, before_path: Path, chron_path: Path) -> None:
    sql = sql_path.read_text().replace("BEGIN;", "").replace("COMMIT;", "")
    snaps = [json.loads(l) for l in before_path.open()]
    moved = [json.loads(l) for l in chron_path.open()] if chron_path.exists() else []
    cur.execute(sql)
    bad = 0
    for s in snaps:
        cur.execute("SELECT to_jsonb(r) FROM relationships r WHERE relationship_id = %s", (s["relationship_id"],))
        got = cur.fetchone()
        if not got or got[0] != s:
            bad += 1
    cbad = 0
    for m in moved:
        cur.execute("SELECT primary_relationship_id::text FROM chronicle_entries WHERE entry_id = %s", (m["entry_id"],))
        got = cur.fetchone()
        if not got or got[0] != m["was"]:
            cbad += 1
    print(f"rollback test: {len(snaps) - bad}/{len(snaps)} relationships restored exactly; "
          f"{len(moved) - cbad}/{len(moved)} chronicle refs restored")


def rollback_test(out: Path) -> None:
    """Run rollback.sql in a transaction, compare with before.jsonl, then roll back."""
    conn = connect(read_only=False)
    try:
        _check_rollback(conn.cursor(), out / "rollback.sql", out / "before.jsonl", out / "chronicle-moved.jsonl")
    finally:
        conn.rollback()
        conn.close()


def rebuild(out: Path, jobs: int = 4) -> None:
    """php artisan timeline:rebuild <id> for each id in rebuild-ids.txt (one exec, ``jobs`` in parallel)."""
    ids = [l.strip() for l in (out / "rebuild-ids.txt").read_text().splitlines() if l.strip()]
    script = (f'xargs -P {jobs} -I{{}} sh -c \'php artisan timeline:rebuild "{{}}" >/dev/null 2>&1 '
              '&& echo OK || echo "FAIL {}"\'')
    proc = subprocess.run(COMPOSE + ["exec", "-T", "app", "sh", "-c", script],
                          input="\n".join(ids) + "\n", text=True, capture_output=True)
    lines = proc.stdout.splitlines()
    fails = [l for l in lines if l.startswith("FAIL")]
    (out / "rebuild.log").write_text(proc.stdout + proc.stderr)
    print(f"timeline:rebuild ok {sum(1 for l in lines if l == 'OK')} / {len(ids)}, failed {len(fails)}")
    for l in fails[:20]:
        print(l)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m pipeline.audit.fix_relation_types")
    ap.add_argument("cmd", choices=["plan", "apply", "rollback-test", "rebuild"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefixes", default="0123456789abcdef", help="first hex char of relationship_id")
    ap.add_argument("--decisions", type=Path, default=None, help="default: <out>/decisions.txt")
    ap.add_argument("--dry-run", action="store_true", help="apply: write, test the rollback, roll back")
    a = ap.parse_args(argv)
    out = a.out if a.out.is_absolute() else REPO / a.out
    if a.cmd == "plan":
        _load_enum()
        plan(out, a.prefixes, a.decisions or out / "decisions.txt")
    elif a.cmd == "apply":
        apply(out, dry_run=a.dry_run)
    elif a.cmd == "rollback-test":
        rollback_test(out)
    else:
        rebuild(out)


if __name__ == "__main__":
    sys.exit(main())
