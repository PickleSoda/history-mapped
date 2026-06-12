"""Compare two eval reports and print the metric deltas.

    py -m pipeline.agent.eval.compare iter1_writepath iter2_semantics_bce

Reads output/eval_runs/<label>/report.json for each label, extracts the
headline metrics, and renders a delta table (also written to
output/eval_runs/<labelB>/comparison_vs_<labelA>.md) so iteration-to-iteration
progress is reproducible and reviewable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from pipeline.agent.eval.harness import EVAL_OUTPUT_DIR, _slug

# metric key -> (label, direction) where direction is +1 if higher-is-better,
# -1 if lower-is-better, 0 if neutral/informational.
_METRICS: list[tuple[str, str, int]] = [
    ("entities", "entities", 0),
    ("relationships", "relationships", 1),
    ("secondary_links", "chronicle secondary links", 1),
    ("entities_with_wikidata", "entities w/ wikidata", 1),
    ("entities_with_geometry", "entities w/ geometry", 1),
    ("range_violations", "event-range violations", -1),
    ("duplicate_relationships", "duplicate relationships", -1),
    ("self_loops", "self-loop relationships", -1),
    ("overlap_dupe_names", "overlap duplicate names", -1),
    ("chronicle_orphans", "chronicle orphan entries", -1),
    ("short_names", "<=2-char names", -1),
    ("runs_failed", "runs with non-zero exit", -1),
]


def _load(label: str) -> dict:
    path = EVAL_OUTPUT_DIR / _slug(label) / "report.json"
    if not path.exists():
        raise click.ClickException(f"No report found for label '{label}' at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def headline(report: dict) -> dict:
    db = report.get("db_state", {})
    counts = db.get("counts", {})
    rf = db.get("relationship_flags", {})
    ef = db.get("entity_flags", {})
    overlap = db.get("overlap", {})
    runs = report.get("runs", [])
    chronicles = db.get("chronicles", [])
    return {
        "entities": counts.get("entities", 0),
        "relationships": counts.get("relationships", 0),
        "secondary_links": counts.get("chronicle_entry_entities", 0),
        "entities_with_wikidata": ef.get("with_wikidata", 0),
        "entities_with_geometry": ef.get("with_geometry", 0),
        "range_violations": len(rf.get("event_range_violations", [])),
        "duplicate_relationships": len(rf.get("duplicates", [])),
        "self_loops": len(rf.get("self_loops", [])),
        "overlap_consistent": overlap.get("consistent"),
        "overlap_dupe_names": len(overlap.get("duplicate_names", [])),
        "chronicle_orphans": sum(int(c.get("orphan_count", 0)) for c in chronicles),
        "short_names": len(ef.get("short_name_review", [])),
        "runs_failed": sum(1 for r in runs if r.get("returncode") != 0),
    }


def _mark(direction: int, delta: int) -> str:
    if direction == 0 or delta == 0:
        return ""
    improved = (delta > 0 and direction > 0) or (delta < 0 and direction < 0)
    return "[better]" if improved else "[worse]"


def render_comparison(label_a: str, a: dict, label_b: str, b: dict) -> str:
    # ASCII-only so it prints on any console (Windows cp1252 chokes on unicode).
    ha, hb = headline(a), headline(b)
    lines = [
        f"# Comparison -- `{label_a}` -> `{label_b}`",
        "",
        f"| metric | {label_a} | {label_b} | delta | |",
        "|---|---|---|---|---|",
    ]
    for key, name, direction in _METRICS:
        va, vb = ha.get(key, 0), hb.get(key, 0)
        delta = vb - va
        sign = f"+{delta}" if delta > 0 else str(delta)
        lines.append(f"| {name} | {va} | {vb} | {sign} | {_mark(direction, delta)} |")
    consistency_gain = "[better]" if hb.get("overlap_consistent") and not ha.get("overlap_consistent") else ""
    lines.append(
        f"| overlap consistent | {ha.get('overlap_consistent')} | "
        f"{hb.get('overlap_consistent')} | | {consistency_gain} |"
    )
    lines.append("")
    return "\n".join(lines)


@click.command()
@click.argument("label_a")
@click.argument("label_b")
def main(label_a: str, label_b: str):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # tolerate any stray unicode on Windows
    except Exception:
        pass
    a, b = _load(label_a), _load(label_b)
    out = render_comparison(label_a, a, label_b, b)
    click.echo(out)
    dest = EVAL_OUTPUT_DIR / _slug(label_b) / f"comparison_vs_{_slug(label_a)}.md"
    dest.write_text(out, encoding="utf-8")
    click.echo(f"\n[compare] written to {dest}")


if __name__ == "__main__":
    sys.exit(main())
