"""QID consequences (2026-11-01 cleanup): remove the data a wrong QID left behind.

When a row carried the wrong ``wikidata_id``, the importer and the backfills
copied that item's data onto it: dates into the primary
``entity_temporal_ranges`` row, a map point (P625, or a birth/work place's
coordinate), the item's English labels and aliases, and Commons images
(``attributes.media_refs``). The cleanup agents repointed or cleared those QIDs;
this pass removes what the old item left behind.

Input: the applied.csv files of finished agents (``--applied``, repeatable).
Every QID change found in them becomes a case (entity, old QIDs, new QID); the
formats read are

  * ``entity_id, old_qid, new_qid[, decision]``  (namesake review)
  * ``entity_id|id, column, old, new[, table, op|fix|decision]`` with
    ``column = wikidata_id``                      (s1-types, merge-review, names-followup)
  * ``entity_id, rejected_qid``                  (s1-types followups-derived-data.csv)

plus every row flagged ``identity_audit:stale_from_old_qid`` (its old QID must
be in one of the inputs). A row whose QID changed again since (not the QID the
last input row set) is skipped.

Per case, compared with the OLD item's values (``output/audit/cache``):

  dates   the primary range's start/end equal an old start/end-like value
          (P571 P569 P585 P580 P577 P575 / P576 P570 P582 P585) at that value's
          precision (a decade matches its ten years; a century or millennium
          only the year Wikidata wrote, as the importer stores it). With a new
          QID the derived side(s) are set from the new item by
          ``backfill_dates.plan_entity`` (its rules and evidence guards; the
          range's own geometry/timeline facts left out, they are copies),
          date_method source_database. With no QID, or a new item whose dates
          are unusable, the derived side is cleared, unless the year is also
          named in the row's own summary/description or the range's
          date_method is not source-derived (another source); never invented.
  point   stale: a wikidata geo ref on an old QID; a wikidata
          place-of-association ref the importer made before the change; a
          ``geo-backfill:*`` period written before the change (it used the old
          QID's P625 or the OHM feature tagged with it); a period or the primary
          location point within 1 km of an old item's P625 (and not of the new
          item's), or on a stale ref's place. Stale periods are deleted (their
          refs detached first), the primary ``entity_locations.geom`` (and
          location_method) nulled, stale refs deactivated (source_meta records
          why) and ``entities.primary_geo_ref_id`` cleared when it pointed at
          one. No point is placed here: ``backfill_geo`` re-places from the
          entity's own QID or OHM.
  aliases an alias equal (case/accents aside) to an old item's label or alias,
          unless it is the row's name, a name of the new item, or listed in
          ``KEEP_ALIASES`` (a genuine name of this entity, hand-checked).
  images  ``media_refs`` items fetched before the change (sources wikidata /
          wikipedia) are dropped; the key goes when none is left. Admin-curated
          rows (``_media_curated_at``) are never touched. After --apply each
          repointed row gets ``entity:fetch-images --refresh --entity-id=<id>``.

  period years  a kept map point whose period start/end is an old item's date (copied from the
          range when it was placed) takes the range's years, else the attested start
          (first dated relationship, backfill_geo's fallback, with its note); a stale end
          becomes the range's end (open when it has none).
  dates-suspect  rows flagged ``identity_audit:row_dates_suspect`` (QID right, dates not) are
          re-dated from the item by ``plan_entity`` (the row's end ignored), or by hand
          (``MANUAL_SUSPECT_DATES``) where the item fails its rules; the flag is dropped.

Overrides from the spot check: ``KEEP_ALIASES``, ``KEEP_DATES`` (another source, or left for
a human); a place-of-association point is kept when the place is named in the row's own name
('Council of Arles' at Arles) and the new item has no site of its own.

Then ``timeline:rebuild <id>`` per entity whose dates or periods changed, and
``entity:fetch-images --refresh`` (50 ids per call) for repointed rows whose images are not
checked under the new QID yet. Timestamps are compared in UTC (the DB's clock; the agents'
applied.csv ``ts`` are local time). ``--rejected-attr`` (plan only) adds every QID-less row
with ``attributes._rejected_wikidata_id``: listing aid, never applied, since the importer also
rejects a right QID that another row holds.

Stages (dry by default):

  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.qid_consequences plan
  scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.audit.qid_consequences apply

``plan`` writes planned.csv; ``apply`` re-plans from the live DB, applies only
the changes planned.csv lists unchanged (one savepoint per entity, every write
guarded on the value read), writes applied.csv, rollback.sql (tested inside a
rolled-back transaction) and backups of the touched tables, then runs the
per-entity image fetches and timeline rebuilds. Pass 2: point ``--applied`` at
the other agents' applied.csv files and ``--out`` at a new directory.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.audit.common import CACHE_DIR, COMPOSE, REPO, connect, write_csv
from pipeline.audit.dates import text_years
from pipeline.audit.wd import QID_RE, WikidataClient

AUDIT = REPO / "output" / "audit"
DEFAULT_OUT = AUDIT / "qid-consequences-20261101"
DEFAULT_APPLIED = [
    AUDIT / "s1-types-20261101" / "applied.csv",
    AUDIT / "s1-types-20261101" / "followups-derived-data.csv",
    AUDIT / "qid-namesake-20261101" / "applied.csv",
    AUDIT / "merge-review-20261101" / "applied.csv",
    AUDIT / "names-followup-20261101" / "applied.csv",
    AUDIT / "qid-suspect-20261101" / "applied.csv",
    f"{AUDIT / 'identity-20261031' / 'applied.csv'}::clear_qid",
]
DATES_SUSPECT_FLAG = "identity_audit:row_dates_suspect"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
STALE_FLAG = "identity_audit:stale_from_old_qid"
CURATED_KEY = "_media_curated_at"
NOTE = "qid_consequences"
TAG = "qid_consequences_20261101"

START_PROPS = ("P571", "P569", "P585", "P580", "P577", "P575")
END_PROPS = ("P576", "P570", "P582", "P585")
# date_method values that name a source other than the Wikidata item
OTHER_SOURCE_METHODS = {"nlp_direct", "nlp_approximate", "llm_reign_resolution", "era_table_lookup",
                        "llm_contextual_inference", "human_assigned"}
NEAR_KM = 1.0
# backfill_geo.WIKIDATA_POINT_TYPES: types it places at their own P625
WIKIDATA_POINT_TYPES = frozenset({
    "city", "infrastructure_monument", "educational_institution", "extraction_infra",
    "event_battle", "event_treaty", "event_natural_disaster", "cultural_work",
})

# Aliases equal to an old item's name that are genuine names of the row too
# (hand-checked in the spot check): (entity_id prefix, alias).
KEEP_ALIASES: set[tuple[str, str]] = {
    ("9221daa5", "I-Kiribati"),       # Gilbertese people (old: the language)
    ("9dfda8b5", "Temple of Hera"),   # a Heraion is a temple of Hera
    ("92c293fb", "Galla"),            # old exonym of the Oromo people (old: the language)
    ("6211397d", "Bengal partition"), # names the 1905 partition as well as the 1947 one
    ("ad3f8951", "Supreme Court"),    # short name of the US Supreme Court
    ("265887cc", "Huari"),            # spelling of Wari
}
# Dates equal to the old item's that another source backs, or that are left for a human
# (hand-checked in the spot check): entity_id prefix -> why.
KEEP_DATES: dict[str, str] = {
    "89aeb417": "kept: enwiki 'Japanese National Railways' lead: operated the network 'from 1949 to 1987'",
    "480afeba": "left for review: 1833 (Q612, Dubai city) is when the Al Maktoum founded Dubai; "
                "no source for the emirate found",
}
# Rows flagged identity_audit:row_dates_suspect whose item fails backfill_dates' rules, dated by hand
# from the item (and enwiki lead): prefix -> (start_date or KEEP, end_date or KEEP, confidence, why).
KEEP = object()
MANUAL_SUSPECT_DATES: dict[str, tuple[Any, Any, str, str]] = {
    "ac4cf545": ("1679-11-19", "1731-03-26", "medium",
                 "preferred-rank P569/P570 of Q982003 (its normal-rank 1693/1740 are the row's old values)"),
    "a75c3d97": (KEEP, "1268", "medium", "P570 of Q7205532 (Kim Jun killed 1268; no birth date)"),
    "54032c73": (KEEP, "831", "medium", "P570 of Q276527 (khan 814-831; birth unknown, start 800 kept, listed)"),
    "ce17d37f": (KEEP, "1418", "medium", "P570 of Q7285440 (birth unknown on Wikidata)"),
    "4429ee39": (KEEP, KEEP, "", "end already the item's P570 (-1076); birth only century-precise"),
    "f83d9380": (KEEP, "983", "medium", "P570 of Q2829249 (died in prison 982/983)"),
}
PERSON_TYPES = {"person"}


# ── inputs ───────────────────────────────────────────────────────────────────
@dataclass
class Case:
    entity_id: str
    old_qids: list[str] = field(default_factory=list)
    new_qid: str | None = None       # the QID the last input row set ('' -> None)
    new_known: bool = False          # False: only a followups/rejected row, no target known
    changed_at: str = ""             # earliest change timestamp (ISO, local time)
    sources: list[str] = field(default_factory=list)


def _norm_qid(v: str | None) -> str | None:
    v = (v or "").strip()
    return v if QID_RE.match(v) else None


def split_spec(spec: str | Path) -> tuple[Path, set[str]]:
    """'dir/applied.csv::clear_qid,repoint' -> (path, {ops}); no '::' keeps every op."""
    text = str(spec)
    if "::" in text:
        path, ops = text.split("::", 1)
        return Path(path), {o for o in ops.split(",") if o}
    return Path(text), set()


def load_cases(specs: list[str | Path]) -> dict[str, Case]:
    events: list[tuple[str, str, str | None, str | None, bool, str]] = []  # ts, eid, old, new, known, src
    for spec in specs:
        path, ops = split_spec(spec)
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
        tag = path.parent.name.replace("-20261101", "")
        with path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            continue
        cols = set(rows[0])
        for r in rows:
            if r.get("status") and r["status"] != "applied":
                continue
            op = r.get("op") or r.get("fix") or r.get("decision") or ""
            if ops and op not in ops:
                continue
            ts = r.get("ts") or mtime
            eid = r.get("entity_id") or r.get("id") or ""
            if "old_qid" in cols and "new_qid" in cols:
                old, new = _norm_qid(r["old_qid"]), _norm_qid(r["new_qid"])
                if old and old != new:
                    events.append((ts, eid, old, new, True, f"{tag}:{r.get('decision', '')}"))
            elif "column" in cols and "old" in cols:
                if r["column"] != "wikidata_id" or r.get("table", "entities") != "entities":
                    continue
                old, new = _norm_qid(r["old"]), _norm_qid(r["new"])
                if old and old != new:
                    events.append((ts, eid, old, new, True, f"{tag}:{op}"))
            elif "rejected_qid" in cols:
                old = _norm_qid(r["rejected_qid"])
                if old:
                    events.append((ts, eid, old, None, False, f"{tag}:rejected"))
    cases: dict[str, Case] = {}
    for ts, eid, old, new, known, src in sorted(events, key=lambda e: e[0]):
        c = cases.setdefault(eid, Case(eid, changed_at=ts))
        if old not in c.old_qids:
            c.old_qids.append(old)
        if known:
            c.new_qid, c.new_known = new, True
        c.changed_at = min(c.changed_at, ts)
        if src not in c.sources:
            c.sources.append(src)
    for c in cases.values():  # a QID set back later is not an old one
        c.old_qids = [q for q in c.old_qids if q != c.new_qid]
    return {k: v for k, v in cases.items() if v.old_qids}


# ── DB state ─────────────────────────────────────────────────────────────────
def load_state(cur, ids: list[str]) -> dict[str, dict[str, Any]]:
    st: dict[str, dict[str, Any]] = {}
    cur.execute("""
        SELECT entity_id::text, name, entity_type::text, wikidata_id, verification_status::text,
               attributes, coalesce(summary, ''), coalesce(description, ''), primary_geo_ref_id::text
        FROM entities WHERE entity_id = ANY(%s::uuid[])""", (ids,))
    for eid, name, typ, qid, status, attrs, summary, desc, pgr in cur.fetchall():
        st[eid] = {"entity_id": eid, "name": name, "type": typ, "qid": qid, "status": status,
                   "attributes": attrs or {}, "summary": summary, "description": desc,
                   "primary_geo_ref_id": pgr, "range": None, "location": None,
                   "periods": [], "refs": [], "aliases": []}
    cur.execute("""
        SELECT entity_id::text, temporal_range_id::text, start_year, end_year, start_date, end_date,
               date_method, date_confidence, duration_type, notes
        FROM entity_temporal_ranges WHERE is_primary AND entity_id = ANY(%s::uuid[])""", (ids,))
    for row in cur.fetchall():
        st[row[0]]["range"] = dict(zip(("range_id", "start_year", "end_year", "start_date", "end_date",
                                        "date_method", "date_confidence", "duration_type", "notes"), row[1:]))
    cur.execute("""
        SELECT entity_id::text, location_id::text, location_name, location_method,
               CASE WHEN GeometryType(geom) = 'POINT' THEN ST_X(geom) END,
               CASE WHEN GeometryType(geom) = 'POINT' THEN ST_Y(geom) END,
               geom IS NOT NULL, territory_geom IS NOT NULL, created_at::text, updated_at::text
        FROM entity_locations WHERE is_primary AND entity_id = ANY(%s::uuid[])""", (ids,))
    for row in cur.fetchall():
        st[row[0]]["location"] = dict(zip(("location_id", "location_name", "location_method", "x", "y",
                                           "has_geom", "has_territory", "created_at", "updated_at"), row[1:]))
    cur.execute("""
        SELECT entity_id::text, geometry_period_id::text, period_type, provenance_mode, created_by,
               start_year, end_year,
               CASE WHEN GeometryType(geom) = 'POINT' THEN ST_X(geom) END,
               CASE WHEN GeometryType(geom) = 'POINT' THEN ST_Y(geom) END,
               territory_geom IS NOT NULL, description, created_at::text
        FROM geometry_periods WHERE entity_id = ANY(%s::uuid[])""", (ids,))
    for row in cur.fetchall():
        st[row[0]]["periods"].append(dict(zip(
            ("period_id", "period_type", "provenance_mode", "created_by", "start_year", "end_year", "x", "y",
             "has_territory", "description", "created_at"), row[1:])))
    cur.execute("""
        SELECT entity_id::text, geo_ref_id::text, provider::text, external_type::text, external_id,
               match_role::text, is_active, geometry_period_id::text, source_meta, created_at::text,
               external_tags
        FROM entity_geo_refs WHERE entity_id = ANY(%s::uuid[])""", (ids,))
    for row in cur.fetchall():
        st[row[0]]["refs"].append(dict(zip(
            ("geo_ref_id", "provider", "external_type", "external_id", "match_role", "is_active",
             "geometry_period_id", "source_meta", "created_at", "external_tags"), row[1:])))
    cur.execute("""
        SELECT entity_id::text, alias_id::text, name, language, source, is_primary
        FROM entity_aliases WHERE entity_id = ANY(%s::uuid[])""", (ids,))
    for row in cur.fetchall():
        st[row[0]]["aliases"].append(dict(zip(("alias_id", "name", "language", "source", "is_primary"), row[1:])))
    return st


# ── helpers ──────────────────────────────────────────────────────────────────
def km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(a)))


def near(x: float | None, y: float | None, coords: list[tuple[float, float, str]],
         tol: float = NEAR_KM) -> str | None:
    """The label of the first (lon, lat, label) within ``tol`` km of (x, y)."""
    if x is None or y is None:
        return None
    for lon, lat, label in coords:
        if km(x, y, lon, lat) <= tol:
            return label
    return None


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.casefold())).strip()


def date_match(year: int | None, v: dict, entity_type: str) -> str | None:
    """How ``year`` equals a Wikidata value at that value's precision."""
    from pipeline.backfill_dates import century_year, interval
    if year is None or "y" not in v:
        return None
    p = v["p"]
    if p >= 9:
        return "year" if year == v["y"] else None
    if p == 8:
        lo, hi = interval(v["y"], 8)
        return "decade" if lo <= year <= hi else None
    if year == v["y"]:
        return "coarse"
    try:
        if year == century_year(v, entity_type):
            return "coarse"
    except Exception:  # noqa: BLE001 - an unparseable time string is just no match
        return None
    return None


def derived_side(year: int | None, claims: dict[str, dict], qids: list[str], props: tuple[str, ...],
                 entity_type: str) -> str | None:
    """'Qxx:P571=1859(year)' when ``year`` is one of the old items' values."""
    for q in qids:
        rec = claims.get(q) or {}
        for prop in props:
            for v in (rec.get("dates") or {}).get(prop, []):
                how = date_match(year, v, entity_type)
                if how:
                    return f"{q}:{prop}={v['y']}({how})"
    return None


def utc(ts: str) -> str:
    """'YYYY-MM-DD HH:MM:SS' in UTC, the DB's clock (timestamps without zone, session UTC).
    A naive ts (the agents' applied.csv, written in local time) is read as local time;
    media_refs' fetched_at carries its own offset."""
    from datetime import timezone
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def fmt_range(r: dict | None) -> str:
    if not r:
        return ""
    return f"{r.get('start_date') or ''}..{r.get('end_date') or ''}"


# ── plan ─────────────────────────────────────────────────────────────────────
@dataclass
class Ctx:
    wd: WikidataClient
    claims: dict[str, dict]
    former: dict[str, bool]
    facts: dict[str, list[tuple]]
    attested: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)


def wd_rec(ctx: Ctx, qid: str | None) -> dict[str, Any]:
    if not qid:
        return {}
    _, rec = ctx.wd.resolved(qid)
    return rec if rec and rec.get("status") == "ok" else {}


def claims_rec(ctx: Ctx, qid: str) -> dict:
    from pipeline.backfill_dates import resolve
    rec = resolve(ctx.claims, qid)[1]
    return rec if rec and rec.get("status") == "ok" else {}


def change(e: dict, case: Case, kind: str, action: str, table: str, row_id: str, column: str,
           old: Any, new: Any, reason: str, guard: dict | None = None, after: dict | None = None,
           restore: dict | None = None) -> dict[str, Any]:
    return {"entity_id": e["entity_id"], "name": e["name"], "entity_type": e["type"],
            "old_qids": " ".join(case.old_qids), "new_qid": e["qid"] or "", "kind": kind, "action": action,
            "table": table, "row_id": row_id, "column": column,
            "old": old if isinstance(old, str) else json.dumps(old, ensure_ascii=False, default=str),
            "new": new if isinstance(new, str) else json.dumps(new, ensure_ascii=False, default=str),
            "reason": reason, "guard": guard or {}, "after": after or {}, "restore": restore or {}}


def plan_dates(e: dict, case: Case, ctx: Ctx) -> tuple[list[dict], list[dict]]:
    from pipeline.backfill_dates import plan_entity
    r = e["range"]
    if not r or (r["start_year"] is None and r["end_year"] is None):
        return [], []
    old_claims = {q: claims_rec(ctx, q) for q in case.old_qids}
    sd = derived_side(r["start_year"], old_claims, case.old_qids, START_PROPS, e["type"])
    ed = derived_side(r["end_year"], old_claims, case.old_qids, END_PROPS, e["type"])
    if not sd and not ed:
        return [], []
    if e["entity_id"][:8] in KEEP_DATES:
        return [], [{"entity_id": e["entity_id"], "name": e["name"], "issue": "dates_left",
                     "detail": f"{fmt_range(r)}: start {sd or '-'} end {ed or '-'}; {KEEP_DATES[e['entity_id'][:8]]}"}]
    notes_list: list[dict] = []
    own_years = set(text_years(e["summary"])) | set(text_years(e["description"]))
    other_method = r["date_method"] in OTHER_SOURCE_METHODS
    new_start, new_end = r["start_year"], r["end_year"]
    new_sdate, new_edate = r["start_date"], r["end_date"]
    method, conf = r["date_method"], r["date_confidence"]
    why: list[str] = []
    new_qid = e["qid"]
    plan: dict | None = None
    if new_qid:
        e_new = {"entity_type": e["type"], "wikidata_id": new_qid, "verification_status": "pipeline_draft",
                 "flags": [], "range_id": r["range_id"],
                 "row_end_year": None if ed else r["end_year"], "row_end_date": None if ed else r["end_date"]}
        if sd is None and r["start_year"] is not None and ed:
            # the start is the row's own: keep it, take only the end from the new item
            pass
        p = plan_entity(e_new, claims_rec(ctx, new_qid), ctx.former.get(new_qid, False),
                        ctx.facts.get(e["entity_id"], []))
        if p["action"] != "skip":
            plan = p
        else:
            why.append(f"new item {new_qid} dates unusable ({p['reason']})")
    if plan and claims_rec(ctx, new_qid).get("fallback"):
        plan["confidence"] = "medium" if plan["confidence"] == "high" else plan["confidence"]
        why.append("best values only (claims not fetched: Wikidata maxlag)")
    if plan:
        if sd or r["start_year"] is None:
            new_start, new_sdate = plan["start"], plan["start_date"]
        if ed or (sd and r["end_year"] is None):
            new_end, new_edate = plan["end"], plan["end_date"]
        method, conf = "source_database", plan["confidence"]
        props = ",".join(x for x in (plan["start_prop"], plan["end_prop"]) if x and x != "row")
        why.append(f"set from new item {new_qid} {props}")
    else:
        # no usable new item: clear the derived side unless another source names it
        for side, hit in (("start", sd), ("end", ed)):
            if not hit:
                continue
            year = r[f"{side}_year"]
            if other_method:
                notes_list.append({"side": side, "kept": f"date_method {r['date_method']}"})
                why.append(f"kept {side} {year}: date_method {r['date_method']}")
                continue
            if year in own_years:
                why.append(f"kept {side} {year}: named in own text")
                continue
            if side == "start":
                new_start, new_sdate = None, None
            else:
                new_end, new_edate = None, None
            why.append(f"cleared {side} {year} ({hit})")
        if new_start is None and new_end is None:
            method, conf = None, None
    if new_start is not None and new_end is not None and new_start > new_end:
        return [], [{"entity_id": e["entity_id"], "name": e["name"], "issue": "start_after_end",
                     "detail": f"{new_start}>{new_end}; {'; '.join(why)}"}]
    if (new_sdate, new_edate) == (r["start_date"], r["end_date"]):
        listed = []
        if any(w.startswith("kept") or w.startswith("new item") for w in why):
            listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "dates_left",
                           "detail": f"{fmt_range(r)}: start {sd or '-'} end {ed or '-'}; {'; '.join(why)}"})
        return [], listed
    old_q = "/".join(case.old_qids)
    note = f"{NOTE}: {'; '.join(why)} (was {fmt_range(r)} from {old_q})"
    guard = {k: r[k] for k in ("start_date", "end_date", "start_year", "end_year", "date_method",
                               "date_confidence", "notes")}
    after = {"start_date": new_sdate, "end_date": new_edate, "start_year": new_start, "end_year": new_end,
             "date_method": method, "date_confidence": conf, "notes": note}
    return [change(e, case, "dates", "set_range", "entity_temporal_ranges", r["range_id"], "start_date,end_date",
                   fmt_range(r), f"{new_sdate or ''}..{new_edate or ''}", "; ".join(why), guard, after)], []


def plan_point(e: dict, case: Case, ctx: Ctx, place_coords: dict[str, tuple[float, float]]
               ) -> tuple[list[dict], list[dict]]:
    out: list[dict] = []
    listed: list[dict] = []
    new = wd_rec(ctx, e["qid"])
    new_coord = new.get("coord")
    new_pts = [(new_coord[1], new_coord[0], f"{e['qid']} P625")] if new_coord else []
    old_pts = []
    for q in case.old_qids:
        c = wd_rec(ctx, q).get("coord")
        if c:
            old_pts.append((c[1], c[0], f"{q} P625"))
    changed = utc(case.changed_at)  # DB created_at/updated_at are UTC

    stale_refs: dict[str, str] = {}
    kept_place_pts: list[tuple[float, float, str]] = []
    for ref in e["refs"]:
        if ref["provider"] != "wikidata" or not ref["is_active"]:
            continue
        src = (ref["source_meta"] or {}).get("source", "")
        if ref["external_id"] in case.old_qids:
            stale_refs[ref["geo_ref_id"]] = f"wikidata ref on old QID {ref['external_id']} ({src})"
        elif src == "wikidata_place_of_association" and ref["created_at"] and ref["created_at"] < changed:
            place = norm_name(wd_rec(ctx, ref["external_id"]).get("label", ""))
            # 'Council of Arles' at Arles is right even when it came from the 554 council's item; it
            # stays unless the new item has its own site, which backfill_geo then places
            own_site = bool(new_pts) and e["type"] in WIKIDATA_POINT_TYPES
            if (e["type"] not in PERSON_TYPES and not own_site and place
                    and re.search(rf"\b{re.escape(place)}\b", norm_name(e["name"]))):
                listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "place_kept_named",
                               "detail": f"place of association {ref['external_id']} '{place}' of old QID is "
                                         f"named in the row's own name; point and ref kept"})
                pc = place_coords.get(ref["external_id"])
                if pc:
                    kept_place_pts.append((pc[0], pc[1], ref["external_id"]))
                continue
            stale_refs[ref["geo_ref_id"]] = (f"place of association {ref['external_id']} of old QID "
                                              f"{'/'.join(case.old_qids)} (made {ref['created_at'][:10]})")
    stale_place_pts = []
    for ref in e["refs"]:
        if ref["geo_ref_id"] in stale_refs:
            pc = place_coords.get(ref["external_id"])
            if pc:
                stale_place_pts.append((pc[0], pc[1], f"{ref['external_id']} P625 (place)"))
    stale_periods: dict[str, str] = {}
    for p in e["periods"]:
        if near(p["x"], p["y"], new_pts):
            continue
        by = p["created_by"] or ""
        hit = near(p["x"], p["y"], old_pts)
        linked = [r for r in e["refs"] if r["geometry_period_id"] == p["period_id"]]
        if hit:
            stale_periods[p["period_id"]] = f"point = {hit}"
        elif by.startswith("geo-backfill:") and p["created_at"] and p["created_at"] < changed:
            stale_periods[p["period_id"]] = f"{by} written {p['created_at'][:16]} UTC with the old QID"
        elif any(r["geo_ref_id"] in stale_refs for r in linked):
            stale_periods[p["period_id"]] = "tied to a stale ref"
        elif (hit := near(p["x"], p["y"], stale_place_pts, 0.05)):
            stale_periods[p["period_id"]] = f"point = {hit}"
    # an OHM ref whose period goes was matched through the old QID's tag: deactivate it too
    for ref in e["refs"]:
        if ref["is_active"] and ref["geometry_period_id"] in stale_periods and ref["geo_ref_id"] not in stale_refs:
            stale_refs[ref["geo_ref_id"]] = f"{ref['provider']} {ref['external_type']}/{ref['external_id']} " \
                                            f"placed through the old QID ({stale_periods[ref['geometry_period_id']]})"
    stale_period_pts = [(p["x"], p["y"], f"stale period {p['period_id'][:8]}") for p in e["periods"]
                        if p["period_id"] in stale_periods and p["x"] is not None]
    loc = e["location"]
    loc_reason = None
    if loc and loc["has_geom"] and loc["x"] is not None and not near(loc["x"], loc["y"], new_pts):
        hit = (near(loc["x"], loc["y"], old_pts) or near(loc["x"], loc["y"], stale_place_pts, 0.05)
               or near(loc["x"], loc["y"], stale_period_pts, 0.05))
        if hit:
            loc_reason = f"point = {hit}"
        elif (loc["location_method"] == "wikidata" and (loc["updated_at"] or "") < changed
              and not near(loc["x"], loc["y"], kept_place_pts, 0.05)):
            listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "wikidata_point_unexplained",
                           "detail": f"POINT({loc['x']:.4f} {loc['y']:.4f}) set {loc['updated_at']}, "
                                     f"old {'/'.join(case.old_qids)} coord {old_pts or 'none'}"})
    # an OHM ref sitting on the old item's place (or on a stale point) was matched through the old item
    stale_pts = stale_period_pts + ([(loc["x"], loc["y"], "stale location point")] if loc_reason else [])
    for ref in e["refs"]:
        if ref["provider"] != "ohm" or not ref["is_active"] or ref["geo_ref_id"] in stale_refs:
            continue
        meta = ref["source_meta"] or {}
        try:
            rx, ry = float(meta["lon"]), float(meta["lat"])
        except (KeyError, TypeError, ValueError):
            continue
        if near(rx, ry, new_pts, 50):
            continue
        hit = near(rx, ry, stale_pts, 0.05) or near(rx, ry, old_pts, 5)
        if hit:
            stale_refs[ref["geo_ref_id"]] = (f"ohm {ref['external_type']}/{ref['external_id']} "
                                              f"'{(meta.get('display_name') or '')[:50]}' at {hit}")
    e["_stale_ohm_names"] = set()
    for ref in e["refs"]:
        if ref["provider"] == "ohm" and ref["geo_ref_id"] in stale_refs:
            meta, tags = ref["source_meta"] or {}, ref.get("external_tags") or {}
            for n in ((meta.get("display_name") or "").split(",")[0], tags.get("name"), tags.get("name:en")):
                if n and n.strip():
                    e["_stale_ohm_names"].add(n.strip())
    surviving = [r for r in e["refs"] if r["is_active"] and r["geo_ref_id"] not in stale_refs
                 and r["geometry_period_id"] and r["geometry_period_id"] not in stale_periods]
    surviving.sort(key=lambda r: (r["provider"] != "ohm", r["match_role"] != "primary", r["created_at"] or ""))
    for ref in e["refs"]:
        if ref["geo_ref_id"] in stale_refs:
            meta = dict(ref["source_meta"] or {})
            new_meta = {**meta, "deactivated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "deactivated_by": TAG,
                        "deactivated_reason": f"from wrong QID {'/'.join(case.old_qids)}"}
            out.append(change(e, case, "point", "deactivate_geo_ref", "entity_geo_refs", ref["geo_ref_id"],
                              "is_active", f"{ref['provider']}:{ref['external_type']}/{ref['external_id']} "
                              f"{ref['match_role']} active", "inactive", stale_refs[ref["geo_ref_id"]],
                              {"is_active": True, "geometry_period_id": ref["geometry_period_id"],
                               "source_meta": meta},
                              {"is_active": False, "geometry_period_id": None, "source_meta": new_meta}))
            if e["primary_geo_ref_id"] == ref["geo_ref_id"]:
                repl = surviving[0]["geo_ref_id"] if surviving else None
                out.append(change(e, case, "point", "null_primary_geo_ref", "entities", e["entity_id"],
                                  "primary_geo_ref_id", ref["geo_ref_id"], repl or "",
                                  "primary ref is stale" + (f"; the ref of the surviving map point instead"
                                                            if repl else ""),
                                  {"primary_geo_ref_id": ref["geo_ref_id"]}, {"primary_geo_ref_id": repl}))
    for p in e["periods"]:
        if p["period_id"] in stale_periods:
            pt = f"POINT({p['x']:.4f} {p['y']:.4f})" if p["x"] is not None else "territory"
            out.append(change(e, case, "point", "delete_period", "geometry_periods", p["period_id"], "*",
                              f"{p['period_type']} {pt} {p['start_year']}..{p['end_year'] or ''} "
                              f"{p['created_by'] or p['provenance_mode']}", "", stale_periods[p["period_id"]],
                              {"created_by": p["created_by"], "start_year": p["start_year"],
                               "end_year": p["end_year"]}))
    if loc_reason:
        out.append(change(e, case, "point", "null_location", "entity_locations", loc["location_id"], "geom",
                          f"POINT({loc['x']:.4f} {loc['y']:.4f}) {loc['location_method'] or ''}", "", loc_reason,
                          {"location_method": loc["location_method"], "x": loc["x"], "y": loc["y"]},
                          {"geom": None, "location_method": None}))
        if not loc["location_name"] and not loc["has_territory"]:
            out.pop()
            listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "location_has_no_name",
                           "detail": "stale point, but nulling geom would leave the row without a locator"})
    return out, listed


ATTESTED_NOTE = ("Years attested in the atlas (from its first dated relationship; to its last, "
                 "unless the place still exists), not a founding or end date.")  # backfill_geo.ATTESTED_NOTE


def plan_period_years(e: dict, case: Case, ctx: Ctx, deleted: set[str], new_range: dict | None
                      ) -> tuple[list[dict], list[dict]]:
    """A kept map point whose period years are the old item's dates (copied from the range
    when the point was placed): the range's years now, else the attested start (backfill_geo's
    fallback); an end that was the old item's becomes the range's (open if it has none)."""
    out, listed = [], []
    r = new_range or e["range"] or {}
    rs, re_ = r.get("start_year"), r.get("end_year")
    old_claims = {q: claims_rec(ctx, q) for q in case.old_qids}
    for p in e["periods"]:
        if p["period_id"] in deleted or p["period_type"] == "presence":
            continue
        ss = p["start_year"] != rs and derived_side(p["start_year"], old_claims, case.old_qids, START_PROPS, e["type"])
        es = (p["end_year"] is not None and p["end_year"] != re_
              and derived_side(p["end_year"], old_claims, case.old_qids, END_PROPS, e["type"]))
        if not ss and not es:
            continue
        start, end, desc, conf, how = p["start_year"], p["end_year"], None, None, []
        if ss:
            if rs is not None:
                start, how = rs, how + [f"start {p['start_year']} -> range start {rs}"]
            elif (ctx.attested.get(e["entity_id"]) or (None,))[0] is not None:
                start = ctx.attested[e["entity_id"]][0]
                desc, conf = ATTESTED_NOTE, "medium"
                how.append(f"start {p['start_year']} -> attested {start}")
            else:
                listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "period_years_stale",
                               "detail": f"period {p['period_id'][:8]} starts {p['start_year']} ({ss}); no other year"})
                continue
        if es:
            end = re_
            how.append(f"end {p['end_year']} -> {re_ if re_ is not None else 'open'}")
        if end is not None and start > end:
            listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "period_years_stale",
                           "detail": f"period {p['period_id'][:8]}: {start}>{end}"})
            continue
        out.append(change(e, case, "dates", "set_period_years", "geometry_periods", p["period_id"],
                          "start_year,end_year", f"{p['start_year']}..{p['end_year'] if p['end_year'] is not None else ''}",
                          f"{start}..{end if end is not None else ''}",
                          f"period years were the old item's ({ss or es}); " + "; ".join(how),
                          {"start_year": p["start_year"], "end_year": p["end_year"], "created_by": p["created_by"],
                           "description": p["description"]},
                          {"start_year": start, "end_year": end,
                           "description": desc if desc else p["description"], "confidence": conf}))
    return out, listed


def plan_aliases(e: dict, case: Case, ctx: Ctx) -> tuple[list[dict], list[dict]]:
    out, listed = [], []
    old_names: dict[str, str] = {}
    for q in case.old_qids:
        rec = wd_rec(ctx, q)
        for n in [rec.get("label", ""), *(rec.get("aliases") or [])]:
            if n:
                old_names.setdefault(norm_name(n), q)
    for n in e.get("_stale_ohm_names") or ():
        old_names.setdefault(norm_name(n), "OHM")
    new = wd_rec(ctx, e["qid"])
    keep = {norm_name(n) for n in [e["name"], new.get("label", ""), *(new.get("aliases") or [])] if n}
    for a in e["aliases"]:
        k = norm_name(a["name"])
        if k not in old_names or a["is_primary"]:
            continue
        if k in keep:
            continue
        if (e["entity_id"][:8], a["name"]) in KEEP_ALIASES:
            listed.append({"entity_id": e["entity_id"], "name": e["name"], "issue": "alias_kept",
                           "detail": f"'{a['name']}' (also {old_names[k]}) is a genuine name"})
            continue
        out.append(change(e, case, "alias", "delete_alias", "entity_aliases", a["alias_id"], "name", a["name"], "",
                          (f"name of old item {old_names[k]} ({wd_rec(ctx, old_names[k]).get('label', '')})"
                           if old_names[k] != "OHM" else "name of the OHM feature matched through the old QID"),
                          {"name": a["name"], "language": a["language"], "source": a["source"],
                           "is_primary": a["is_primary"]}))
    return out, listed


def plan_images(e: dict, case: Case) -> list[dict]:
    attrs = e["attributes"] if isinstance(e["attributes"], dict) else {}
    refs = attrs.get("media_refs")
    if CURATED_KEY in attrs or not isinstance(refs, list):
        return []
    changed = utc(case.changed_at)
    stale = [m for m in refs if isinstance(m, dict) and m.get("source") in ("wikidata", "wikipedia")
             and utc(m.get("fetched_at") or "") < changed]
    if not stale:
        return []
    keep = [m for m in refs if m not in stale]
    after = {"media_refs": keep if keep else None}
    files = ", ".join((m.get("file") or "?")[:40] for m in stale) or "[] (checked under the old QID)"
    return [change(e, case, "image", "drop_media_refs", "entities", e["entity_id"], "attributes.media_refs",
                   f"{len(refs)} item(s): {files}", f"{len(keep)} item(s)",
                   f"fetched for old QID {'/'.join(case.old_qids)} before {changed}",
                   {"media_refs": refs}, after)]


def plan_suspect_dates(e: dict, ctx: Ctx) -> tuple[list[dict], list[dict]]:
    """A row whose QID is right but whose dates are not (flag identity_audit:row_dates_suspect):
    set the range from the item (backfill_dates rules, the row's own end ignored) and drop the flag."""
    from pipeline.backfill_dates import plan_entity
    r = e["range"]
    case = Case(e["entity_id"], new_qid=e["qid"], new_known=True)
    if not e["qid"] or not r:
        return [], [{"entity_id": e["entity_id"], "name": e["name"], "issue": "dates_suspect_left",
                     "detail": "no QID or no primary range"}]
    p = plan_entity({"entity_type": e["type"], "wikidata_id": e["qid"], "verification_status": "pipeline_draft",
                     "flags": [], "range_id": r["range_id"], "row_end_year": None, "row_end_date": None},
                    claims_rec(ctx, e["qid"]), ctx.former.get(e["qid"], False), ctx.facts.get(e["entity_id"], []))
    manual = MANUAL_SUSPECT_DATES.get(e["entity_id"][:8])
    if p["action"] == "skip" and manual:
        sdate, edate, conf, why = manual
        sdate = r["start_date"] if sdate is KEEP else sdate
        edate = r["end_date"] if edate is KEEP else edate
        from pipeline.backfill_dates import era_year
        p = {"action": "manual", "start_date": sdate, "end_date": edate,
             "start": era_year(sdate) if sdate else None, "end": era_year(edate) if edate else None,
             "confidence": conf or r["date_confidence"], "start_prop": f"by hand: {why}", "end_prop": None}
    if p["action"] == "skip":
        return [], [{"entity_id": e["entity_id"], "name": e["name"], "issue": "dates_suspect_left",
                     "detail": f"{fmt_range(r)}; item {e['qid']} dates unusable ({p['reason']}; "
                               f"start {p.get('start')} end {p.get('end')})"}]
    props = ",".join(x for x in (p["start_prop"], p["end_prop"]) if x and x != "row")
    if claims_rec(ctx, e["qid"]).get("fallback"):
        p["confidence"] = "medium" if p["confidence"] == "high" else p["confidence"]
        props += " (best values only)"
    note = f"{NOTE}: row dates suspect; set from {e['qid']} {props} (was {fmt_range(r)})"
    out = []
    if (p["start_date"], p["end_date"]) != (r["start_date"], r["end_date"]):
        guard = {k: r[k] for k in ("start_date", "end_date", "start_year", "end_year", "date_method",
                                   "date_confidence", "notes")}
        after = {"start_date": p["start_date"], "end_date": p["end_date"], "start_year": p["start"],
                 "end_year": p["end"], "date_method": "source_database", "date_confidence": p["confidence"],
                 "notes": note}
        out.append(change(e, case, "dates", "set_range", "entity_temporal_ranges", r["range_id"],
                          "start_date,end_date", fmt_range(r), f"{p['start_date'] or ''}..{p['end_date'] or ''}",
                          f"row dates suspect; set from item {e['qid']} {props}", guard, after))
    flags = list((e["attributes"] or {}).get("validation_flags") or [])
    new_flags = [f for f in flags if f != DATES_SUSPECT_FLAG]
    out.append(change(e, case, "dates", "remove_flag", "entities", e["entity_id"], "attributes.validation_flags",
                      flags, new_flags, "dates now from the item", {"validation_flags": flags},
                      {"validation_flags": new_flags}))
    return out, []


def build_plan(conn, cases: dict[str, Case], wd: WikidataClient,
               suspect_dates: bool = True) -> tuple[list[dict], list[dict], dict]:
    from pipeline.backfill_dates import FORMER_ROOTS, load_facts
    cur = conn.cursor()
    suspect_ids: list[str] = []
    if suspect_dates:
        cur.execute("SELECT entity_id::text FROM entities WHERE attributes->'validation_flags' ? %s",
                    (DATES_SUSPECT_FLAG,))
        suspect_ids = [r[0] for r in cur.fetchall() if not r[0].startswith(USER_DECISION_PREFIXES)]
    ids = sorted(set(cases) | set(suspect_ids))
    state = load_state(cur, ids)
    listed: list[dict] = []
    todo: list[tuple[dict, Case]] = []
    for eid, case in cases.items():
        e = state.get(eid)
        why = None
        if eid.startswith(USER_DECISION_PREFIXES):
            why = "user_decision_row"
        elif e is None:
            why = "entity_gone (merged away)"
        elif e["qid"] in case.old_qids:
            why = f"still carries old QID {e['qid']}"
        if why:
            listed.append({"entity_id": eid, "name": e["name"] if e else "", "issue": "skipped", "detail": why})
            continue
        if case.new_known and (e["qid"] or None) != case.new_qid:
            # a later agent set another QID: the old ones are still wrong, compare with the current one
            case.sources.append(f"qid_changed_since:{case.new_qid}->{e['qid']}")
        todo.append((e, case))
    suspects = [state[i] for i in suspect_ids if i in state]
    old_new = ({q for _, c in todo for q in c.old_qids} | {e["qid"] for e, _ in todo if e["qid"]}
               | {e["qid"] for e in suspects if e["qid"]})
    print(f"cases {len(cases)}, in scope {len(todo)}; dates-suspect rows {len(suspects)}; QIDs {len(old_new)}",
          flush=True)
    wd.get_entities(old_new, need_links=True)
    claims = get_claims(wd, sorted(old_new))
    new_qids = {e["qid"] for e, _ in todo if e["qid"]} | {e["qid"] for e in suspects if e["qid"]}
    p31 = {q: wd_rec_raw(wd, q).get("p31", []) for q in new_qids}
    roots = wd.class_roots({c for cs in p31.values() for c in cs}, FORMER_ROOTS)
    former = {q: any(roots.get(c) for c in cs) for q, cs in p31.items()}
    fact_rows = {e["entity_id"]: e for e, _ in todo} | {e["entity_id"]: e for e in suspects}
    raw_facts = load_facts(cur, [{"entity_id": e["entity_id"], "summary": e["summary"],
                                  "description": e["description"]} for e in fact_rows.values()])
    # the range's own copies (periods, refs, timeline) are not evidence
    facts = {k: [f for f in v if not f[2].startswith(("geometry", "geo_ref", "timeline"))]
             for k, v in raw_facts.items()}
    cur.execute("""
        SELECT e.id, MIN(r.start_year), MAX(COALESCE(r.end_year, r.start_year))
        FROM unnest(%s::uuid[]) AS e(id)
        JOIN relationships r ON (r.source_entity_id = e.id OR r.target_entity_id = e.id)
        WHERE r.start_year IS NOT NULL AND r.confidence IS DISTINCT FROM 'low'
        GROUP BY e.id""", ([e["entity_id"] for e, _ in todo],))
    attested = {str(eid): (lo, hi) for eid, lo, hi in cur.fetchall()}
    ctx = Ctx(wd, claims, former, facts, attested)
    places = {r["external_id"] for e, _ in todo for r in e["refs"]
              if r["provider"] == "wikidata" and QID_RE.match(r["external_id"] or "")}
    wd.get_entities(places, need_links=True)
    place_coords = {}
    for q in places:
        c = wd_rec(ctx, q).get("coord")
        if c:
            place_coords[q] = (c[1], c[0])
    changes: list[dict] = []
    suspect_set = {e["entity_id"] for e in suspects}
    for e, case in todo:
        steps = [lambda e, c, x: plan_point(e, c, x, place_coords), plan_aliases]
        if e["entity_id"] not in suspect_set:
            steps.insert(0, plan_dates)
        mine: list[dict] = []
        for fn in steps:
            ch, li = fn(e, case, ctx)
            mine.extend(ch)
            listed.extend(li)
        deleted = {c["row_id"] for c in mine if c["action"] == "delete_period"}
        rng = next((c["after"] for c in mine if c["action"] == "set_range"), None)
        ch, li = plan_period_years(e, case, ctx, deleted, rng)
        changes.extend(mine + ch)
        listed.extend(li)
        changes.extend(plan_images(e, case))
    for e in suspects:
        ch, li = plan_suspect_dates(e, ctx)
        changes.extend(ch)
        listed.extend(li)
    repointed = sorted({e["entity_id"] for e, _ in todo if e["qid"]})
    return changes, listed, {"repointed": repointed}


def get_claims(wd: WikidataClient, qids: list[str], tries: int = 3) -> dict[str, dict]:
    """Full date claims (backfill_dates' cache and parser), fetched with maxlag=5.

    Unlike backfill_dates.fetch_claims, a batch Wikidata refuses (maxlag, error)
    is never cached as 'missing'. While Wikidata stays lagged, the remaining
    QIDs fall back to the entity cache's best value per property (no
    qualifiers, no month/day; marked 'fallback', never written to the cache)."""
    from pipeline.backfill_dates import API, CACHE_VERSION, CLAIMS_CACHE, parse_claims
    cache = {q: r for q, r in wd._load_jsonl(CLAIMS_CACHE, "qid").items()
             if r.get("status") != "ok" or r.get("v") == CACHE_VERSION}
    todo = sorted({q for q in qids if QID_RE.match(q) and q not in cache}, key=lambda q: int(q[1:]))
    lagging = False
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        data: dict = {}
        for attempt in range(tries):
            data = wd._get(API, {"action": "wbgetentities", "ids": "|".join(batch), "props": "info|claims",
                                 "format": "json", "maxlag": "5"}).json()
            if (data.get("error") or {}).get("code") != "maxlag":
                break
            time.sleep(10 * 2 ** attempt)
        if (data.get("error") or {}).get("code") == "maxlag":
            lagging = True
            print(f"   Wikidata lagged ({data['error'].get('info', '')[:60]}); falling back to the entity cache",
                  flush=True)
            break
        if data.get("error") or not data.get("entities"):
            continue
        got: dict[str, dict] = {}
        for key, ent in data["entities"].items():
            if "missing" in ent:
                got[ent.get("id", key)] = {"status": "missing"}
                continue
            real = ent.get("id", key)
            got[real] = parse_claims(ent)
            src = (ent.get("redirects") or {}).get("from") or (key if key != real else None)
            if src:
                got[src] = {"status": "redirect", "redirect_to": real}
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        new = [{"qid": q, "fetched": stamp, **r} for q, r in got.items() if q not in cache]
        for rec in new:
            cache[rec["qid"]] = rec
        wd._append(CLAIMS_CACHE, new)
    fallback = 0
    for q in qids:
        if q in cache:
            continue
        final, rec = wd.resolved(q)
        if not rec or rec.get("status") != "ok":
            continue
        dates = {prop: [{"r": "normal", "y": v[0], "p": v[1], "t": "", "q": {}}]
                 for prop, v in (rec.get("dates") or {}).items()}
        cache[q] = {"status": "ok", "fallback": True, "dates": dates}
        if final != q:
            cache[final] = cache[q]
        fallback += 1
    if fallback:
        print(f"   {fallback} QIDs use the entity cache's best values (lagging={lagging})", flush=True)
    return cache


def wd_rec_raw(wd: WikidataClient, qid: str) -> dict:
    _, rec = wd.resolved(qid)
    return rec if rec and rec.get("status") == "ok" else {}


# ── CSV ──────────────────────────────────────────────────────────────────────
PLAN_FIELDS = ["entity_id", "name", "entity_type", "old_qids", "new_qid", "kind", "action", "table", "row_id",
               "column", "old", "new", "reason", "guard", "after"]
LIST_FIELDS = ["entity_id", "name", "issue", "detail"]


def key_of(ch: dict) -> tuple:
    return (ch["action"], ch["row_id"], ch["old"], ch["new"])


def write_plan(out: Path, changes: list[dict], listed: list[dict]) -> None:
    write_csv(out / "planned.csv", sorted(changes, key=lambda c: (c["name"], c["entity_id"], c["kind"])),
              PLAN_FIELDS)
    write_csv(out / "listed.csv", sorted(listed, key=lambda c: (c["issue"], c["name"])), LIST_FIELDS)
    by = Counter((c["kind"], c["action"]) for c in changes)
    print(f"planned {len(changes)} changes on {len({c['entity_id'] for c in changes})} entities")
    for (k, a), n in sorted(by.items()):
        print(f"   {k:6s} {a:22s} {n}")
    print("listed: " + ", ".join(f"{k} {n}" for k, n in Counter(x["issue"] for x in listed).most_common()))


# ── apply ────────────────────────────────────────────────────────────────────
class Changed(Exception):
    pass


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def _one(cur, sql: str, args: tuple, what: str) -> None:
    cur.execute(sql, args)
    if cur.rowcount != 1:
        raise Changed(f"{what}: {cur.rowcount} rows matched the guard")


def apply_entity(cur, items: list[dict]) -> list[str]:
    """Apply one entity's changes (guarded); returns its rollback statements."""
    rb: list[str] = []
    order = {"deactivate_geo_ref": 0, "null_primary_geo_ref": 1, "delete_period": 2, "null_location": 3,
             "delete_alias": 4, "set_range": 5, "drop_media_refs": 6, "remove_flag": 7, "set_period_years": 8}
    reinsert_periods: list[str] = []
    reattach: list[str] = []
    eid = items[0]["entity_id"]
    cur.execute("SELECT coalesce(wikidata_id, '') FROM entities WHERE entity_id = %s FOR UPDATE", (eid,))
    row = cur.fetchone()
    if not row or row[0] != items[0]["new_qid"]:
        raise Changed(f"QID is now {row[0] if row else 'gone'!r}, planned {items[0]['new_qid']!r}")
    for ch in sorted(items, key=lambda c: order[c["action"]]):
        g, a, rid = ch["guard"], ch["after"], ch["row_id"]
        if ch["action"] == "deactivate_geo_ref":
            _one(cur, """
                UPDATE entity_geo_refs SET is_active = false, geometry_period_id = NULL,
                       source_meta = %s::jsonb, updated_at = now()
                WHERE geo_ref_id = %s AND is_active AND geometry_period_id IS NOT DISTINCT FROM %s::uuid
                  AND coalesce(source_meta, '{}'::jsonb) = %s::jsonb""",
                 (json.dumps(a["source_meta"]), rid, g["geometry_period_id"], json.dumps(g["source_meta"] or {})),
                 f"geo ref {rid}")
            reattach.append(
                f"UPDATE entity_geo_refs SET is_active = true, geometry_period_id = {_lit(g['geometry_period_id'])}"
                f"::uuid, source_meta = {_lit(g['source_meta'])}, updated_at = now() "
                f"WHERE geo_ref_id = '{rid}' AND NOT is_active AND source_meta->>'deactivated_by' = '{TAG}';")
        elif ch["action"] == "null_primary_geo_ref":
            _one(cur, "UPDATE entities SET primary_geo_ref_id = %s::uuid WHERE entity_id = %s "
                      "AND primary_geo_ref_id = %s",
                 (a["primary_geo_ref_id"], rid, g["primary_geo_ref_id"]), f"primary_geo_ref {rid}")
            reattach.append(f"UPDATE entities SET primary_geo_ref_id = '{g['primary_geo_ref_id']}' "
                            f"WHERE entity_id = '{rid}' AND primary_geo_ref_id IS NOT DISTINCT FROM "
                            f"{_lit(a['primary_geo_ref_id'])}::uuid;")
        elif ch["action"] == "delete_period":
            cur.execute("""
                SELECT geometry_period_id, entity_id, period_type, start_year, end_year,
                       encode(ST_AsEWKB(geom), 'hex'), encode(ST_AsEWKB(territory_geom), 'hex'), description,
                       provenance_mode, relationship_id, source_event_id, created_by, created_at, updated_at,
                       confidence::text
                FROM geometry_periods WHERE geometry_period_id = %s AND created_by IS NOT DISTINCT FROM %s
                  AND start_year = %s AND end_year IS NOT DISTINCT FROM %s""",
                        (rid, g["created_by"], g["start_year"], g["end_year"]))
            row = cur.fetchone()
            if not row:
                raise Changed(f"period {rid} changed")
            cur.execute("SELECT count(*) FROM entity_geo_refs WHERE geometry_period_id = %s", (rid,))
            if cur.fetchone()[0]:
                raise Changed(f"period {rid} still has a geo ref")
            _one(cur, "DELETE FROM geometry_periods WHERE geometry_period_id = %s", (rid,), f"period {rid}")
            (pid, eid, ptype, sy, ey, geom, terr, desc, prov, rel, src, by, cat, uat, conf) = row
            reinsert_periods.append(
                "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, geom, "
                "territory_geom, description, provenance_mode, relationship_id, source_event_id, created_by, "
                "created_at, updated_at, confidence) VALUES ("
                f"'{pid}', '{eid}', {_lit(ptype)}, {_lit(sy)}, {_lit(ey)}, "
                f"{('decode(' + _lit(geom) + ', ' + chr(39) + 'hex' + chr(39) + ')::geometry') if geom else 'NULL'}, "
                f"{('decode(' + _lit(terr) + ', ' + chr(39) + 'hex' + chr(39) + ')::geometry') if terr else 'NULL'}, "
                f"{_lit(desc)}, {_lit(prov)}, {_lit(str(rel) if rel else None)}::uuid, "
                f"{_lit(str(src) if src else None)}::uuid, {_lit(by)}, {_lit(str(cat) if cat else None)}::timestamp, "
                f"{_lit(str(uat) if uat else None)}::timestamp, {_lit(conf)}::confidence_level) "
                "ON CONFLICT (geometry_period_id) DO NOTHING;")
        elif ch["action"] == "null_location":
            cur.execute("""
                SELECT encode(ST_AsEWKB(geom), 'hex') FROM entity_locations
                WHERE location_id = %s AND location_method IS NOT DISTINCT FROM %s
                  AND GeometryType(geom) = 'POINT' AND abs(ST_X(geom) - %s) < 1e-9 AND abs(ST_Y(geom) - %s) < 1e-9""",
                        (rid, g["location_method"], g["x"], g["y"]))
            row = cur.fetchone()
            if not row:
                raise Changed(f"location {rid} changed")
            _one(cur, "UPDATE entity_locations SET geom = NULL, location_method = NULL, updated_at = now() "
                      "WHERE location_id = %s AND geom IS NOT NULL", (rid,), f"location {rid}")
            rb.append(f"UPDATE entity_locations SET geom = decode('{row[0]}', 'hex')::geometry, "
                      f"location_method = {_lit(g['location_method'])}, updated_at = now() "
                      f"WHERE location_id = '{rid}' AND geom IS NULL;")
        elif ch["action"] == "delete_alias":
            cur.execute("""
                SELECT alias_id, entity_id, name, language, source, is_primary, created_at, updated_at
                FROM entity_aliases WHERE alias_id = %s AND name = %s AND NOT is_primary""", (rid, g["name"]))
            row = cur.fetchone()
            if not row:
                raise Changed(f"alias {rid} changed")
            _one(cur, "DELETE FROM entity_aliases WHERE alias_id = %s AND name = %s", (rid, g["name"]), f"alias {rid}")
            aid, eid, name, lang, src, prim, cat, uat = row
            rb.append("INSERT INTO entity_aliases (alias_id, entity_id, name, language, source, is_primary, "
                      f"created_at, updated_at) VALUES ('{aid}', '{eid}', {_lit(name)}, {_lit(lang)}, {_lit(src)}, "
                      f"{_lit(prim)}, {_lit(str(cat) if cat else None)}::timestamp, "
                      f"{_lit(str(uat) if uat else None)}::timestamp) ON CONFLICT (alias_id) DO NOTHING;")
        elif ch["action"] == "set_range":
            cols = ("start_date", "end_date", "start_year", "end_year", "date_method", "date_confidence", "notes")
            where = " AND ".join(f"{c} IS NOT DISTINCT FROM %s" for c in cols)
            _one(cur, f"""
                UPDATE entity_temporal_ranges
                SET start_date = %s, end_date = %s, start_year = %s, end_year = %s, date_method = %s,
                    date_confidence = %s, notes = %s, updated_at = now()
                WHERE temporal_range_id = %s AND is_primary AND {where}""",
                 (*[a[c] for c in cols], rid, *[g[c] for c in cols]), f"range {rid}")
            rb.append("UPDATE entity_temporal_ranges SET "
                      + ", ".join(f"{c} = {_lit(g[c])}" for c in cols) + ", updated_at = now() "
                      f"WHERE temporal_range_id = '{rid}' AND notes IS NOT DISTINCT FROM {_lit(a['notes'])} "
                      f"AND start_date IS NOT DISTINCT FROM {_lit(a['start_date'])} "
                      f"AND end_date IS NOT DISTINCT FROM {_lit(a['end_date'])};")
        elif ch["action"] == "drop_media_refs":
            if a["media_refs"] is None:
                _one(cur, "UPDATE entities SET attributes = attributes - 'media_refs', updated_at = now() "
                          "WHERE entity_id = %s AND attributes->'media_refs' = %s::jsonb "
                          f"AND NOT attributes ? '{CURATED_KEY}'",
                     (rid, json.dumps(g["media_refs"])), f"media_refs {rid}")
                rb.append(f"UPDATE entities SET attributes = jsonb_set(attributes, '{{media_refs}}', "
                          f"{_lit(g['media_refs'])}) WHERE entity_id = '{rid}' AND NOT attributes ? 'media_refs';")
            else:
                _one(cur, "UPDATE entities SET attributes = jsonb_set(attributes, '{media_refs}', %s::jsonb), "
                          "updated_at = now() WHERE entity_id = %s AND attributes->'media_refs' = %s::jsonb "
                          f"AND NOT attributes ? '{CURATED_KEY}'",
                     (json.dumps(a["media_refs"]), rid, json.dumps(g["media_refs"])), f"media_refs {rid}")
                rb.append(f"UPDATE entities SET attributes = jsonb_set(attributes, '{{media_refs}}', "
                          f"{_lit(g['media_refs'])}) WHERE entity_id = '{rid}' "
                          f"AND attributes->'media_refs' = {_lit(a['media_refs'])};")
        elif ch["action"] == "set_period_years":
            cur.execute("SELECT confidence::text FROM geometry_periods WHERE geometry_period_id = %s", (rid,))
            row = cur.fetchone()
            if not row:
                raise Changed(f"period {rid} gone")
            _one(cur, """
                UPDATE geometry_periods SET start_year = %s, end_year = %s, description = %s,
                       confidence = coalesce(%s::confidence_level, confidence), updated_at = now()
                WHERE geometry_period_id = %s AND start_year = %s AND end_year IS NOT DISTINCT FROM %s
                  AND created_by IS NOT DISTINCT FROM %s AND description IS NOT DISTINCT FROM %s""",
                 (a["start_year"], a["end_year"], a["description"], a["confidence"], rid,
                  g["start_year"], g["end_year"], g["created_by"], g["description"]), f"period years {rid}")
            rb.append(f"UPDATE geometry_periods SET start_year = {_lit(g['start_year'])}, "
                      f"end_year = {_lit(g['end_year'])}, description = {_lit(g['description'])}, "
                      f"confidence = {_lit(row[0])}::confidence_level, updated_at = now() "
                      f"WHERE geometry_period_id = '{rid}' AND start_year = {_lit(a['start_year'])} "
                      f"AND end_year IS NOT DISTINCT FROM {_lit(a['end_year'])};")
        elif ch["action"] == "remove_flag":
            _one(cur, "UPDATE entities SET attributes = jsonb_set(attributes, '{validation_flags}', %s::jsonb), "
                      "updated_at = now() WHERE entity_id = %s "
                      "AND coalesce(attributes->'validation_flags', '[]'::jsonb) = %s::jsonb",
                 (json.dumps(a["validation_flags"]), rid, json.dumps(g["validation_flags"])), f"flags {rid}")
            rb.append(f"UPDATE entities SET attributes = jsonb_set(attributes, '{{validation_flags}}', "
                      f"{_lit(g['validation_flags'])}) WHERE entity_id = '{rid}' "
                      f"AND attributes->'validation_flags' = {_lit(a['validation_flags'])};")
    return reinsert_periods + reattach + rb


def pg_dump(path: Path, tables: list[str]) -> None:
    cmd = [*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
           *[a for t in tables for a in ("-t", t)], "history-mapped"]
    with path.open("wb") as fh:
        subprocess.run(cmd, stdout=fh, check=True)


def backup(conn, out: Path, entity_ids: list[str]) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dump = out / f"pre-apply-{stamp}.dump"
    print(f"backing up -> {dump}", flush=True)
    pg_dump(dump, ["entity_temporal_ranges", "entity_locations", "geometry_periods", "entity_geo_refs",
                   "entity_aliases"])
    cur = conn.cursor()
    cur.execute("""SELECT entity_id::text, wikidata_id, primary_geo_ref_id::text, attributes->'media_refs',
                          attributes ? %s, attributes->'validation_flags'
                   FROM entities WHERE entity_id = ANY(%s::uuid[])""", (CURATED_KEY, entity_ids))
    with (out / f"entities-image-columns-{stamp}.jsonl").open("w", encoding="utf-8") as fh:
        for eid, qid, pgr, media, curated, flags in cur.fetchall():
            fh.write(json.dumps({"entity_id": eid, "wikidata_id": qid, "primary_geo_ref_id": pgr,
                                 "media_refs": media, "curated": curated, "validation_flags": flags},
                                ensure_ascii=False) + "\n")


def run_artisan(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", *args],
                          capture_output=True, text=True, check=False)
    lines = [ln.strip() for ln in (proc.stdout + proc.stderr).splitlines() if ln.strip()]
    return proc.returncode, " / ".join(lines[-3:])


def apply(conn, out: Path, changes: list[dict], planned_path: Path, post: bool, meta: dict) -> None:
    with planned_path.open(encoding="utf-8") as fh:
        planned = {(r["action"], r["row_id"], r["old"], r["new"]) for r in csv.DictReader(fh)}
    todo = [c for c in changes if key_of(c) in planned]
    drift = [c for c in changes if key_of(c) not in planned]
    missing = len(planned) - len(todo)
    print(f"apply: {len(todo)} of {len(planned)} planned changes still hold; {missing} gone; "
          f"{len(drift)} new since the plan (not applied)")
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for c in todo:
        by_entity[c["entity_id"]].append(c)
    conn.rollback()
    conn.read_only = False
    backup(conn, out, list(by_entity))
    cur = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    log: list[dict] = []
    rollback = [f"-- Rollback for pipeline/audit/qid_consequences.py apply ({ts}): guarded inverses.",
                "-- Afterwards run timeline:rebuild <id> for the same entities.", "BEGIN;"]
    for eid, items in by_entity.items():
        cur.execute("SAVEPOINT qc")
        try:
            rb = apply_entity(cur, items)
        except Exception as exc:  # noqa: BLE001 - Changed, or a constraint another agent's write tripped
            cur.execute("ROLLBACK TO SAVEPOINT qc")
            for c in items:
                log.append({**c, "ts": ts, "status": f"skipped: {exc}"})
            continue
        cur.execute("RELEASE SAVEPOINT qc")
        rollback.extend(rb)
        for c in items:
            log.append({**c, "ts": ts, "status": "applied"})
    for c in drift:
        log.append({**c, "ts": ts, "status": "skipped: not in planned.csv (new since the plan)"})
    rollback.append("COMMIT;")
    conn.commit()
    (out / "rollback.sql").write_text("\n".join(rollback) + "\n", encoding="utf-8")
    write_csv(out / "applied.csv", log, ["ts", "status", *PLAN_FIELDS])
    print("applied: " + ", ".join(f"{k} {n}" for k, n in Counter(x["status"].split(":")[0] for x in log).items()))
    test_rollback(conn, out / "rollback.sql")
    if not post:
        return
    done = [x for x in log if x["status"] == "applied"]
    timeline = sorted({x["entity_id"] for x in done
                       if x["action"] in ("set_range", "delete_period", "set_period_years")})
    # repointed rows whose images are not checked under the new QID yet (none, or dropped now)
    dropped = {x["entity_id"] for x in done if x["action"] == "drop_media_refs"}
    cur = conn.cursor()
    cur.execute("SELECT entity_id::text FROM entities WHERE entity_id = ANY(%s::uuid[]) AND wikidata_id IS NOT NULL "
                "AND NOT attributes ? %s AND (NOT attributes ? 'media_refs' OR entity_id = ANY(%s::uuid[]))",
                (meta["repointed"], CURATED_KEY, sorted(dropped)))
    repointed = sorted(r[0] for r in cur.fetchall())
    conn.rollback()
    post_log = []
    # per-entity fetches, 50 ids per call (one Wikimedia batch), never a global refresh
    for i in range(0, len(repointed), 50):
        chunk = repointed[i:i + 50]
        rc, last = run_artisan(["entity:fetch-images", "--refresh", *[f"--entity-id={eid}" for eid in chunk]])
        for eid in chunk:
            post_log.append({"entity_id": eid, "step": "fetch-images", "rc": rc, "out": last})
        print(f"   fetch-images {i + len(chunk)}/{len(repointed)} rc={rc} {last[:80]}", flush=True)
    for eid in timeline:
        rc, last = run_artisan(["timeline:rebuild", eid])
        post_log.append({"entity_id": eid, "step": "timeline:rebuild", "rc": rc, "out": last})
    write_csv(out / "post-steps.csv", post_log, ["entity_id", "step", "rc", "out"])
    print(f"post: fetch-images {len(repointed)}, timeline:rebuild {len(timeline)}; failures "
          f"{sum(1 for p in post_log if p['rc'])}")


def test_rollback(conn, path: Path) -> None:
    """Run rollback.sql inside a transaction that is rolled back; report what it would restore."""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("--") and ln.strip() not in ("BEGIN;", "COMMIT;")]
    stmts = [s for s in "\n".join(lines).split(";\n") if s.strip()]
    cur = conn.cursor()
    n_rows = 0
    try:
        for s in stmts:
            cur.execute(s)
            n_rows += max(cur.rowcount, 0)
    finally:
        conn.rollback()
    print(f"rollback test: {len(stmts)} statements, {n_rows} rows restored (rolled back)")


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=("plan", "apply"))
    ap.add_argument("--applied", action="append", default=None,
                    help="an agent's applied.csv, optionally 'path::op1,op2' to take only those ops "
                         "(repeatable; default: the pass-1 files)")
    ap.add_argument("--rejected-attr", action="store_true",
                    help="also every QID-less row with attributes._rejected_wikidata_id that no input names "
                         "(old QID = the rejected one; change time unknown, so all its Wikimedia images count)")
    ap.add_argument("--no-suspect-dates", action="store_true",
                    help=f"do not re-date rows flagged {DATES_SUSPECT_FLAG}")
    ap.add_argument("--no-stale-flag", action="store_true",
                    help="do not add rows flagged identity_audit:stale_from_old_qid")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-post", action="store_true", help="apply: skip fetch-images and timeline rebuilds")
    args = ap.parse_args()
    paths = args.applied or DEFAULT_APPLIED
    args.out.mkdir(parents=True, exist_ok=True)
    cases = load_cases(paths)
    conn = connect(read_only=True)
    if not args.no_stale_flag:
        cur = conn.cursor()
        cur.execute("SELECT entity_id::text, name FROM entities WHERE attributes->'validation_flags' ? %s",
                    (STALE_FLAG,))
        missing = [(eid, name) for eid, name in cur.fetchall() if eid not in cases]
        for eid, name in missing:
            print(f"   flagged {STALE_FLAG} but no old QID in the inputs: {eid} {name}")
    if args.rejected_attr:
        if args.stage == "apply":
            raise SystemExit("--rejected-attr is plan-only: a QID the importer rejected because another row "
                             "holds it may be the right item (its dates and point are then genuine)")
        cur = conn.cursor()
        cur.execute("""SELECT entity_id::text, attributes->>'_rejected_wikidata_id' FROM entities
                       WHERE wikidata_id IS NULL AND attributes->>'_rejected_wikidata_id' ~ '^Q[1-9][0-9]*$'""")
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        extra = 0
        for eid, rej in cur.fetchall():
            if eid not in cases:
                cases[eid] = Case(eid, [rej], None, True, now, ["rejected_attr"])
                extra += 1
        print(f"   --rejected-attr: {extra} more QID-less rows with a rejected QID")
    wd = WikidataClient(CACHE_DIR, max_rps=0.5, workers=1)
    changes, listed, meta = build_plan(conn, cases, wd, not args.no_suspect_dates)
    print(f"Wikidata requests made: {wd.requests_made}")
    if args.stage == "plan":
        write_plan(args.out, changes, listed)
        return 0
    write_csv(args.out / "listed.csv", sorted(listed, key=lambda c: (c["issue"], c["name"])), LIST_FIELDS)
    apply(conn, args.out, changes, args.out / "planned.csv", not args.no_post, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
