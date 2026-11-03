#!/usr/bin/env python3
"""Date backfill: give undated entities a start (and end) year from their own Wikidata item.

The map hides an entity whose range has no start year (backfill_geo needs one
for the point's period), so this fills entity_temporal_ranges for entities that
have a QID and no range with a start year. Dates come only from the entity's own
item, never from a neighbour or a guess.

  type                                    start            end
  person                                  P569 birth       P570 death              [1]
  political_entity, military_unit         P571 inception,  P576 dissolved,         [2]
                                            else P580       else P582
  dynasty, diplomatic_relationship,       P571, else P580  P576, else P582         [3]
    intellectual_movement
  archaeological_culture                  P580, else P571  P582, else P576         [3]
  educational_institution,                P571             P576 (else open)
    religious_movement
  city, infrastructure_monument,          P571             P576 destroyed or       [4]
    extraction_infra                                         abandoned (else open)
  event_*, migration, epidemic_disease    P580             P582 (P585 must fall    [3]
                                                             inside), else P585
                                                             as a point
  cultural_work, religious_text,          P577, else P571  open
    legal_code
  technology                              P575, else P571  open
  language, natural_resource, social_class, trade_route,  left out: their items'
    currency_monetary_system                               dates are conventions,
                                                           absent, or about one
                                                           aspect (pound sterling's
                                                           P580 is the Bank of
                                                           England's founding)
  P1249 (earliest written record) is cached and counted but never stored: it
  is when a place is first attested, not when it began.

  [1] Someone born before 1910 with no usable death date is skipped: an open
      end would show them alive today.
  [2] An open end only when the item is not a former thing (P31* historical
      country, former administrative unit, historical region …).
  [3] An end is required.
  [4] An open end only when the item is not an ancient city, archaeological
      site, ruin, ghost town or other former settlement.

Every value is the item's own, stored as given: never shifted, never invented.

* Rank: deprecated values are ignored; a preferred value beats normal ones,
  then the finest precision wins.
* Qualifiers: a value scoped to a part or aspect (P518 applies to part, P642,
  P1013, P5102, P3831, P2868, P794, P2210, P276, or a P31 other than the
  pre-1584 calendar marker) or marked disputed is ignored, so a city's later
  "city status" inception neither starts it nor conflicts. circa,
  approximately, refine-date and earliest/latest-date qualifiers give
  date_confidence 'medium'. A pre-1584 date flagged as maybe in the wrong
  calendar keeps only its year. An "unknown value" statement beside a value
  means the value is in doubt: skipped.
* Precision: year or finer is stored as is (month/day kept in start_date);
  a decade is stored with date_confidence 'low'; a century or coarser is
  skipped and listed. --century follows the importer instead
  (min_storable_precision / storable_wikidata_dates): a non-person's century
  is stored as the year Wikidata wrote for it, date_confidence 'low', notes
  '… century:start[+end]'; persons and millennia stay skipped. It writes
  planned-century.csv / rollback-century.sql.
* Conflicts: two non-deprecated values of a property (or of the type's
  alternative properties, e.g. P571 against P580) more than 10 years apart,
  allowing for their precision, skip the entity.
* BCE: Wikidata's '-0044' is 44 BCE and is stored as -44, the repo's
  convention (Julius Caesar's death row says -44).
* Evidence guard: the entity's own dated facts in the DB (its relationships,
  chronicle entries, geometry periods, OHM ref years, timeline entries, years
  named in its summary or description, and an end year its row already has)
  must not predate the start. A fact spanning years counts by its last year,
  so the entity only has to exist by then. This catches the modern re-founding
  trap (a historical kingdom whose item's P571 is 1918). A non-person's
  Wikidata end more than 10 years before the latest fact is skipped too (the
  Brigantes "ended" in 60 CE but fought Cerialis in 71), a work more than 300
  years older than anything known about it is a namesake (al-Bitruji's On the
  Sphere linked to Archimedes'), and a person's lifespan must touch a fact.
* SPOT_CHECK_REJECTS lists the few items a manual check found wrong for their
  entity although every rule passed; keyed by QID, so a re-pointed entity is
  planned again.
* An existing primary row with a null start is updated, never duplicated, and
  keeps its own end year; a Wikidata end more than 10 years from it skips the
  entity.
* QIDs in doubt are skipped: needs_review rows flagged identity_audit:qid_suspect*,
  identity_audit:place_namesake, namesake_ambiguous or low_wikidata_match.

Rows get date_method 'source_database', notes 'backfill_dates:<start prop>[,<end prop>]'
and date_confidence high | medium (approximate, or values 1-10 years apart) |
low (decade). Writes go to entity_temporal_ranges only; its trigger derives
start_year/end_year from start_date/end_date, so the dates are what is written.

Dry run by default; --apply writes in a single transaction after appending
undo statements to rollback.sql, then rebuilds the materialized timeline of
the entities it dated (entity_timeline_entries; observers do not fire on raw
SQL). Re-runnable: dated entities drop out of scope, and an entity that gained
a QID since is picked up. Wikidata claims are cached in
output/audit/cache/wd-date-claims.jsonl (delete it to refetch).

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.backfill_dates            # dry run
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.backfill_dates --apply    # write
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import psycopg

from pipeline.agent.tools.disambiguation import era_year
from pipeline.agent.tools.wikidata import (
    DECADE_PRECISION,
    _wikidata_date,
    min_storable_precision,
    storable_wikidata_dates,
)
from pipeline.audit.dates import text_years
from pipeline.audit.wd import API, QID_RE, WikidataClient, _parse_time

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
METHOD = "source_database"  # DateResolutionMethod::SourceDatabase
NOTE = "backfill_dates"
CLAIMS_CACHE = "wd-date-claims.jsonl"
COMPOSE = ["docker", "compose", "-f", str(_REPO_ROOT / "docker" / "docker-compose.yml")]

# P1249 (earliest written record) is cached for reporting only: it is when a
# place is first attested, not when it began.
PROPS = ("P569", "P570", "P571", "P576", "P580", "P582", "P585", "P577", "P575", "P1249")
CACHE_VERSION = 2
# Qualifiers that narrow what a value is about (applies to part, of, criterion
# used, nature of statement, object/subject has role, as, relative to,
# location): such a value is not the item's own start or end.
SCOPE_QUALIFIERS = {"P518", "P642", "P1013", "P5102", "P3831", "P2868", "P794", "P2210", "P276"}
# Qualifiers that make a value approximate (sourcing circumstances, refine
# date, earliest/latest date): stored with date_confidence 'medium'.
UNCERTAIN_QUALIFIERS = {"P1480", "P4241", "P1319", "P1326"}
DISPUTED = "Q18912752"       # P1480 sourcing circumstances: disputed
GREGORIAN_PRE_1584 = "Q26961029"  # P31 marker: day/month may be in the wrong calendar
CONFLICT_YEARS = 10          # values further apart than this are a conflict
START_SLACK = 0              # a start may follow the earliest fact by this much
END_SLACK = 10               # a non-person's end may precede the latest fact by this much
WORK_GAP = 300               # a work this much older than its earliest fact is a namesake
WORK_TYPES = {"cultural_work", "religious_text", "legal_code"}
LIFESPAN_SLACK = 30          # a lifespan must come this close to some fact
MAX_LIFESPAN = 120
ALIVE_BORN_AFTER = 1910      # born earlier with no death date: not alive today
DOUBT_FLAGS = ("identity_audit:place_namesake", "namesake_ambiguous", "low_wikidata_match")
DOUBT_PREFIX = "identity_audit:qid_suspect"
# Items whose dates the rules accept but a manual spot check found wrong for
# the entity (keyed by QID, so re-pointing the entity lifts the block).
SPOT_CHECK_REJECTS = {
    "Q1240870": "item_is_1915_recapture",   # Siege of Przemyśl: entity is the 133-day 1914-15 siege
    "Q608293": "inception_not_founding",     # Woodstock NY: P571 1829, but the town was formed in 1787
    "Q711949": "end_sign_error",             # Liaoning bronze dagger culture: P582 +200 century, ended c. 200 BCE
    "Q83418": "start_predates_normans",      # Normans: P580 '700' century, open end; they date from the 10th c.
}

# Classes whose items no longer exist: an open end would show them today.
FORMER_ROOTS = {
    "Q3024240",   # historical country
    "Q19953632",  # former administrative territorial entity
    "Q1620908",   # historical region
    "Q28171280",  # ancient civilization
    "Q15661340",  # ancient city
    "Q839954",    # archaeological site
    "Q109607",    # ruins
    "Q74047",     # ghost town
    "Q2974842",   # lost city
    "Q15893266",  # former entity
}


@dataclass(frozen=True)
class Rule:
    starts: tuple[str, ...]
    ends: tuple[str, ...]
    end: str  # person | former | required | open | place | event | none


_POLITY = Rule(("P571", "P580"), ("P576", "P582"), "former")
_SPAN = Rule(("P571", "P580"), ("P576", "P582"), "required")
_INSTITUTION = Rule(("P571",), ("P576",), "open")
_PLACE = Rule(("P571",), ("P576",), "place")
_EVENT = Rule(("P580",), ("P582",), "event")  # else P585 as a point
_WORK = Rule(("P577", "P571"), (), "none")

RULES: dict[str, Rule] = {
    "person": Rule(("P569",), ("P570",), "person"),
    "political_entity": _POLITY,
    "military_unit": _POLITY,
    "dynasty": _SPAN,
    "diplomatic_relationship": _SPAN,
    "intellectual_movement": _SPAN,
    "archaeological_culture": Rule(("P580", "P571"), ("P582", "P576"), "required"),
    "educational_institution": _INSTITUTION,
    "religious_movement": _INSTITUTION,
    "city": _PLACE,
    "infrastructure_monument": _PLACE,
    "extraction_infra": _PLACE,
    **{t: _EVENT for t in ("event_war", "event_battle", "event_treaty", "event_rebellion",
                           "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
                           "migration", "epidemic_disease")},
    "cultural_work": _WORK,
    "religious_text": _WORK,
    "legal_code": _WORK,
    "technology": Rule(("P575", "P571"), (), "none"),
}


# ── Wikidata values ────────────────────────────────────────────────────────────
def parse_statement(st: dict[str, Any]) -> dict[str, Any] | None:
    """A non-deprecated time statement: year 'y', precision 'p', rank 'r', raw
    time 't' and qualifiers 'q' ({prop: [item ids]}); {'some': True} for an
    unknown value; None otherwise."""
    if not isinstance(st, dict) or st.get("rank") == "deprecated":
        return None
    snak = st.get("mainsnak") or {}
    out: dict[str, Any] = {"r": st.get("rank", "normal")}
    if snak.get("snaktype") == "somevalue":
        out["some"] = True
        return out
    try:
        value = snak["datavalue"]["value"]
    except (KeyError, TypeError):
        return None
    parsed = _parse_time(value) if isinstance(value, dict) else None
    if not parsed or parsed[0] == 0:
        return None
    quals = {prop: [_item_id(q) for q in snaks] for prop, snaks in (st.get("qualifiers") or {}).items()}
    out.update(y=parsed[0], p=parsed[1], t=value.get("time", ""), q=quals)
    return out


def _item_id(snak: Any) -> str | None:
    value = ((snak.get("datavalue") or {}).get("value")) if isinstance(snak, dict) else None
    return value.get("id") if isinstance(value, dict) else None


def parse_claims(ent: dict[str, Any]) -> dict[str, Any]:
    claims = ent.get("claims") or {}
    dates = {}
    for prop in PROPS:
        vals = [v for v in (parse_statement(s) for s in claims.get(prop) or []) if v]
        if vals:
            dates[prop] = vals
    return {"status": "ok", "v": CACHE_VERSION, "dates": dates}


def kind(v: dict) -> str:
    """'some' (unknown value), 'scope' (about a part or aspect), 'disputed',
    'uncertain' (circa, approximately, refined, bounded) or 'plain'."""
    if "y" not in v:
        return "some"
    q = v.get("q") or {}
    if SCOPE_QUALIFIERS & set(q) or any(x != GREGORIAN_PRE_1584 for x in q.get("P31", [])):
        return "scope"
    if DISPUTED in q.get("P1480", []):
        return "disputed"
    if UNCERTAIN_QUALIFIERS & set(q):
        return "uncertain"
    return "plain"


def fetch_claims(client: WikidataClient, qids: list[str]) -> dict[str, dict[str, Any]]:
    """Every non-deprecated date statement of each item, cached beside the audit's
    entity cache and fetched through the audit client (same User-Agent, rate
    limit and backoff)."""
    cache = {q: r for q, r in client._load_jsonl(CLAIMS_CACHE, "qid").items()
             if r.get("status") != "ok" or r.get("v") == CACHE_VERSION}
    todo = sorted({q for q in qids if QID_RE.match(q) and q not in cache}, key=lambda q: int(q[1:]))
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        for attempt in range(6):  # maxlag: yield to a lagging Wikidata, as RULES.md asks
            data = client._get(API, {"action": "wbgetentities", "ids": "|".join(batch),
                                     "props": "info|claims", "format": "json", "maxlag": "5"}).json()
            if (data.get("error") or {}).get("code") != "maxlag":
                break
            time.sleep(5 * (attempt + 1))
        if "entities" not in data:
            # Still lagging (or another API error): never cache a failure as "missing",
            # or a later run silently skips real items. They are fetched again next run.
            print(f"   claims batch {i // 50} not fetched: {(data.get('error') or {}).get('code', 'no entities')}",
                  flush=True)
            continue
        got: dict[str, dict[str, Any]] = {}
        for key, ent in (data.get("entities") or {}).items():
            if "missing" in ent:
                got[ent.get("id", key)] = {"status": "missing"}
                continue
            real = ent.get("id", key)
            got[real] = parse_claims(ent)
            src = (ent.get("redirects") or {}).get("from") or (key if key != real else None)
            if src:
                got[src] = {"status": "redirect", "redirect_to": real}
        stamp = time_stamp()
        new = [{"qid": q, "fetched": stamp, **r} for q, r in got.items() if q not in cache]
        for rec in new:
            cache[rec["qid"]] = rec
        client._append(CLAIMS_CACHE, new)
        if (i // 50) % 20 == 19:
            print(f"   claims {min(i + 50, len(todo))}/{len(todo)}", flush=True)
    return cache


def time_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def resolve(cache: dict[str, dict], qid: str) -> tuple[str, dict | None]:
    seen: set[str] = set()
    rec = cache.get(qid)
    while rec and rec.get("status") == "redirect" and qid not in seen:
        seen.add(qid)
        qid = rec["redirect_to"]
        rec = cache.get(qid)
    return qid, rec


def interval(year: int, precision: int) -> tuple[int, int]:
    """The years a value can mean: a decade, century or millennium as Wikidata
    shows it ('-0480' at decade precision is 489-480 BCE)."""
    if precision >= 9:
        return year, year
    size = {8: 10, 7: 100, 6: 1000}.get(precision)
    if size is None:
        return -10**6, 10**6
    if precision == 8:
        lo = abs(year) // 10 * 10
        return (lo, lo + 9) if year > 0 else (-lo - 9, -lo)
    n = (abs(year) - 1) // size
    lo, hi = n * size + 1, (n + 1) * size
    return (lo, hi) if year > 0 else (-hi, -lo)


def gap(a: dict, b: dict) -> int:
    (alo, ahi), (blo, bhi) = interval(a["y"], a["p"]), interval(b["y"], b["p"])
    return max(0, max(alo, blo) - min(ahi, bhi))


def usable(values: list[dict]) -> list[dict]:
    return [v for v in values if kind(v) in ("plain", "uncertain")]


def pick(values: list[dict], floor: int = DECADE_PRECISION) -> tuple[dict | None, str]:
    """The value to store and '', or None and why: 'unknown' (Wikidata says the
    value is unknown, alone or beside a value), 'qualified' (only values about a
    part or aspect, or disputed ones), 'conflict', 'coarse' or 'none'."""
    if any(kind(v) == "some" for v in values):
        return None, "unknown"
    known = usable(values)
    if not known:
        return None, "qualified" if values else "none"
    if any(gap(a, b) > CONFLICT_YEARS for a, b in combinations(known, 2)):
        return None, "conflict"
    pool = [v for v in known if v["r"] == "preferred"] or known
    best = max(pool, key=lambda v: v["p"])  # first of the finest
    if best["p"] < floor:
        return None, "coarse"
    return best, ""


def confidence(chosen: dict, values: list[dict]) -> str:
    if chosen["p"] <= 8:
        return "low"
    if kind(chosen) == "uncertain" or any(v["y"] != chosen["y"] for v in usable(values)):
        return "medium"
    return "high"


def date_text(v: dict) -> str:
    """'-490', '1066', '1066-10', '1066-10-14', '-0044-03-15' (4-digit years once
    a month is known). A pre-1584 date flagged as possibly in the wrong calendar
    keeps only its year."""
    y, p = v["y"], v["p"]
    m = re.match(r"^[+-]?\d+-(\d\d)-(\d\d)", v.get("t", ""))
    if GREGORIAN_PRE_1584 in (v.get("q") or {}).get("P31", []):
        return str(y)
    if p >= 10 and m and m.group(1) != "00":
        head = f"{'-' if y < 0 else ''}{abs(y):04d}-{m.group(1)}"
        return f"{head}-{m.group(2)}" if p >= 11 and m.group(2) != "00" else head
    return str(y)


CONF_RANK = {"low": 0, "medium": 1, "high": 2}


# ── one entity ─────────────────────────────────────────────────────────────────
def in_doubt(e: dict) -> bool:
    if e.get("verification_status") != "needs_review":
        return False
    flags = e.get("flags") or []
    return any(isinstance(f, str) and (f.startswith(DOUBT_PREFIX) or f in DOUBT_FLAGS) for f in flags)


def choose(dates: dict, props: tuple[str, ...],
           floor: int = DECADE_PRECISION) -> tuple[str | None, dict | None, str]:
    """(prop, value, why-not) for the first property with a usable value, checked
    against the type's alternative properties."""
    present = [p for p in props if dates.get(p)]
    if not present:
        return None, None, "none"
    prop = present[0]
    value, why = pick(dates[prop], floor)
    if value is None:
        return prop, None, why
    for other in present[1:]:
        if any(gap(value, v) > CONFLICT_YEARS for v in usable(dates[other])):
            return prop, None, f"prop_conflict:{prop}/{other}"
    return prop, value, ""


def fact_bounds(facts: list[tuple]) -> tuple[tuple | None, tuple | None]:
    """The fact the entity must exist by (earliest last-year) and the one it
    must still exist at (latest first-year), as (year, label)."""
    by = [((hi if hi is not None else lo), label) for lo, hi, label in facts]
    at = [((lo if lo is not None else hi), label) for lo, hi, label in facts]
    by = [f for f in by if f[0] is not None]
    at = [f for f in at if f[0] is not None]
    return (min(by) if by else None), (max(at) if at else None)


def century_year(v: dict, entity_type: str) -> int | None:
    """The year the importer stores for a value (storable_wikidata_dates then
    era_year): a century is kept as the year Wikidata wrote for it ('+0601' or
    '+0700' for the 7th century, '-0100' for the 1st century BCE); None when
    the importer would not store it (a person's century)."""
    raw = _wikidata_date({"time": v["t"], "precision": v["p"]})
    stored, _ = storable_wikidata_dates({"start_date": raw, "start_precision": v["p"]}, entity_type)
    return era_year(stored)


def plan_entity(e: dict, claims: dict | None, former: bool, facts: list[tuple],
                century: bool = False) -> dict:
    """The row to write for one entity, or a skip with its reason.

    e: entity_type, wikidata_id, verification_status, flags, range_id,
       row_end_year, row_end_date.
    claims: the item's {'status', 'dates'} record (redirects already followed).
    former: the item is an instance of a FORMER_ROOTS class.
    facts: (start_year, end_year, label) of the entity's dated facts in the DB.
    century: also store century precision for non-person types, as the
       importer does (min_storable_precision); persons are left alone."""
    def skip(reason: str, **kw) -> dict:
        return {"action": "skip", "reason": reason, **kw}

    rule = RULES.get(e["entity_type"])
    if rule is None:
        return skip("type_not_covered")
    if century and e["entity_type"] == "person":
        return skip("person_not_in_century_pass")
    floor = min_storable_precision(e["entity_type"]) if century else DECADE_PRECISION
    if in_doubt(e):
        return skip("qid_in_doubt")
    if not claims or claims.get("status") != "ok":
        return skip("qid_missing")
    dates = claims.get("dates") or {}

    # ── start and end from the item ──────────────────────────────────────────
    reject = SPOT_CHECK_REJECTS.get(e["wikidata_id"])
    if reject:
        return skip(f"spot_check:{reject}")

    point = rule.end == "event" and not dates.get("P580")
    if point:
        sprop, start, why = choose(dates, ("P585",), floor)
        eprop, end, ewhy = sprop, start, why
    else:
        sprop, start, why = choose(dates, rule.starts, floor)
        eprop, end, ewhy = (choose(dates, rule.ends, floor) if rule.ends else (None, None, "none"))
        if rule.end == "event" and start is not None and end is not None:
            if any(not (start["y"] - CONFLICT_YEARS <= v["y"] <= end["y"] + CONFLICT_YEARS)
                   for v in usable(dates.get("P585", []))):
                return skip("start_prop_conflict:P580/P585", start_prop=sprop)
    if start is None:
        return skip(f"start_{why}" + (f":{sprop}" if sprop and ":" not in why else ""), start_prop=sprop)
    if end is None and (ewhy in ("conflict", "coarse", "qualified") or ewhy.startswith("prop_conflict")):
        return skip(f"end_{ewhy}" + (f":{eprop}" if ":" not in ewhy else ""), start_prop=sprop, end_prop=eprop)

    plan = {"action": "update" if e.get("range_id") else "insert", "reason": "",
            "start_prop": sprop, "start": start["y"], "start_date": date_text(start),
            "end_prop": eprop if end is not None else None,
            "end": end["y"] if end is not None else None,
            "end_date": date_text(end) if end is not None else None,
            "confidence": confidence(start, dates[sprop]), "start_precision": start["p"]}
    coarse = [side for side, v in (("start", start), ("end", end)) if v is not None and v["p"] < DECADE_PRECISION]
    for side in coarse:  # stored exactly as the importer would store it
        year = century_year(start if side == "start" else end, e["entity_type"])
        if year is None:
            return skip(f"{side}_not_storable", **_keep(plan))
        plan[side], plan[f"{side}_date"] = year, str(year)

    # ── an end year the row already has wins; it must agree ─────────────────
    row_end = e.get("row_end_year")
    if row_end is not None:
        if plan["start"] > row_end:
            return skip("start_after_row_end", **_keep(plan))
        if end is not None and gap(end, {"y": row_end, "p": 9}) > CONFLICT_YEARS:
            return skip("end_disagrees_with_row", **_keep(plan))
        plan.update(end=row_end, end_date=e.get("row_end_date") or str(row_end), end_prop="row")
    elif end is not None:
        plan["confidence"] = min(plan["confidence"], confidence(end, dates[eprop]), key=CONF_RANK.get)

    # ── an open end must be true ─────────────────────────────────────────────
    if plan["end"] is None:
        if ewhy == "unknown":  # Wikidata: it ended, date unknown
            return skip("death_unknown" if rule.end == "person" else "end_unknown", **_keep(plan))
        if rule.end == "person" and start["y"] < ALIVE_BORN_AFTER:
            return skip("no_death_date", **_keep(plan))
        if rule.end in ("required", "event"):
            return skip("no_end_date", **_keep(plan))
        if rule.end in ("former", "place") and former:
            return skip("no_end_former", **_keep(plan))

    if plan["end"] is not None and plan["end"] < plan["start"]:
        return skip("end_before_start", **_keep(plan))
    if rule.end == "person" and plan["end"] is not None and plan["end"] - plan["start"] > MAX_LIFESPAN:
        return skip("lifespan_over_120", **_keep(plan))

    # ── the entity's own dated facts must not predate it ─────────────────────
    earliest, latest = fact_bounds(facts)
    plan["earliest"] = f"{earliest[0]} {earliest[1]}" if earliest else ""
    plan["latest"] = f"{latest[0]} {latest[1]}" if latest else ""
    if earliest and plan["start"] > earliest[0] + START_SLACK:
        return skip("start_after_evidence", **_keep(plan))
    if e["entity_type"] in WORK_TYPES and earliest and plan["start"] < earliest[0] - WORK_GAP:
        return skip("start_far_before_evidence", **_keep(plan))
    if rule.end == "person":
        hi = plan["end"] if plan["end"] is not None else plan["start"] + 100
        if facts and not any(_touches(lo, fhi, plan["start"], hi) for lo, fhi, _ in facts):
            return skip("lifespan_misses_evidence", **_keep(plan))
    elif plan["end_prop"] not in (None, "row") and latest and plan["end"] < latest[0] - END_SLACK:
        return skip("end_before_evidence", **_keep(plan))
    if point:
        plan["point"] = True
    sides = [side for side in coarse if side == "start" or plan["end_prop"] not in (None, "row")]
    if sides:
        plan["precision_note"] = "century:" + "+".join(sides)
    return plan


def _keep(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if k not in ("action", "reason")}


def _touches(lo: int | None, hi: int | None, start: int, end: int) -> bool:
    lo = lo if lo is not None else hi
    hi = hi if hi is not None else lo
    return lo - LIFESPAN_SLACK <= end and hi + LIFESPAN_SLACK >= start


# ── DB ─────────────────────────────────────────────────────────────────────────
def load_state(cur) -> list[dict]:
    """Entities with a QID and no range with a start year, plus their primary row."""
    cur.execute("""
        SELECT e.entity_id::text AS entity_id, e.name, e.entity_type::text AS entity_type,
               e.wikidata_id, e.verification_status::text AS verification_status,
               CASE WHEN jsonb_typeof(e.attributes->'validation_flags') = 'array'
                    THEN e.attributes->'validation_flags' ELSE '[]'::jsonb END AS flags,
               e.summary, e.description,
               t.temporal_range_id::text AS range_id, t.end_year AS row_end_year,
               t.end_date AS row_end_date, t.date_method, t.date_confidence, t.notes,
               t.duration_type, t.updated_at
        FROM entities e
        LEFT JOIN entity_temporal_ranges t ON t.entity_id = e.entity_id AND t.is_primary
        WHERE e.wikidata_id IS NOT NULL AND e.wikidata_id <> ''
          AND NOT EXISTS (SELECT 1 FROM entity_temporal_ranges x
                          WHERE x.entity_id = e.entity_id AND x.start_year IS NOT NULL)
        ORDER BY e.entity_id
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_facts(cur, rows: list[dict]) -> dict[str, list[tuple]]:
    """Each entity's dated facts: (start_year, end_year, label)."""
    ids = [r["entity_id"] for r in rows]
    cur.execute("""
        WITH ids AS (SELECT unnest(%(ids)s::uuid[]) AS id)
        SELECT r.source_entity_id::text, r.start_year, r.end_year,
               'rel ' || r.relationship_type || ' → ' || o.name
        FROM relationships r JOIN ids ON ids.id = r.source_entity_id
        JOIN entities o ON o.entity_id = r.target_entity_id
        WHERE r.start_year IS NOT NULL OR r.end_year IS NOT NULL
        UNION ALL
        SELECT r.target_entity_id::text, r.start_year, r.end_year,
               'rel ' || o.name || ' ' || r.relationship_type || ' →'
        FROM relationships r JOIN ids ON ids.id = r.target_entity_id
        JOIN entities o ON o.entity_id = r.source_entity_id
        WHERE r.start_year IS NOT NULL OR r.end_year IS NOT NULL
        UNION ALL
        SELECT c.entity_id::text, ce.start_year, ce.end_year,
               'chronicle ' || left(regexp_replace(coalesce(ce.narrative_text, ''), '\\s+', ' ', 'g'), 50)
        FROM chronicle_entry_entities c JOIN ids ON ids.id = c.entity_id
        JOIN chronicle_entries ce ON ce.entry_id = c.entry_id
        WHERE ce.start_year IS NOT NULL OR ce.end_year IS NOT NULL
        UNION ALL
        SELECT g.entity_id::text, g.start_year, g.end_year,
               'geometry ' || coalesce(g.created_by, g.provenance_mode::text, '')
        FROM geometry_periods g JOIN ids ON ids.id = g.entity_id
        WHERE g.start_year IS NOT NULL OR g.end_year IS NOT NULL
        UNION ALL
        SELECT g.entity_id::text, g.temporal_start_year, g.temporal_end_year,
               'geo_ref ' || g.provider::text || ' ' || g.external_type::text || '/' || g.external_id
        FROM entity_geo_refs g JOIN ids ON ids.id = g.entity_id
        WHERE g.is_active AND (g.temporal_start_year IS NOT NULL OR g.temporal_end_year IS NOT NULL)
        UNION ALL
        SELECT t.entity_id::text, t.start_year, t.end_year,
               'timeline ' || t.entry_kind || ' ' || coalesce(t.title, '')
        FROM entity_timeline_entries t JOIN ids ON ids.id = t.entity_id
    """, {"ids": ids})
    facts: dict[str, list[tuple]] = defaultdict(list)
    for eid, lo, hi, label in cur.fetchall():
        facts[eid].append((lo, hi, label))
    for r in rows:
        for field in ("summary", "description"):
            for y in text_years(r.get(field) or ""):
                facts[r["entity_id"]].append((y, y, field))
    return facts


def apply_plan(cur, plans: list[tuple[dict, dict]]) -> tuple[Counter, list[str]]:
    """Write each planned row unless the entity changed since it was planned
    (its QID was re-pointed, or it got a start year) — other agents write nearby."""
    done: Counter = Counter()
    applied: list[str] = []
    for e, p in plans:
        notes = f"{NOTE}:{p['start_prop']}" + (f",{p['end_prop']}" if p["end_prop"] not in (None, "row") else "")
        if p.get("precision_note"):
            notes += f" {p['precision_note']}"
        guard = ("EXISTS (SELECT 1 FROM entities WHERE entity_id = %(eid)s::uuid AND wikidata_id = %(qid)s) "
                 "AND NOT EXISTS (SELECT 1 FROM entity_temporal_ranges WHERE entity_id = %(eid)s::uuid "
                 "AND start_year IS NOT NULL)")
        args = {"eid": e["entity_id"], "qid": e["wikidata_id"], "sd": p["start_date"], "ed": p["end_date"],
                "sy": p["start"], "ey": p["end"], "conf": p["confidence"], "notes": notes,
                "method": METHOD, "rid": p["range_id"], "old_end": e.get("row_end_date")}
        if p["action"] == "update":
            cur.execute(f"""
                UPDATE entity_temporal_ranges
                SET start_date = %(sd)s, end_date = %(ed)s, start_year = %(sy)s, end_year = %(ey)s,
                    date_method = %(method)s, date_confidence = %(conf)s, notes = %(notes)s,
                    updated_at = now()
                WHERE temporal_range_id = %(rid)s::uuid AND start_year IS NULL
                  AND end_date IS NOT DISTINCT FROM %(old_end)s::text AND {guard}
            """, args)
        else:
            cur.execute(f"""
                INSERT INTO entity_temporal_ranges
                    (temporal_range_id, entity_id, range_type, start_date, end_date, start_year, end_year,
                     date_method, date_confidence, is_primary, notes, created_at, updated_at)
                SELECT %(rid)s::uuid, %(eid)s::uuid, 'primary', %(sd)s::text, %(ed)s::text,
                       %(sy)s::int, %(ey)s::int, %(method)s::text, %(conf)s::text, true, %(notes)s::text,
                       now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM entity_temporal_ranges
                                  WHERE entity_id = %(eid)s::uuid AND is_primary) AND {guard}
            """, args)
        done[p["action"] if cur.rowcount else "changed_since_plan"] += 1
        if cur.rowcount:
            applied.append(e["entity_id"])
    return done, applied


def load_exclusions(paths: list[Path]) -> set[str]:
    """Entity ids in any *_id column of the given CSVs (e.g. another agent's merge
    verdicts' survivor_id / loser_id)."""
    out: set[str] = set()
    for path in paths:
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                out.update(v.strip() for k, v in row.items()
                           if k and k.endswith("_id") and v and re.match(r"^[0-9a-f-]{36}$", v.strip()))
    return out


def write_rollback(path: Path, plans: list[tuple[dict, dict]]) -> None:
    """Undo statements, appended per run: inserted rows are deleted; updated rows
    get their old columns back. Each is a no-op unless the row still carries
    this script's note."""
    def lit(v: Any) -> str:
        if v is None:
            return "NULL"
        return "'" + str(v).replace("'", "''") + "'"

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(f"-- backfill_dates run {time_stamp()}: undo {len(plans)} planned rows\nBEGIN;\n")
        inserts = [p["range_id"] for _, p in plans if p["action"] == "insert"]
        for i in range(0, len(inserts), 500):
            ids = ", ".join(lit(x) for x in inserts[i:i + 500])
            f.write(f"DELETE FROM entity_temporal_ranges WHERE notes LIKE '{NOTE}:%' "
                    f"AND temporal_range_id IN ({ids});\n")
        for e, p in plans:
            if p["action"] != "update":
                continue
            f.write("UPDATE entity_temporal_ranges SET "
                    f"start_date = NULL, end_date = {lit(e['row_end_date'])}, "
                    f"date_method = {lit(e['date_method'])}, date_confidence = {lit(e['date_confidence'])}, "
                    f"notes = {lit(e['notes'])}, duration_type = {lit(e['duration_type'])}, "
                    f"updated_at = {lit(e['updated_at'])} "
                    f"WHERE temporal_range_id = {lit(p['range_id'])} AND notes LIKE '{NOTE}:%';\n")
        f.write("COMMIT;\n-- then rebuild their timelines (see the module docstring)\n\n")


def rebuild_timelines(entity_ids: list[str]) -> None:
    """entity_timeline_entries falls back to the range for an entity with no
    geometry or dated relationships: rebuild each entity this run dated, one
    `timeline:rebuild <id>` at a time (no global rebuild)."""
    for i, eid in enumerate(entity_ids, 1):
        subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", "timeline:rebuild", eid],
                       check=True, stdout=subprocess.DEVNULL)
        if i % 25 == 0 or i == len(entity_ids):
            print(f"   rebuilt {i}/{len(entity_ids)} timelines", flush=True)


# ── CSV and report ─────────────────────────────────────────────────────────────
CSV_COLS = ["entity_id", "name", "type", "qid", "wd_label", "wd_description", "action", "reason",
            "start_year", "end_year", "start_date", "end_date", "start_prop", "end_prop",
            "confidence", "precision", "earliest_fact", "latest_fact", "wd_first_record_P1249"]


def write_plan(path: Path, results: list[tuple[dict, dict]], meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for e, p in results:
            m = meta.get(e["wikidata_id"]) or {}
            w.writerow([e["entity_id"], e["name"], e["entity_type"], e["wikidata_id"], m.get("label", ""),
                        m.get("description", ""), p["action"], p["reason"], p.get("start"), p.get("end"),
                        p.get("start_date"), p.get("end_date"), p.get("start_prop"), p.get("end_prop"),
                        p.get("confidence"), p.get("precision_note", ""), p.get("earliest", ""), p.get("latest", ""),
                        p.get("first_record", "")])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write rows (default: dry run)")
    ap.add_argument("--no-timelines", action="store_true", help="skip the timeline rebuild after --apply")
    ap.add_argument("--limit", type=int, default=0, help="cap entities (smoke test)")
    ap.add_argument("--cache", type=Path, default=Path("output/audit/cache"), help="Wikidata cache dir")
    ap.add_argument("--out", type=Path, default=Path(f"output/audit/dates-backfill-{date.today():%Y%m%d}"),
                    help="directory for planned.csv and rollback.sql")
    ap.add_argument("--century", action="store_true",
                    help="also store century precision for non-person types, as the importer does "
                         "(persons untouched); writes planned-century.csv / rollback-century.sql")
    ap.add_argument("--exclude", type=Path, action="append", default=[],
                    help="CSV whose *_id columns list entities never to write (repeatable)")
    ap.add_argument("--exclude-prefix", action="append", default=[],
                    help="entity_id prefix never to write (repeatable)")
    args = ap.parse_args()
    suffix = "-century" if args.century else ""
    plan_csv, rollback_sql = args.out / f"planned{suffix}.csv", args.out / f"rollback{suffix}.sql"
    excluded = load_exclusions(args.exclude)

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    rows = load_state(cur)
    if args.limit:
        rows = rows[: args.limit]
    print(f"{len(rows)} entities with a QID and no start year\n")

    client = WikidataClient(args.cache, max_rps=1.0, workers=1)
    qids = sorted({r["wikidata_id"] for r in rows if QID_RE.match(r["wikidata_id"])})
    print(f"Fetching date claims for {len(qids)} QIDs…")
    claims = fetch_claims(client, qids)
    final = {q: resolve(claims, q)[0] for q in qids}
    print("Fetching labels and classes…")
    meta = client.get_entities(set(qids) | set(final.values()), progress=True)
    meta = {q: client.resolved(q)[1] or {} for q in qids}
    p31 = {q: m.get("p31", []) for q, m in meta.items()}
    roots = client.class_roots({c for cs in p31.values() for c in cs}, FORMER_ROOTS, progress=True)
    former = {q: any(roots.get(c) for c in cs) for q, cs in p31.items()}
    facts = load_facts(cur, rows)

    results: list[tuple[dict, dict]] = []
    for e in rows:
        qid = e["wikidata_id"]
        rec = resolve(claims, qid)[1] if QID_RE.match(qid) else None
        if e["entity_id"] in excluded or e["entity_id"].startswith(tuple(args.exclude_prefix) or ("\0",)):
            p = {"action": "skip", "reason": "excluded"}
        else:
            p = plan_entity(e, rec, former.get(qid, False), facts.get(e["entity_id"], []), args.century)
        if p["action"] != "skip":
            p["range_id"] = e["range_id"] or str(uuid.uuid4())
        elif rec and rec.get("status") == "ok":
            first, _ = pick(rec["dates"].get("P1249", []))
            if first:
                p["first_record"] = first["y"]
        results.append((e, p))
    planned = [(e, p) for e, p in results if p["action"] != "skip"]
    write_plan(plan_csv, results, meta)

    # ── Report ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("DATE BACKFILL" + ("  (APPLYING)" if args.apply else "  (DRY RUN)"))
    print("=" * 72)
    print(f"Rows to write: {len(planned)} / {len(rows)}   (plan: {plan_csv})")
    print("By precision: " + ", ".join(f"{k or 'decade or finer'} {n}" for k, n in
                                      Counter(p.get("precision_note") for _, p in planned).most_common()))
    for k, n in Counter(p["action"] for _, p in planned).most_common():
        print(f"   {k:28s} {n}")
    print("By confidence: " + ", ".join(f"{k} {n}" for k, n in
                                       Counter(p["confidence"] for _, p in planned).most_common()))
    print("By type (planned / in scope):")
    scope = Counter(e["entity_type"] for e, _ in results)
    done = Counter(e["entity_type"] for e, _ in planned)
    for t, n in scope.most_common():
        print(f"   {t:28s} {done[t]:5d} / {n}")
    print("Skipped (top types):")
    by_reason: dict[str, Counter] = defaultdict(Counter)
    for e, p in results:
        if p["action"] == "skip":
            by_reason[p["reason"].split(":")[0]][e["entity_type"]] += 1
    for reason, types in sorted(by_reason.items(), key=lambda kv: -sum(kv[1].values())):
        top = ", ".join(f"{t} {n}" for t, n in types.most_common(4))
        print(f"   {reason:26s} {sum(types.values()):5d}   {top}")
    first = Counter(e["entity_type"] for e, p in results if "first_record" in p)
    print(f"Skipped but with a P1249 earliest written record (not used): {sum(first.values())}   "
          + ", ".join(f"{t} {n}" for t, n in first.most_common(5)))

    if args.apply:
        write_rollback(rollback_sql, planned)
        print(f"\nApplying in a single transaction… (undo: {rollback_sql})")
        try:
            counts, applied = apply_plan(cur, planned)
            conn.commit()
            print("  committed: " + ", ".join(f"{k} {n}" for k, n in counts.items()))
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
        if not args.no_timelines:
            print("Rebuilding the timelines of dated entities…")
            rebuild_timelines(applied)
    else:
        print("\nDry run: re-run with --apply to write.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
