"""Acceptance metrics (campaign spec §7 / remediation §2) against the compose DB."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from pipeline.campaign import paths

COMPOSE_FILE = "docker/docker-compose.yml"
DEFAULTS = {"POSTGRES_USER": "history-mapped", "POSTGRES_DB": "history-mapped"}


class DbUnavailable(Exception):
    pass


def _env_file_value(path: Path, name: str) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(rf"^\s*{name}\s*=\s*(.*?)\s*$", line)
            if m:
                return m.group(1).strip("'\"")
    except FileNotFoundError:
        pass
    return None


def db_setting(name: str, root: Path | None = None) -> str:
    """Env var, then docker/.env / .env, then the compose file's ${NAME:-default}."""
    root = root or paths.root()
    if os.environ.get(name):
        return os.environ[name]
    for env_file in (root / "docker" / ".env", root / ".env"):
        v = _env_file_value(env_file, name)
        if v:
            return v
    try:
        m = re.search(rf"\$\{{{name}:-([^}}]+)\}}", (root / COMPOSE_FILE).read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    except FileNotFoundError:
        pass
    return DEFAULTS[name]


def canonical_types_sql() -> str:
    from pipeline.agent.schemas.entities import _CANONICAL_ENTITY_TYPES

    return ", ".join(f"'{t}'" for t in sorted(_CANONICAL_ENTITY_TYPES))


def build_sql() -> str:
    return f"""
SELECT 'entities', count(*) FROM entities;
SELECT 'qid', count(*) FILTER (WHERE coalesce(wikidata_id, '') <> ''), count(*) FROM entities;
SELECT 'type', entity_type::text, count(*) FROM entities GROUP BY entity_type ORDER BY count(*) DESC, 2 LIMIT 15;
SELECT 'geo', e.entity_group::text, count(*),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM entity_geo_refs g WHERE g.entity_id = e.entity_id AND g.is_active)),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM entity_locations l WHERE l.entity_id = e.entity_id
                                 AND (l.geom IS NOT NULL OR l.territory_geom IS NOT NULL))),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM entity_geo_refs g WHERE g.entity_id = e.entity_id AND g.is_active)
                      OR EXISTS (SELECT 1 FROM entity_locations l WHERE l.entity_id = e.entity_id
                                 AND (l.geom IS NOT NULL OR l.territory_geom IS NOT NULL)))
FROM entities e GROUP BY e.entity_group ORDER BY 2;
SELECT 'jan1_ranges', count(*) FROM entity_temporal_ranges
  WHERE start_date ~ '^-?[0-9]+-01-01' OR end_date ~ '^-?[0-9]+-01-01';
SELECT 'jan1_relations', count(*) FROM relationships
  WHERE temporal_start ~ '^-?[0-9]+-01-01' OR temporal_end ~ '^-?[0-9]+-01-01';
SELECT 'orphans', count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM relationships r
  WHERE r.source_entity_id = e.entity_id OR r.target_entity_id = e.entity_id)), count(*) FROM entities e;
SELECT 'relations', count(*) FROM relationships;
SELECT 'chronicles', count(*), count(DISTINCT impact_score) FROM chronicles;
SELECT 'offtax', count(*) FROM entities WHERE entity_type::text NOT IN ({canonical_types_sql()});
"""


def _compose(root: Path) -> list[str]:
    return ["docker", "compose", "-f", str(root / COMPOSE_FILE)]


def run_sql(sql: str, root: Path | None = None) -> list[list[str]]:
    root = root or paths.root()
    try:
        ps = subprocess.run(_compose(root) + ["ps", "--status", "running", "--services"],
                            capture_output=True, text=True, timeout=30, cwd=root)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise DbUnavailable(f"docker compose unavailable ({exc})")
    if ps.returncode != 0 or "db" not in ps.stdout.split():
        raise DbUnavailable("db service is not running (start it: docker compose -f docker/docker-compose.yml up -d db)")
    cmd = _compose(root) + ["exec", "-T", "db", "psql", "-U", db_setting("POSTGRES_USER", root),
                            "-d", db_setting("POSTGRES_DB", root), "-X", "-A", "-t", "-F", "|",
                            "-v", "ON_ERROR_STOP=1", "-f", "-"]
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=300, cwd=root)
    if res.returncode != 0:
        first = (res.stderr.strip().splitlines() or ["psql failed"])[0]
        raise DbUnavailable(f"psql failed: {first}")
    return [line.split("|") for line in res.stdout.splitlines() if line.strip()]


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else f"{n}/0"


def report_lines(rows: list[list[str]]) -> list[str]:
    by: dict[str, list[list[str]]] = {}
    for r in rows:
        by.setdefault(r[0], []).append(r[1:])

    def one(key: str) -> list[str]:
        return (by.get(key) or [["0"]])[0]

    total = int(one("entities")[0])
    qid, q_total = (int(x) for x in (one("qid") + ["0"])[:2])
    orphans, o_total = (int(x) for x in (one("orphans") + ["0"])[:2])
    chron = one("chronicles") + ["0"]
    out = [
        f"{'entities':<26}{total}",
        f"{'with QID':<26}{_pct(qid, q_total)}",
        f"{'relations':<26}{one('relations')[0]}",
        f"{'orphan entities':<26}{_pct(orphans, o_total)}   (target <15%)",
        f"{'chronicles':<26}{chron[0]}   distinct impact={chron[1]} (target >10)",
        f"{'fabricated -01-01 dates':<26}ranges={one('jan1_ranges')[0]} relations={one('jan1_relations')[0]}   (target ~0)",
        f"{'off-taxonomy types':<26}{one('offtax')[0]}   (target 0)",
        "geo by group (geo-ref / located / any):",
    ]
    for group, n, georef, located, any_geo in by.get("geo", []):
        target = "   (target >80%)" if group == "PLACE" else ""
        out.append(f"  {group:<10}{_pct(int(any_geo), int(n))}  georef={georef} located={located}{target}")
    out.append("top entity types: " + ", ".join(f"{t}={c}" for t, c in by.get("type", [])))
    return out
