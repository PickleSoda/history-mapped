"""CLI: python -m pipeline.audit identity [--only qid|dups|names|text|relations|stories] [--apply-safe] [--limit N]

Read-only unless --apply-safe. See docs/implementation-docs/identity-audit.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.audit.common import DEFAULT_OUT, load_rows, write_csv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.audit")
    sub = ap.add_subparsers(dest="command", required=True)
    idp = sub.add_parser("identity", help="audit entity identity (QIDs, names, types, dates, text)")
    idp.add_argument("--only", help="comma-separated sections: qid,dups,names,text,relations,stories")
    idp.add_argument("--apply-safe", action="store_true",
                     help="apply the safe fix classes (QID set/clear, redirects, mechanical renames, aliases, needs_review)")
    idp.add_argument("--limit", type=int, help="check at most N QID rows (for trial runs)")
    idp.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output directory (default {DEFAULT_OUT})")
    idp.add_argument("--offline", action="store_true", help="use the Wikidata cache only; fail on a cache miss")
    idp.add_argument("--workers", type=int, default=4, help="parallel wbgetentities batches (shared 4 req/s limit)")
    idp.add_argument("--no-resolve", action="store_true", help="skip C3 (no Wikidata searches)")
    idp.add_argument("--report-only", action="store_true",
                     help="rebuild report.md from the outputs on disk (re-runs only the read-only story check)")
    args = ap.parse_args(argv)

    from pipeline.audit.identity import SECTIONS, Audit
    from pipeline.audit.report import write_report

    sections = SECTIONS if not args.only else tuple(s.strip() for s in args.only.split(",") if s.strip())
    unknown = set(sections) - set(SECTIONS)
    if unknown:
        ap.error(f"unknown section(s): {', '.join(sorted(unknown))}")
    audit = Audit(args.out, offline=args.offline, limit=args.limit, workers=args.workers)
    if args.report_only:
        load_outputs(audit)
        audit.stories()
        write_report(audit, SECTIONS)
        print(f"report: {args.out / 'report.md'}")
        return 0
    audit.inventory("before")
    if "qid" in sections:
        audit.qids(resolve=not args.no_resolve)
    if "places" in sections:
        audit.places()
    if "dups" in sections:
        audit.dups()
    if "names" in sections:
        audit.names()
    if "text" in sections:
        audit.text()
    if "relations" in sections:
        audit.relations()
    if "stories" in sections:
        audit.stories()
    if args.apply_safe:
        apply_safe(audit)
    write_report(audit, sections)
    print(f"report: {args.out / 'report.md'}")
    return 0


def apply_safe(audit) -> None:
    from pipeline.audit.apply import APPLIED_FIELDS, apply_changes, backup
    from pipeline.audit.identity import QID_FIELDS

    changes = audit.plan_changes()
    if not changes:
        audit.log("C9 nothing to apply")
        return
    path = backup(audit.out)
    audit.log(f"C9 backup written: {path}")
    log = apply_changes(audit.conn, changes, audit.out)
    applied = [entry for entry in log if entry["status"] == "applied"]
    audit.results["applied"] = log
    audit.results["backup"] = str(path)
    audit.log(f"C9 applied {len(applied)} column changes ({len(log) - len(applied)} skipped)")
    qid_log = [e for e in log if e["column"] in ("wikidata_id", "attributes._rejected_wikidata_id")]
    write_csv(audit.out / "qid-fixes-applied.csv", qid_log, APPLIED_FIELDS)
    # re-check the changed rows and re-take the counts
    audit.rows = load_rows(audit.conn)
    changed = {e["id"] for e in applied if e["table"] == "entities"}
    recheck = audit.qids(only_ids=changed, resolve=False, write=False) if changed else []
    audit.results["recheck"] = recheck
    audit.results["recheck_ids"] = changed
    write_csv(audit.out / "qid-recheck.csv", recheck, QID_FIELDS)
    if "stories" in audit.results:
        audit.stories()  # story refs resolve against the fixed rows
    audit.inventory("after")


def load_outputs(audit) -> None:
    """Read a finished run's outputs back into ``audit.results`` (for --report-only)."""
    import csv
    import json

    out = audit.out

    def rows(name):
        path = out / name
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def split(v):
        return [x for x in (v or "").split(" | ") if x]

    R = audit.results
    for when in ("before", "after"):
        path = out / f"inventory-{when}.json"
        if path.exists():
            R[f"inventory_{when}"] = json.loads(path.read_text())
    if (flags := rows("qid-flags.csv")) is not None:
        R["qid_flags"] = flags
    if (applied := rows("applied.csv")) is not None:
        R["applied"] = applied
        R["recheck_ids"] = {a["id"] for a in applied if a["table"] == "entities" and a["status"] == "applied"}
        R["recheck"] = rows("qid-recheck.csv") or []
        backups = sorted(out.glob("backup-*.sql.gz"))
        R["backup"] = str(backups[-1]) if backups else ""
    if (dups := rows("duplicates.csv")) is not None:
        R["dups"] = dups
    if (names := rows("names.csv")) is not None:
        R["names"] = [{**n, "issues": split(n["issues"]), "apply": n["apply"] == "True"} for n in names]
        conv = out / "name-conventions.json"
        R["name_conventions"] = json.loads(conv.read_text()) if conv.exists() else {}
    if (text := rows("text-flags.csv")) is not None:
        R["text"] = text
    if (rel := rows("relation-flags.csv")) is not None:
        R["relations"] = rel
    if (places := rows("place-flags.csv")) is not None:
        R["places"] = places


if __name__ == "__main__":
    sys.exit(main())
