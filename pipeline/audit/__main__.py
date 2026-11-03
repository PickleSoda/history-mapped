"""CLI: python -m pipeline.audit identity [--only qid|dups|names|text|relations|stories|reconcile] [--apply-safe] [--limit N]

Read-only unless --apply-safe. See docs/implementation-docs/identity-audit.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.audit.common import DEFAULT_OUT, RECONCILE_OUT, load_rows, write_csv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.audit")
    sub = ap.add_subparsers(dest="command", required=True)
    idp = sub.add_parser("identity", help="audit entity identity (QIDs, names, types, dates, text)")
    idp.add_argument("--only", help="comma-separated sections: qid,places,dups,names,text,relations,stories; "
                                    "or the opt-in reconcile (find QIDs for rows that have none)")
    idp.add_argument("--apply-safe", action="store_true",
                     help="apply the safe fix classes (QID set/clear, redirects, mechanical renames, aliases, needs_review)")
    idp.add_argument("--limit", type=int, help="check at most N QID rows (for trial runs)")
    idp.add_argument("--out", type=Path, help=f"output directory (default {DEFAULT_OUT}; "
                                              f"{RECONCILE_OUT} for --only reconcile)")
    idp.add_argument("--types", help="reconcile only: comma-separated entity types")
    idp.add_argument("--apply-planned", action="store_true",
                     help="reconcile only: apply the set_qid lines of planned.csv in --out as reviewed, "
                          "without re-planning (backup first, one transaction, guarded per row)")
    idp.add_argument("--max-rps", type=float, default=4.0, help="Wikidata requests per second (default 4)")
    idp.add_argument("--offline", action="store_true", help="use the Wikidata cache only; fail on a cache miss")
    idp.add_argument("--workers", type=int, default=4, help="parallel wbgetentities batches (shared 4 req/s limit)")
    idp.add_argument("--no-resolve", action="store_true", help="skip C3 (no Wikidata searches)")
    idp.add_argument("--report-only", action="store_true",
                     help="rebuild report.md from the outputs on disk (re-runs only the read-only story check)")
    args = ap.parse_args(argv)

    from pipeline.audit.identity import OPTIONAL_SECTIONS, SECTIONS, Audit
    from pipeline.audit.report import write_report

    sections = SECTIONS if not args.only else tuple(s.strip() for s in args.only.split(",") if s.strip())
    unknown = set(sections) - set(SECTIONS) - set(OPTIONAL_SECTIONS)
    if unknown:
        ap.error(f"unknown section(s): {', '.join(sorted(unknown))}")
    if args.out is None:
        args.out = RECONCILE_OUT if sections == ("reconcile",) else DEFAULT_OUT
    audit = Audit(args.out, offline=args.offline, limit=args.limit, workers=args.workers, max_rps=args.max_rps)
    if args.apply_planned:
        if sections != ("reconcile",):
            ap.error("--apply-planned goes with --only reconcile")
        load_outputs(audit)  # outcomes.csv, for the report
        # the set_qid lines are exactly planned.csv as reviewed; nothing is re-planned
        audit.results["reconcile"] = load_planned(args.out) + [
            x for x in audit.results.get("reconcile", []) if x.get("action") != "set_qid"]
        audit.inventory("before")
        apply_safe(audit)
        write_report(audit, sections)
        print(f"applied {sum(1 for e in audit.results.get('applied', []) if e['status'] == 'applied')} changes; "
              f"report: {args.out / 'report.md'}")
        return 0
    if args.report_only:
        load_outputs(audit)
        if "stories" in sections:
            audit.stories()
        write_report(audit, sections)
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
    if "reconcile" in sections:
        types = {t.strip() for t in args.types.split(",") if t.strip()} if args.types else None
        audit.reconcile(types)
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


def load_planned(out: Path) -> list[dict]:
    """planned.csv as reviewed: its set_qid lines, for --apply-planned."""
    import csv

    path = out / "planned.csv"
    if not path.exists():
        raise SystemExit(f"no {path}: run --only reconcile first")
    with path.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r.get("action") == "set_qid" and r.get("qid")]


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
    if (rec := rows("outcomes.csv")) is not None:
        R["reconcile"] = rec
        R["reconcile_dups"] = rows("duplicate-candidates.csv") or []


if __name__ == "__main__":
    sys.exit(main())
