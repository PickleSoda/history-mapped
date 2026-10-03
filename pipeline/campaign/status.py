"""Campaign-wide status: one row per run (transcripts ∪ handoff dirs)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pipeline.campaign import paths

THIN_FACTS = 60
THIN_DENSITY = 1.3


@dataclass
class Row:
    slug: str
    era: str
    region: str
    facts: int | None
    events: int | None
    entities: int | None
    relations: int | None
    density: float | None
    review: str
    ingest: str
    stale: bool = False
    valid: str | None = None

    @property
    def thin(self) -> bool:
        return (self.facts or 0) < THIN_FACTS or (self.density is not None and self.density < THIN_DENSITY)


def latest_review(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None
    history = data if isinstance(data, list) else data.get("history") or []
    return history[-1] if history else None


def ingest_state(manifest: Path) -> str:
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "-"
    except ValueError:
        return "failed"
    return "failed" if m.get("errors") or m.get("errors_count") else "clean"


def run_slugs() -> list[str]:
    slugs = {p.stem for p in paths.transcripts_dir().glob("*.txt")}
    slugs |= {paths.slug_of(p.name) for p in paths.extractions_dir().glob(f"{paths.RUN_PREFIX}*") if p.is_dir()}
    return sorted(slugs)


def collect(era: str | None = None, validate: bool = False) -> list[Row]:
    manifests = paths.manifests_dir()
    validator = None
    if validate:
        from pipeline.agent.validate_handoff import validate as validator
    rows = []
    for slug in run_slugs():
        e, region, _ = paths.parse_slug(slug)
        if era and e != era:
            continue
        cand = paths.candidates_path(slug)
        events = entities = relations = None
        density = None
        if cand.exists():
            try:
                doc = json.loads(cand.read_text(encoding="utf-8"))
                events = len(doc.get("parsed_events") or [])
                entities = len(doc.get("candidate_entities") or [])
                relations = len(doc.get("candidate_relations") or [])
                density = round(relations / entities, 2) if entities else 0.0
            except ValueError:
                pass
        review = latest_review(paths.review_path(slug))
        manifest = paths.manifest_path(slug, manifests)
        ingest = ingest_state(manifest)
        stale = ingest == "clean" and cand.exists() and cand.stat().st_mtime > manifest.stat().st_mtime
        valid = None
        if validator is not None:
            valid = "-" if not cand.exists() else ("OK" if not validator(str(cand)) else "FAIL")
        rows.append(Row(
            slug=slug, era=e, region=region,
            facts=paths.count_facts(paths.transcript_path(slug)),
            events=events, entities=entities, relations=relations, density=density,
            review=(review or {}).get("verdict") or "-", ingest=ingest, stale=stale, valid=valid,
        ))
    return rows


def _cell(v) -> str:
    return "-" if v is None else str(v)


def table_lines(rows: list[Row], show_valid: bool = False) -> list[str]:
    headers = ["slug", "facts", "ev", "ent", "rel", "r/e", "review", "ingest"] + (["valid"] if show_valid else [])
    data = [[r.slug, _cell(r.facts), _cell(r.events), _cell(r.entities), _cell(r.relations),
             "-" if r.density is None else f"{r.density:.2f}", r.review, r.ingest]
            + ([_cell(r.valid)] if show_valid else []) for r in rows]
    widths = [max(len(h), *(len(d[i]) for d in data)) if data else len(h) for i, h in enumerate(headers)]

    def fmt(cells: list[str]) -> str:
        return "  ".join(c.ljust(widths[0]) if i == 0 else c.rjust(widths[i]) for i, c in enumerate(cells)).rstrip()

    return [fmt(headers)] + [fmt(d) for d in data]


def totals(rows: list[Row]) -> dict:
    def s(attr: str) -> int:
        return sum(getattr(r, attr) or 0 for r in rows)

    ent, rel = s("entities"), s("relations")
    out = {
        "runs": len(rows),
        "transcripts": sum(r.facts is not None for r in rows),
        "handoffs": sum(r.entities is not None for r in rows),
        "facts": s("facts"), "events": s("events"), "entities": ent, "relations": rel,
        "r/e": round(rel / ent, 2) if ent else 0.0,
        "ingest": {"clean": sum(r.ingest == "clean" for r in rows), "failed": sum(r.ingest == "failed" for r in rows),
                   "none": sum(r.ingest == "-" for r in rows)},
        "review": {},
        "stale": [r.slug for r in rows if r.stale],
    }
    for r in rows:
        out["review"][r.review] = out["review"].get(r.review, 0) + 1
    if any(r.valid is not None for r in rows):
        out["valid"] = {k: sum(r.valid == k for r in rows) for k in ("OK", "FAIL")}
    return out


def grid(rows: list[Row]) -> dict[str, dict[str, int]]:
    g: dict[str, dict[str, int]] = {}
    for r in rows:
        g.setdefault(r.region, {}).setdefault(r.era, 0)
        g[r.region][r.era] += 1
    return g


def footer_lines(rows: list[Row]) -> list[str]:
    t = totals(rows)
    out = [
        f"runs={t['runs']} transcripts={t['transcripts']} handoffs={t['handoffs']} facts={t['facts']} "
        f"events={t['events']} entities={t['entities']} relations={t['relations']} r/e={t['r/e']:.2f}",
        "ingest " + " ".join(f"{k}={v}" for k, v in t["ingest"].items())
        + "  review " + " ".join(f"{k}={v}" for k, v in sorted(t["review"].items()))
        + ("  valid " + " ".join(f"{k}={v}" for k, v in t["valid"].items()) if "valid" in t else ""),
    ]
    if t["stale"]:
        out.append(f"stale (handoff edited after clean ingest; re-ingest with --refresh): {' '.join(t['stale'])}")
    g = grid(rows)
    eras = sorted({r.era for r in rows})
    if g:
        w = max(len("region"), *(len(k) for k in g))
        out.append("region".ljust(w) + " " + " ".join(e.rjust(3) for e in eras))
        for region in sorted(g):
            out.append(region.ljust(w) + " " + " ".join(
                (str(g[region][e]) if e in g[region] else ".").rjust(3) for e in eras))
    return out


def as_json(rows: list[Row]) -> dict:
    return {"runs": [{**asdict(r), "thin": r.thin} for r in rows], "totals": totals(rows), "grid": grid(rows)}
