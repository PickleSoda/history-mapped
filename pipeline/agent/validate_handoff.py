"""Fail-fast validation gate for opencode extraction handoffs.

Checks (spec §4.2): schema parse, canonical entity types, allowed relation
types, referential integrity, summary completeness when precomputed, date
sanity (start <= end, plausible years, era bounds when the path encodes an era).

Usage: python -m pipeline.agent.validate_handoff <path/to/candidates.json>
Exit 0 = clean; exit 1 = itemised errors.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from pipeline.agent.graph.nodes.validate import ALLOWED_RELATION_TYPES
from pipeline.agent.handoff import load_handoff
from pipeline.agent.schemas.entities import _CANONICAL_ENTITY_TYPES

ERA_BOUNDS = {
    # Bounds are editorial buckets; edges are widened where real facts straddle
    # them (Jericho c. 9500, Olympics 776, post-collapse campaigns). The gate's
    # real job is catching sign errors and wild misdatings.
    "e01": (-10000, -4000),
    "e02": (-4000, -1050),
    "e03": (-1200, -750),
    "e04": (-800, -300),
    "e05": (-330, -30),
    "e06": (-30, 500),
    "e07": (500, 1000),
    "e08": (1000, 1350),
    "e09": (1350, 1750),
    "e10": (1750, 2000),
}


def _year(date_str: str | None) -> int | None:
    if not date_str:
        return None
    m = re.match(r"^(-?\d{1,5})", date_str.strip())
    return int(m.group(1)) if m else None


def validate(path: str | Path) -> list[str]:
    errors: list[str] = []
    try:
        doc = load_handoff(path)
    except Exception as exc:
        return [f"schema parse failed: {exc}"]

    labels = {c.label for c in doc.candidate_entities}
    for c in doc.candidate_entities:
        if c.entity_type not in _CANONICAL_ENTITY_TYPES:
            errors.append(f"entity '{c.label}': non-canonical type '{c.entity_type}'")
        sy, ey = _year(c.start_date), _year(c.end_date)
        if sy is not None and ey is not None and sy > ey:
            errors.append(f"entity '{c.label}': start_year {sy} > end_year {ey}")
        for y in (sy, ey):
            if y is not None and not -10000 < y <= 2100:
                errors.append(f"entity '{c.label}': implausible year {y}")

    for r in doc.candidate_relations:
        if r.relationship_type not in ALLOWED_RELATION_TYPES:
            errors.append(
                f"relation {r.source_label}->{r.target_label}: "
                f"disallowed type '{r.relationship_type}'"
            )
        for endpoint in (r.source_label, r.target_label):
            if endpoint not in labels:
                errors.append(f"relation endpoint '{endpoint}' has no extracted entity")

    if doc.summaries_precomputed:
        for c in doc.candidate_entities:
            fields = doc.summaries.get(c.label) or {}
            if not (fields.get("summary") or "").strip() or not (fields.get("significance") or "").strip():
                errors.append(
                    f"entity '{c.label}': missing summary/significance "
                    f"(summaries_precomputed=true)"
                )

    # Era may be encoded as a path segment or embedded in the run id:
    #   .../e04__x/candidates.json  |  campaign_e04__aegean/candidates.json
    era_match = re.search(r"(?:^|[_/\\])e(\d{2})(?:[_/\\]|$)", str(path))
    if era_match:
        # Era bounds police the era's FACTS (parsed events), not entity lifespans:
        # cities and dynasties legitimately predate the transcript that features them.
        key = f"e{era_match.group(1)}"
        lo, hi = ERA_BOUNDS[key]
        for ev in doc.parsed_events:
            y = _year(ev.start_date)
            if y is not None and not lo <= y <= hi:
                errors.append(f"event '{ev.label}': year {y} outside {key} bounds [{lo}, {hi}]")
    return errors


def main(path: str) -> int:
    errors = validate(path)
    if errors:
        print(f"INVALID handoff {path}: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m pipeline.agent.validate_handoff <candidates.json>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
