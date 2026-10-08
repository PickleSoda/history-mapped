"""Acceptance metrics (campaign spec §7 / remediation §2) against the compose DB."""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.campaign import paths
from pipeline.campaign.dates import depad, is_jan1, jan1_years

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


JAN1_SQL = "'^-?[0-9]+-01-01$'"
# Campaign runs of the CE-only eras (e07 500 CE .. e10): a BCE start there is suspect.
CE_ERA_RUN_SQL = "'^campaign_e(0[7-9]|10)__'"


def sign_sql() -> str:
    """BCE/CE sign checks: impossible person lifespans (rows), relation years that
    leave a person endpoint's lifespan while their mirror fits it (rows), BCE
    starts that mirror cleanly in CE-era runs, and year-0 dates (counts)."""
    from pipeline.agent.date_utils import MAX_PERSON_LIFESPAN
    from pipeline.agent.tools.disambiguation import CONTEMPORANEOUS_RELATION_TYPES
    from pipeline.campaign.handoff_ops import LIFESPAN_SLACK_YEARS

    contemporaneous = ", ".join(f"'{t}'" for t in sorted(CONTEMPORANEOUS_RELATION_TYPES))
    slack = LIFESPAN_SLACK_YEARS
    return f"""
SELECT 'lifespan_row', e.entity_id, coalesce(e.wikidata_id, ''), coalesce(r.start_date, ''), coalesce(r.end_date, ''),
  coalesce(e.source_citations->>'transcript_run', ''), replace(e.name, '|', '/')
FROM entities e JOIN entity_temporal_ranges r ON r.entity_id = e.entity_id AND r.is_primary
  WHERE e.entity_type = 'person' AND (r.start_year > r.end_year OR r.end_year - r.start_year > {MAX_PERSON_LIFESPAN});
WITH p AS (SELECT r.entity_id, r.start_year sy, r.end_year ey FROM entity_temporal_ranges r JOIN entities e USING (entity_id)
           WHERE r.is_primary AND e.entity_type = 'person' AND r.start_year <= r.end_year
             AND r.end_year - r.start_year <= {MAX_PERSON_LIFESPAN})
SELECT DISTINCT 'rel_sign_row', rel.relationship_id, coalesce(rel.temporal_start, ''), coalesce(rel.temporal_end, ''),
  coalesce(rel.source_citations->>'transcript_run', ''), pe.name || ' ' || p.sy || '..' || p.ey,
  replace(s.name || ' -' || rel.relationship_type::text || '-> ' || t.name, '|', '/')
FROM relationships rel JOIN p ON p.entity_id IN (rel.source_entity_id, rel.target_entity_id)
  JOIN entities pe ON pe.entity_id = p.entity_id
  JOIN entities s ON s.entity_id = rel.source_entity_id JOIN entities t ON t.entity_id = rel.target_entity_id
  WHERE rel.relationship_type::text IN ({contemporaneous}) AND (
    (rel.start_year <> 0 AND rel.start_year NOT BETWEEN p.sy - {slack} AND p.ey + {slack}
       AND -rel.start_year BETWEEN p.sy - {slack} AND p.ey + {slack})
    OR (rel.end_year <> 0 AND rel.end_year NOT BETWEEN p.sy - {slack} AND p.ey + {slack}
       AND -rel.end_year BETWEEN p.sy - {slack} AND p.ey + {slack}));
SELECT 'ce_bce_starts',
  (SELECT count(*) FROM entities e JOIN entity_temporal_ranges r ON r.entity_id = e.entity_id AND r.is_primary
     WHERE e.entity_type <> 'person' AND e.source_citations->>'transcript_run' ~ {CE_ERA_RUN_SQL}
       AND r.start_year < 0 AND r.end_year > 0 AND -r.start_year <= r.end_year),
  (SELECT count(*) FROM relationships rel WHERE rel.source_citations->>'transcript_run' ~ {CE_ERA_RUN_SQL}
       AND rel.start_year < 0 AND rel.end_year > 0 AND -rel.start_year <= rel.end_year);
SELECT 'year0', (SELECT count(*) FROM entity_temporal_ranges WHERE start_year = 0 OR end_year = 0),
  (SELECT count(*) FROM relationships WHERE start_year = 0 OR end_year = 0);
"""


def build_sql() -> str:
    jan1 = JAN1_SQL
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
                                 AND (l.geom IS NOT NULL OR l.territory_geom IS NOT NULL))),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM geometry_periods gp WHERE gp.entity_id = e.entity_id
                                 AND (gp.geom IS NOT NULL OR gp.territory_geom IS NOT NULL)))
FROM entities e GROUP BY e.entity_group ORDER BY 2;
SELECT 'jan1_ranges', count(*) FROM entity_temporal_ranges
  WHERE start_date ~ {jan1} OR end_date ~ {jan1};
SELECT 'jan1_relations', count(*) FROM relationships
  WHERE temporal_start ~ {jan1} OR temporal_end ~ {jan1};
SELECT 'jan1_range_row', r.temporal_range_id, coalesce(e.wikidata_id, ''), coalesce(r.start_date, ''),
  coalesce(r.end_date, ''), coalesce(e.source_citations->>'transcript_run', ''), replace(e.name, '|', '/')
FROM entity_temporal_ranges r JOIN entities e USING (entity_id)
  WHERE r.start_date ~ {jan1} OR r.end_date ~ {jan1};
SELECT 'jan1_rel_row', r.relationship_id, coalesce(r.temporal_start, ''), coalesce(r.temporal_end, ''),
  coalesce(r.source_citations->>'transcript_run', ''), replace(coalesce(r.source_citations->>'source_event', ''), '|', '/'),
  replace(s.name || ' -' || r.relationship_type::text || '-> ' || t.name, '|', '/')
FROM relationships r JOIN entities s ON s.entity_id = r.source_entity_id JOIN entities t ON t.entity_id = r.target_entity_id
  WHERE r.temporal_start ~ {jan1} OR r.temporal_end ~ {jan1};
{sign_sql()}
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


# ── -01-01 classification ───────────────────────────────────────────────────
# A DB date of YYYY-01-01 is either genuine (a transcript fact states 1 January of
# that year, or the pipeline copied a day-precision Wikidata date — year-precision
# Wikidata values are already cut to the year) or padded (the extractor wrote a
# year-only / month-only fact as -01-01). Classify each flagged row by tracing it
# back to its handoff and transcript fact.

@dataclass
class Jan1Fix:
    table: str          # e.g. "relationships.temporal_start"
    id: str
    current: str
    correct: str        # == current when the date is genuine; "" = clear it
    run: str
    verdict: str        # padded | stated | wikidata | residue | unknown
    evidence: str


class _Runs:
    """Lazy per-run handoff + transcript context (event facts, fact text, 1-January years)."""

    def __init__(self) -> None:
        self._cache: dict[str, dict | None] = {}
        self._label_index: dict[str, list[tuple[str, dict]]] | None = None

    def get(self, run: str) -> dict | None:
        if not run:
            return None
        if run not in self._cache:
            self._cache[run] = self._load(run)
        return self._cache[run]

    @staticmethod
    def _load(run: str) -> dict | None:
        try:
            doc = json.loads(paths.candidates_path(run).read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return None
        facts = paths.fact_lines(paths.transcript_path(run)) or {}
        events = {e.get("label"): e.get("fact") for e in doc.get("parsed_events") or [] if isinstance(e, dict)}
        return {"doc": doc, "facts": facts, "event_facts": events, "jan1": jan1_years(facts.values())}

    def entity_items(self, label: str) -> list[tuple[str, dict]]:
        if self._label_index is None:
            self._label_index = {}
            for cand in sorted(paths.extractions_dir().glob("*/candidates.json")):
                run = cand.parent.name
                ctx = self.get(run)
                for item in (ctx or {}).get("doc", {}).get("candidate_entities") or []:
                    if isinstance(item, dict):
                        self._label_index.setdefault(item.get("label"), []).append((run, item))
        return self._label_index.get(label, [])


def _judge(ctx: dict, source_event: str | None, value: str) -> tuple[str, str, str]:
    """(verdict, correct value, evidence) for one -01-01 value from a handoff item."""
    n = ctx["event_facts"].get(source_event)
    text = ctx["facts"].get(n) if n is not None else None
    fix = depad(value, text, ctx["jan1"])
    quote = f"fact {n}: {text[:160]}" if text else f"no fact text (source_event={source_event!r})"
    if fix is None:
        return "stated", value, f"1 January stated in the transcript; {quote}"
    return "padded", fix, quote


def classify_jan1(rows: list[list[str]]) -> list[Jan1Fix]:
    runs = _Runs()
    out: list[Jan1Fix] = []
    for r in rows:
        kind = r[0]
        if kind == "jan1_rel_row":
            rel_id, start, end, run, source_event, label = r[1], r[2], r[3], r[4], r[5], "|".join(r[6:])
            ctx = runs.get(run)
            for col, value in (("temporal_start", start), ("temporal_end", end)):
                if not is_jan1(value):
                    continue
                if ctx is None:
                    out.append(Jan1Fix(f"relationships.{col}", rel_id, value, value, run, "unknown",
                                       f"{label}: no handoff for run {run!r}"))
                    continue
                verdict, correct, why = _judge(ctx, source_event or None, value)
                out.append(Jan1Fix(f"relationships.{col}", rel_id, value, correct, run, verdict, f"{label}: {why}"))
        elif kind == "jan1_range_row":
            range_id, qid, start, end, own_run, name = r[1], r[2], r[3], r[4], r[5], "|".join(r[6:])
            judged: dict[str, Jan1Fix] = {}
            for key, value in (("start_date", start), ("end_date", end)):
                if not is_jan1(value):
                    continue
                hits = [(run, it) for run, it in runs.entity_items(name) if it.get(key) == value]
                hits.sort(key=lambda h: h[0] != own_run)
                if hits:
                    run, item = hits[0]
                    verdict, correct, why = _judge(runs.get(run), item.get("source_event"), value)
                    judged[key] = Jan1Fix(f"entity_temporal_ranges.{key}", range_id, value, correct, run, verdict,
                                          f"{name}: handoff {key}; {why}")
            for key, value in (("start_date", start), ("end_date", end)):
                if not is_jan1(value):
                    continue
                other = judged.get("end_date" if key == "start_date" else "start_date")
                if key in judged:
                    out.append(judged[key])
                elif other is not None and other.current == value:
                    # The commit writer mirrors a point-in-time event's one bound onto the other.
                    out.append(Jan1Fix(f"entity_temporal_ranges.{key}", range_id, value, other.correct, other.run,
                                       other.verdict, f"{name}: {key} mirrored from the other bound; "
                                       + other.evidence.split(": ", 1)[1]))
                elif qid:
                    out.append(Jan1Fix(f"entity_temporal_ranges.{key}", range_id, value, value, own_run, "wikidata",
                                       f"{name}: not in any handoff, so copied from Wikidata {qid} "
                                       "(only day-precision values keep -01-01)"))
                else:
                    out.append(Jan1Fix(f"entity_temporal_ranges.{key}", range_id, value, "", own_run, "residue",
                                       f"{name}: not in any handoff and the entity has no QID now: a Wikidata date "
                                       "left behind when a wrong QID was cleared"))
    return out


PADDED_VERDICTS = {"padded", "residue"}


def write_jan1_csv(fixes: list[Jan1Fix], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "id", "current value", "correct value", "source run", "evidence"])
        for x in fixes:
            w.writerow([x.table, x.id, x.current, x.correct, x.run, f"{x.verdict.upper()}: {x.evidence}"])


# ── impossible person lifespans ─────────────────────────────────────────────
# Each bound is traced to its source: a handoff item of that name (any run) that
# gives the same year, else Wikidata (the pipeline fills a missing bound from the
# entity's QID). Verdicts:
#   sign-handoff   crosses year 0 and the bad sign is in a handoff (the gatherer's minus)
#   sign-wikidata  crosses year 0 and a bound came from Wikidata (an unsigned BCE
#                  death on Wikidata, or a century value such as -0100..0100)
#   mixed          one bound from the handoff, the other from Wikidata: a namesake
#                  QID's date, or a century-precision birth, glued to the transcript's
#   wikidata       both bounds from Wikidata (century precision, or Wikidata's own data)
#   handoff        both bounds from the handoff: a reign/floruit/radiocarbon window
#                  or a traditional lifespan, given as birth/death
# "century?" marks a Wikidata-sourced bound shaped like a century value (zero-padded
# "-0300"/"0601", or a round X00/X01): likely precision 7, not a year.

@dataclass
class LifespanFinding:
    kind: str           # lifespan | relation
    id: str
    name: str
    start: str
    end: str
    run: str
    verdict: str
    evidence: str


_CENTURY_SHAPED = re.compile(r"^-?(0\d{3}|\d*0[01])$")


def _same_year(a: str | None, b: str | None) -> bool:
    from pipeline.agent.tools.disambiguation import era_year

    return bool(a) and bool(b) and era_year(a) == era_year(b)


def classify_lifespans(rows: list[list[str]]) -> list[LifespanFinding]:
    from pipeline.agent.tools.disambiguation import era_year

    runs = _Runs()
    out: list[LifespanFinding] = []
    for r in rows:
        if r[0] == "rel_sign_row":
            rel_id, start, end, run, person, label = r[1], r[2], r[3], r[4], r[5], "|".join(r[6:])
            out.append(LifespanFinding("relation", rel_id, label, start, end, run, "relation-sign",
                                       f"a date lies outside {person} while its mirror lies inside"))
            continue
        if r[0] != "lifespan_row":
            continue
        eid, qid, start, end, run, name = r[1], r[2], r[3], r[4], r[5], "|".join(r[6:])
        items = runs.entity_items(name)
        src = {}
        for key, value in (("start_date", start), ("end_date", end)):
            if any(_same_year(value, it.get(key)) for _, it in items):
                src[key] = "handoff"
            else:
                src[key] = "wikidata" if qid else "unknown"
        sy, ey = era_year(start), era_year(end)
        sources = set(src.values())
        if sy is not None and ey is not None and sy < 0 < ey:
            verdict = "sign-handoff" if sources == {"handoff"} else "sign-wikidata"
        elif sources == {"handoff"}:
            verdict = "handoff"
        elif "handoff" in sources:
            verdict = "mixed"
        else:
            verdict = "wikidata"
        century = [k.split("_")[0] for k, v in (("start_date", start), ("end_date", end))
                   if src[k] == "wikidata" and _CENTURY_SHAPED.match(v or "")]
        evidence = (f"start {start or '-'} from {src['start_date']}, end {end or '-'} from {src['end_date']}"
                    + (f"; century? {'+'.join(century)}" if century else "")
                    + (f"; QID {qid}" if qid else ""))
        out.append(LifespanFinding("lifespan", eid, name, start, end, run, verdict, evidence))
    return out


def write_sign_csv(findings: list[LifespanFinding], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "id", "name", "start", "end", "source run", "verdict", "evidence"])
        for x in findings:
            w.writerow([x.kind, x.id, x.name, x.start, x.end, x.run, x.verdict, x.evidence])


def _sign_lines(rows: list[list[str]], by: dict[str, list[list[str]]]) -> list[str]:
    findings = classify_lifespans([r for r in rows if r and r[0] in ("lifespan_row", "rel_sign_row")])
    spans = [x for x in findings if x.kind == "lifespan"]
    rels = [x for x in findings if x.kind == "relation"]
    counts: dict[str, int] = {}
    for x in spans:
        counts[x.verdict] = counts.get(x.verdict, 0) + 1
    century = sum(1 for x in spans if "century?" in x.evidence)
    order = ("sign-handoff", "sign-wikidata", "mixed", "wikidata", "handoff")
    detail = " ".join(f"{k}={counts[k]}" for k in order if counts.get(k))
    ce = (by.get("ce_bce_starts") or [["0", "0"]])[0] + ["0"]
    y0 = (by.get("year0") or [["0", "0"]])[0] + ["0"]
    return [
        f"{'person lifespans >110y':<26}{len(spans)}" + (f"   ({detail}; century-shaped Wikidata bound={century})"
                                                        if spans else "") + "   (target 0)",
        f"{'relation sign slips':<26}{len({x.id for x in rels})}   (a year outside a person endpoint's lifespan "
        "whose mirror fits it; triage: also a namesake's dates)",
        f"{'CE-era BCE starts':<26}entities={ce[0]} relations={ce[1]}   (mirror also ordered; check the minus)",
        f"{'year-0 dates':<26}ranges={y0[0]} relations={y0[1]}",
    ]


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
    detail = [r for r in rows if r and r[0] in ("jan1_range_row", "jan1_rel_row")]
    jan1_line = f"ranges={one('jan1_ranges')[0]} relations={one('jan1_relations')[0]}"
    if detail:
        fixes = classify_jan1(detail)
        bad_ranges = {x.id for x in fixes if x.verdict in PADDED_VERDICTS and x.table.startswith("entity_temporal")}
        bad_rels = {x.id for x in fixes if x.verdict in PADDED_VERDICTS and x.table.startswith("relationships")}
        jan1_line = (f"ranges={len(bad_ranges)} relations={len(bad_rels)} padded "
                     f"(all -01-01: {jan1_line}; the rest are stated in a fact or Wikidata day-precision)")
    out = [
        f"{'entities':<26}{total}",
        f"{'with QID':<26}{_pct(qid, q_total)}",
        f"{'relations':<26}{one('relations')[0]}",
        f"{'orphan entities':<26}{_pct(orphans, o_total)}   (target <15%)",
        f"{'chronicles':<26}{chron[0]}   distinct impact={chron[1]} (target >10)",
        f"{'fabricated -01-01 dates':<26}{jan1_line}   (target ~0)",
        f"{'off-taxonomy types':<26}{one('offtax')[0]}   (target 0)",
    ]
    if any(k in by for k in ("lifespan_row", "rel_sign_row", "ce_bce_starts", "year0")):
        out += _sign_lines(rows, by)
    out.append("geo by group (any = geo-ref or located; map = geometry_periods, what the SPA map renders):")
    for group, n, georef, located, any_geo, *rest in by.get("geo", []):
        target = "   (target >80%)" if group == "PLACE" else ""
        on_map = f" map={_pct(int(rest[0]), int(n))}" if rest else ""
        out.append(f"  {group:<10}{_pct(int(any_geo), int(n))}  georef={georef} located={located}{on_map}{target}")
    out.append("top entity types: " + ", ".join(f"{t}={c}" for t, c in by.get("type", [])))
    return out
