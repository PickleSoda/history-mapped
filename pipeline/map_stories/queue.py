"""Rank the atlas's battles that still lack a map story into a work queue.

    python -m pipeline.map_stories queue --limit 200 [--kinds battle,siege,naval_battle]

Reads the local DB (read-only, through the `db` container's psql), ranks
`event_battle` entities that have a Q-id and no `map_stories` row, and writes
output/map-stories/queue.tsv with the columns

    rank  slug  name  qid  year  kind  score  status

`status` is todo | done | skip (or any word an orchestrator writes, such as
`wip`); rebuilding keeps every non-todo status, and a battle whose story has
been synced becomes `done`.

Score (0–100) = 40 Wikidata sitelinks + 25 relationships + 15 chronicle
entries + 10 description length + 10 for a point location; each count term is
log-scaled against the largest value among the candidates.
"""

from __future__ import annotations

import csv
import math
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pipeline.map_stories.net import wd_entities

REPO = Path(__file__).resolve().parents[2]
QUEUE = REPO / "output" / "map-stories" / "queue.tsv"
COLUMNS = ("rank", "slug", "name", "qid", "year", "kind", "score", "status")
WEIGHTS = {"sitelinks": 40, "rels": 25, "chron": 15, "desc": 10}
POINT_BONUS = 10

NAVAL = {"Q1261499"}
SIEGE = {"Q188055"}
BATTLE = {"Q178561", "Q650711"}  # battle, combat
CAMPAIGN = {"Q831663", "Q645883", "Q2001676"}  # military campaign, military operation, offensive
NOT_A_BATTLE = {
    "Q1139665", "Q3882219", "Q2656967", "Q4688003", "Q135010", "Q744913", "Q3199915", "Q2223653", "Q2380335",
}  # political murder, assassination, nuclear explosion, aerial bombing, war crime, aviation accident, massacre, terrorist attack, airstrike

SQL = r"""
select e.entity_id, e.name, e.wikidata_id,
  (select coalesce(min(t.start_year) filter (where t.is_primary), min(t.start_year))
     from entity_temporal_ranges t where t.entity_id = e.entity_id),
  (select count(*) from relationships r where r.source_entity_id = e.entity_id or r.target_entity_id = e.entity_id),
  (select count(distinct ce.chronicle_id) from chronicle_entry_entities cee
     join chronicle_entries ce on ce.entry_id = cee.entry_id where cee.entity_id = e.entity_id),
  greatest(length(coalesce(e.description, '')), length(coalesce(e.summary, ''))),
  exists (select 1 from entity_locations l where l.entity_id = e.entity_id and l.geom is not null
          and geometrytype(l.geom) = 'POINT'),
  (select m.slug from map_stories m where m.entity_id = e.entity_id limit 1)
from entities e
where e.entity_type = 'event_battle' and e.wikidata_id ~ '^Q[0-9]+$'
"""


@dataclass
class Row:
    name: str
    qid: str
    year: int | None
    rels: int
    chron: int
    desc: int
    point: bool
    story: str | None
    sitelinks: int = 0
    kind: str = "battle"
    score: float = 0.0
    slug: str = ""
    status: str = "todo"


def psql(sql: str) -> list[list[str]]:
    cmd = ["docker", "compose", "-f", str(REPO / "docker" / "docker-compose.yml"), "exec", "-T", "db",
           "psql", "-U", "history-mapped", "history-mapped", "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        raise SystemExit(f"psql failed: {res.stderr.strip()[:300]}")
    return [line.split("\t") for line in res.stdout.splitlines() if line.strip()]


def fetch_rows() -> list[Row]:
    out = []
    for c in psql(SQL):
        out.append(Row(c[1], c[2], int(c[3]) if c[3] else None, int(c[4]), int(c[5]), int(c[6]), c[7] == "t", c[8] or None))
    return out


def slugify(name: str) -> str:
    """'Battle of Châlons' → 'battle-of-chalons' (as the committed stories are named)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")[:110] or "story"


def year_tag(year: int | None) -> str:
    if year is None:
        return "undated"
    return f"{-year}-bc" if year < 0 else str(year)


def kind_of(name: str, p31: list[str]) -> str:
    types = set(p31)
    if types & NAVAL:
        return "naval_battle"
    if types & SIEGE or name.casefold().startswith("siege of"):
        return "siege"
    if types & BATTLE:
        return "battle"
    if types & CAMPAIGN:
        return "campaign"
    if types & NOT_A_BATTLE:
        return "other"
    return "battle" if re.match(r"(?i)(naval )?battles? (of|at|off|on)\b", name) else "other"


def score(rows: list[Row]) -> None:
    def norm(values: list[int]):  # noqa: ANN202
        top = math.log1p(max(values or [0]))
        return lambda v: math.log1p(v) / top if top else 0.0

    ns = {k: norm([getattr(r, k) for r in rows]) for k in WEIGHTS}
    for r in rows:
        r.score = round(sum(w * ns[k](getattr(r, k)) for k, w in WEIGHTS.items()) + (POINT_BONUS if r.point else 0), 1)


def assign_slugs(rows: list[Row], taken: set[str]) -> None:
    """battle-of-x; on a collision (with each other or an existing story) add the year."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[slugify(r.name)] = counts.get(slugify(r.name), 0) + 1
    for r in rows:
        base = slugify(r.name)
        r.slug = r.story or (f"{base}-{year_tag(r.year)}" if counts[base] > 1 or base in taken else base)


def read_statuses(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {row["qid"]: row for row in csv.DictReader(f, delimiter="\t") if row.get("qid")}


def build(limit: int, kinds: tuple[str, ...], path: Path = QUEUE, rows: list[Row] | None = None) -> list[Row]:
    rows = fetch_rows() if rows is None else rows
    wd = wd_entities([r.qid for r in rows])
    for r in rows:
        info = wd.get(r.qid) or {}
        r.sitelinks = int(info.get("sitelinks") or 0)
        r.kind = kind_of(r.name, info.get("p31") or [])
    taken = {r.story for r in rows if r.story}
    candidates = [r for r in rows if r.story is None and r.kind in kinds]
    score(candidates)
    assign_slugs(candidates, taken | {p.stem for p in (REPO / "api" / "resources" / "map-stories").glob("*.json")})
    old = read_statuses(path)
    ranked = sorted(candidates, key=lambda r: (-r.score, r.name))
    keep = ranked[:limit]
    in_keep = {r.qid for r in keep}
    done = {r.qid: r for r in rows if r.story}
    for r in keep:
        prev = old.get(r.qid, {}).get("status", "todo")
        r.status = prev or "todo"
    # Rows from the previous queue that fell out of this cut keep their status.
    extra: list[Row] = []
    for qid, prev in old.items():
        if qid in in_keep:
            continue
        if qid in done:
            r = done[qid]
            r.slug, r.status, r.score = r.story or prev.get("slug", ""), "done", float(prev.get("score") or 0)
            extra.append(r)
        elif prev.get("status", "todo") != "todo":
            r = next((c for c in candidates if c.qid == qid), None)
            if r is not None:
                r.status = prev["status"]
                extra.append(r)
    write(keep + extra, path)
    return keep + extra


def write(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(COLUMNS)
        for i, r in enumerate(rows, 1):
            w.writerow([i, r.slug, r.name, r.qid, "" if r.year is None else r.year, r.kind, f"{r.score:.1f}", r.status])


def summary(rows: list[Row], path: Path, show: int = 10) -> str:
    from collections import Counter

    st = Counter(r.status for r in rows)
    kinds = Counter(r.kind for r in rows)
    lines = [f"wrote {path.relative_to(REPO) if path.is_relative_to(REPO) else path}: {len(rows)} rows ({', '.join(f'{k} {v}' for k, v in st.items())}; {', '.join(f'{k} {v}' for k, v in kinds.items())})"]
    for i, r in enumerate(rows[:show], 1):
        lines.append(f"{i:3} {r.score:5.1f} {r.slug[:40]:40} {r.qid:10} {'' if r.year is None else r.year:>6} {r.kind:12} {r.status}")
    if len(rows) > show:
        lines.append(f"… {len(rows) - show} more in the file")
    return "\n".join(lines)
