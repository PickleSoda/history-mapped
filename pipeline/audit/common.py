"""Shared paths, DB access and output helpers for the identity audit."""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "output" / "audit" / "identity-20261031"
CACHE_DIR = REPO / "output" / "audit" / "cache"
STORIES_DIR = REPO / "api" / "resources" / "map-stories"
STORY_SOURCES = REPO / "pipeline" / "map_stories" / "stories"
COMPOSE = ["docker", "compose", "-f", str(REPO / "docker" / "docker-compose.yml")]


def dsn() -> str:
    """The pipeline's DATABASE_URL (pipeline/.env), local dev DB by default."""
    url = os.environ.get("DATABASE_URL")
    env = REPO / "pipeline" / ".env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    url = url or "postgresql://history-mapped:secret@localhost:5432/history-mapped"
    host = url.split("@")[-1].split("/")[0].split(":")[0]
    if host not in ("localhost", "127.0.0.1", "db"):
        raise SystemExit(f"refusing to run against non-local database host {host!r}")
    return url


@dataclass
class Row:
    id: str
    name: str
    type: str
    group: str
    qid: str | None
    status: str
    summary: str
    description: str
    attributes: dict[str, Any]
    impact: int | None
    created_at: str
    start: int | None
    end: int | None
    aliases: list[str] = field(default_factory=list)
    rels: int = 0
    chron: int = 0
    has_geo: bool = False
    point: tuple[float, float] | None = None
    stories: list[str] = field(default_factory=list)
    created_by: str = ""

    @property
    def names(self) -> list[str]:
        return [self.name, *[a for a in self.aliases if a != self.name]]

    @property
    def span(self) -> tuple[int, int] | None:
        lo = self.start if self.start is not None else self.end
        hi = self.end if self.end is not None else self.start
        if lo is None or hi is None:
            return None
        return (min(lo, hi), max(lo, hi))

    @property
    def text(self) -> str:
        return " ".join(t for t in (self.summary, self.description) if t)


def connect(read_only: bool = True):
    import psycopg

    conn = psycopg.connect(dsn())
    conn.read_only = read_only
    return conn


def load_rows(conn) -> dict[str, Row]:
    cur = conn.cursor()
    cur.execute("""
        SELECT e.entity_id::text, e.name, e.entity_type::text, e.entity_group::text, e.wikidata_id,
               e.verification_status::text, coalesce(e.summary,''), coalesce(e.description,''),
               e.attributes, e.impact_score, coalesce(e.created_at::text,''), t.start_year, t.end_year
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
    """)
    rows = {r[0]: Row(*r[:13]) for r in cur.fetchall()}
    cur.execute("SELECT entity_id::text, coalesce(created_by,'') FROM entities")
    for eid, by in cur.fetchall():
        rows[eid].created_by = by
    cur.execute("SELECT entity_id::text, name FROM entity_aliases ORDER BY is_primary DESC, created_at")
    for eid, name in cur.fetchall():
        if eid in rows and name not in rows[eid].aliases:
            rows[eid].aliases.append(name)
    cur.execute("""
        SELECT id, count(*) FROM (
            SELECT source_entity_id::text id FROM relationships
            UNION ALL SELECT target_entity_id::text FROM relationships) x GROUP BY id""")
    for eid, n in cur.fetchall():
        if eid in rows:
            rows[eid].rels = n
    cur.execute("SELECT entity_id::text, count(*) FROM chronicle_entry_entities GROUP BY 1")
    for eid, n in cur.fetchall():
        if eid in rows:
            rows[eid].chron = n
    cur.execute("""
        SELECT DISTINCT entity_id::text FROM geometry_periods WHERE geom IS NOT NULL OR territory_geom IS NOT NULL
        UNION SELECT entity_id::text FROM entity_locations WHERE geom IS NOT NULL OR territory_geom IS NOT NULL""")
    for (eid,) in cur.fetchall():
        if eid in rows:
            rows[eid].has_geo = True
    cur.execute("""
        SELECT entity_id::text, ST_X(geom), ST_Y(geom) FROM entity_locations
        WHERE is_primary AND geom IS NOT NULL AND GeometryType(geom) = 'POINT'""")
    for eid, x, y in cur.fetchall():
        if eid in rows:
            rows[eid].point = (x, y)
    cur.execute("SELECT entity_id::text, slug FROM map_stories")
    for eid, slug in cur.fetchall():
        if eid in rows:
            rows[eid].stories.append(slug)
    return rows


def load_relationships(conn) -> list[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT relationship_id::text, source_entity_id::text, target_entity_id::text,
               relationship_type::text, start_year, end_year, coalesce(description,'')
        FROM relationships""")
    cols = ("id", "source", "target", "type", "start", "end", "description")
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r.get(k)) for k in fields})
            n += 1
    return n


def _cell(v: Any) -> Any:
    if isinstance(v, (list, tuple, set)):
        return " | ".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else v


def inventory(rows: dict[str, Row]) -> dict[str, Any]:
    """C1 counts: by type with/without QID and by verification_status."""
    by_type: dict[str, Counter] = defaultdict(Counter)
    for r in rows.values():
        c = by_type[r.type]
        c["total"] += 1
        c["with_qid" if r.qid else "without_qid"] += 1
        c[f"status:{r.status}"] += 1
    qid_counts = Counter(r.qid for r in rows.values() if r.qid)
    return {
        "entities": len(rows),
        "with_qid": sum(1 for r in rows.values() if r.qid),
        "distinct_qids": len(qid_counts),
        "qids_on_2plus_rows": sum(1 for n in qid_counts.values() if n > 1),
        "by_status": dict(Counter(r.status for r in rows.values())),
        "by_type": {t: dict(c) for t, c in sorted(by_type.items(), key=lambda kv: -kv[1]["total"])},
    }
