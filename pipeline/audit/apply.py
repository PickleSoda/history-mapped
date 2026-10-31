"""C9: apply the safe fixes, with a backup, a change log and rollback SQL.

Safe fix classes (nothing else is ever written):
  set_qid      — set a missing/wrong QID (high-confidence C3 winner, a redirect
                 target, or a hand-verified pin);
  clear_qid    — clear a QID judged wrong when no correct one is found; the
                 old id goes to attributes._rejected_wikidata_id (the importer's
                 convention) so it is not re-attached;
  rename       — a mechanical C5 rename (the old name kept as an alias when the
                 normalised tokens change);
  add_alias    — an alias row;
  needs_review — verification_status = needs_review, with the reason appended to
                 attributes.validation_flags as 'identity_audit:<reason>'.

Before the first write the affected tables are dumped with pg_dump
(``backup-<time>.sql.gz``). Every change is guarded on the value the audit
read, so a row someone else changed since is skipped, not overwritten. All
changes go in one transaction; ``applied.csv`` and ``rollback.sql`` are written
from what the transaction actually changed.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from pipeline.audit.common import COMPOSE, write_csv

APPLIED_FIELDS = ["ts", "fix", "table", "id", "column", "old", "new", "reason", "evidence", "status"]
BACKUP_TABLES = ["entities", "entity_aliases"]


def backup(out_dir: Path, tables: list[str] = BACKUP_TABLES) -> Path:
    """pg_dump the affected tables (data + schema) into backup-<time>.sql.gz."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"backup-{stamp}.sql.gz"
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-d", "history-mapped",
           "--no-owner", *[a for t in tables for a in ("-t", f"public.{t}")]]
    with gzip.open(path, "wb") as fh:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0 or not proc.stdout:
            raise SystemExit(f"pg_dump failed: {proc.stderr.decode()[:500]}")
        fh.write(proc.stdout)
    return path


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False, sort_keys=True).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def apply_changes(conn, changes: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    """Apply ``changes`` in one transaction and log them.

    A change: {fix, id, reason, evidence, ...} with
      set_qid / clear_qid: old_qid, new_qid
      rename: old_name, new_name, add_alias (bool)
      add_alias: alias
      needs_review: flag
    """
    conn.rollback()  # end the audit's read-only transaction (it wrote nothing)
    conn.read_only = False
    cur = conn.cursor()
    log: list[dict[str, Any]] = []
    rollback: list[str] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    def entry(fix, table, key, column, old, new, ch, status="applied"):
        log.append({"ts": ts, "fix": fix, "table": table, "id": key, "column": column,
                    "old": json.dumps(old, ensure_ascii=False, sort_keys=True) if isinstance(old, (dict, list)) else old,
                    "new": json.dumps(new, ensure_ascii=False, sort_keys=True) if isinstance(new, (dict, list)) else new,
                    "reason": ch.get("reason", ""), "evidence": ch.get("evidence", ""), "status": status})

    try:
        for ch in changes:
            eid = ch["id"]
            cur.execute("SELECT wikidata_id, name, verification_status::text, attributes, updated_at "
                        "FROM entities WHERE entity_id = %s FOR UPDATE", (eid,))
            got = cur.fetchone()
            if not got:
                entry(ch["fix"], "entities", eid, "-", None, None, ch, "skipped: row gone")
                continue
            qid, name, status, attrs, updated = got
            attrs = attrs or {}
            fix = ch["fix"]
            if fix in ("set_qid", "clear_qid"):
                if qid != ch["old_qid"]:
                    entry(fix, "entities", eid, "wikidata_id", ch["old_qid"], ch.get("new_qid"), ch,
                          f"skipped: QID is now {qid}")
                    continue
                cur.execute("UPDATE entities SET wikidata_id = %s, updated_at = now() WHERE entity_id = %s "
                            "AND wikidata_id IS NOT DISTINCT FROM %s", (ch.get("new_qid"), eid, qid))
                entry(fix, "entities", eid, "wikidata_id", qid, ch.get("new_qid"), ch)
                rollback.append(f"UPDATE entities SET wikidata_id = {_lit(qid)}, updated_at = {_lit(str(updated) if updated else None)} "
                                f"WHERE entity_id = {_lit(eid)} AND wikidata_id IS NOT DISTINCT FROM {_lit(ch.get('new_qid'))};")
                if fix == "clear_qid" and qid:
                    new_attrs = {**attrs, "_rejected_wikidata_id": qid}
                    _set_attrs(cur, eid, attrs, new_attrs, rollback)
                    entry(fix, "entities", eid, "attributes._rejected_wikidata_id",
                          attrs.get("_rejected_wikidata_id"), qid, ch)
                    attrs = new_attrs
                if ch.get("flag"):
                    attrs = _needs_review(cur, eid, status, attrs, ch, entry, rollback)
            elif fix == "rename":
                if name != ch["old_name"]:
                    entry(fix, "entities", eid, "name", ch["old_name"], ch["new_name"], ch, f"skipped: name is now {name!r}")
                    continue
                cur.execute("UPDATE entities SET name = %s, updated_at = now() WHERE entity_id = %s AND name = %s",
                            (ch["new_name"], eid, name))
                entry(fix, "entities", eid, "name", name, ch["new_name"], ch)
                rollback.append(f"UPDATE entities SET name = {_lit(name)}, updated_at = {_lit(str(updated) if updated else None)} "
                                f"WHERE entity_id = {_lit(eid)} AND name = {_lit(ch['new_name'])};")
                if ch.get("add_alias"):
                    _add_alias(cur, eid, name, ch, entry, rollback)
            elif fix == "add_alias":
                _add_alias(cur, eid, ch["alias"], ch, entry, rollback)
            elif fix == "needs_review":
                _needs_review(cur, eid, status, attrs, ch, entry, rollback)
            else:
                raise ValueError(f"not a safe fix class: {fix}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.read_only = True

    applied_path = out_dir / "applied.csv"
    previous = _read_existing(applied_path)
    write_csv(applied_path, previous + log, APPLIED_FIELDS)
    rb = out_dir / "rollback.sql"
    header = ("-- Rollback of the identity audit's safe fixes (generated; newest batch first).\n"
              "-- Run: docker compose -f docker/docker-compose.yml exec -T db psql -U history-mapped "
              "-d history-mapped -f - < output/audit/identity-20261031/rollback.sql\n"
              "-- Every statement is guarded on the value the audit wrote; rows changed since are left alone.\n"
              "\\set ON_ERROR_STOP on\n")
    old_body = ""
    if rb.exists():
        old_body = rb.read_text().split("\\set ON_ERROR_STOP on\n", 1)[-1]
    batch = f"-- batch {ts}: {len([l for l in log if l['status'] == 'applied'])} changes\nBEGIN;\n" + \
        "\n".join(reversed(rollback)) + "\nCOMMIT;\n"
    rb.write_text(header + batch + old_body)
    return log


def _read_existing(path: Path) -> list[dict[str, Any]]:
    import csv
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _set_attrs(cur, eid, old, new, rollback):
    cur.execute("UPDATE entities SET attributes = %s::jsonb, updated_at = now() WHERE entity_id = %s",
                (json.dumps(new, ensure_ascii=False), eid))
    rollback.append(f"UPDATE entities SET attributes = {_lit(old)} WHERE entity_id = {_lit(eid)} "
                    f"AND attributes = {_lit(new)};")


def _needs_review(cur, eid, status, attrs, ch, entry, rollback):
    flag = f"identity_audit:{ch['flag']}"
    flags = list(attrs.get("validation_flags") or [])
    new_attrs = attrs
    if flag not in flags:
        new_attrs = {**attrs, "validation_flags": [*flags, flag]}
        _set_attrs(cur, eid, attrs, new_attrs, rollback)
        entry("needs_review", "entities", eid, "attributes.validation_flags", flags, new_attrs["validation_flags"], ch)
    if status != "needs_review":
        cur.execute("UPDATE entities SET verification_status = 'needs_review', updated_at = now() "
                    "WHERE entity_id = %s AND verification_status = %s::verification_status", (eid, status))
        entry("needs_review", "entities", eid, "verification_status", status, "needs_review", ch)
        rollback.append(f"UPDATE entities SET verification_status = {_lit(status)} WHERE entity_id = {_lit(eid)} "
                        f"AND verification_status = 'needs_review';")
    return new_attrs


def _add_alias(cur, eid, alias, ch, entry, rollback):
    cur.execute("SELECT 1 FROM entity_aliases WHERE entity_id = %s AND name = %s", (eid, alias))
    if cur.fetchone():
        return
    alias_id = str(uuid.uuid4())
    cur.execute("INSERT INTO entity_aliases (alias_id, entity_id, name, source, is_primary, created_at, updated_at) "
                "VALUES (%s, %s, %s, 'identity-audit', false, now(), now())", (alias_id, eid, alias))
    entry("add_alias", "entity_aliases", alias_id, "name", None, alias, {**ch, "evidence": f"entity {eid}"})
    rollback.append(f"DELETE FROM entity_aliases WHERE alias_id = {_lit(alias_id)} AND name = {_lit(alias)};")
