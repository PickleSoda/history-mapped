#!/usr/bin/env python3
"""Person date backfill: life dates for undated people that backfill_dates could not date.

Scope: people with a QID and no entity_temporal_ranges row with a start year
(backfill_dates already took every plain Wikidata birth). Dates come from two
sources, in this order:

1. Wikidata, the statements backfill_dates left: a birth (P569) or death
   (P570) that is "unknown value" with an earliest/latest-date pair
   (P1319/P1326) at most 20 years wide, a century value narrowed by such a
   pair, or a value beside an "unknown value". A range is stored as its outer
   bounds (earliest birth, latest death), a decade as its label year, all with
   date_confidence low. A one-sided or wider bound, or a century, only limits
   what the lead may say. Over a preferred "unknown value" only with the
   lead's agreement.
2. The enwiki lead: the opening parentheses of the article's first sentence
   ('(c. 1294 – 1336)', '(died 1453)', '(born c. 540 BC, died 480 BC)'), read
   by parse_lead(). 'c.', '?', '1294/95', '1294 or 1295', '1290s',
   'c. 1240–1250' or a month/day alternative make it low; a one-sided bound
   ('before 1558', 'by 1489') is not a year of birth or death. Where Wikidata
   gives only a range and the lead a year inside it, the lead's year is used.

All sources must agree within 5 years (the audit's person tolerance) with each
other and with an end year the row already has; that end is kept.

A floruit or reign is not a lifespan, and the spec (duration_type point /
period / ongoing / uncertain; one 'primary' range) has no way to mark one, so
people with only a floruit (P1317), work period (P2031/P2032), 'fl.' or 'r.'
are listed (action 'list'), never stored.

Guards, as in backfill_dates: QIDs in doubt and the merge-review and
user-decision entities are skipped; no lifespan over 120 years; someone born
before 1910 with no death is skipped; the birth may not follow the person's
earliest dated fact and the lifespan must touch one. A lead birth equal to the
start of the person's own 'rules' relationship, or of a Wikidata floruit, is a
reign. Lead parses are written only once checked by hand (HAND_CHECK, by QID):
a clean '(1130–1167)' is a reign often enough.

A birth gives the start; with no birth, a known death fills an empty end (the
person stays off the map, but the end is a fact). Rows get date_method
source_database (Wikidata) or nlp_direct / nlp_approximate (the lead: the enum
has no Wikipedia value), date_confidence high | medium | low, duration_type
'period' once both ends are set, and notes
'backfill_person_dates:<start source>,<end source>'. Years only: Wikipedia's
days are often Julian without saying so. An existing primary row with a null
start is updated, never duplicated (one primary row per entity).

Dry run by default. --apply dumps entity_temporal_ranges and
entity_timeline_entries, appends guarded undo statements to rollback.sql,
writes in one transaction (each write guarded on the QID and the row as read),
appends applied.csv and rebuilds the timeline of each person written. Caches:
output/audit/cache/wd-person-dates.jsonl and enwiki-intros.jsonl.

    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.backfill_person_dates            # dry run
    scripts/capped.sh pipeline/.venv/bin/python3 -m pipeline.backfill_person_dates --apply    # write
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.audit.wd import API, QID_RE, WikidataClient, _parse_time
from pipeline.backfill_dates import (ALIVE_BORN_AFTER, MAX_LIFESPAN, _touches, fact_bounds, in_doubt,
                                     load_facts)

import psycopg

DSN = "postgresql://history-mapped:secret@localhost:5432/history-mapped"
COMPOSE = ["docker", "compose", "-f", str(_REPO_ROOT / "docker" / "docker-compose.yml")]
NOTE = "backfill_person_dates"
MERGE_VERDICTS = _REPO_ROOT / "output" / "audit" / "merge-review-20261101" / "verdicts.csv"
USER_DECISION_PREFIXES = ("a05afb75", "6255478f", "17d96812", "7baeedc3")
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
CLAIMS_CACHE = "wd-person-dates.jsonl"
INTRO_CACHE = "enwiki-intros.jsonl"
CACHE_VERSION = 1
# birth, death, floruit, work period start / end
PROPS = ("P569", "P570", "P1317", "P2031", "P2032")
EARLIEST, LATEST = "P1319", "P1326"
# Lead parses checked by hand (keyed by QID): "ok", or "reject:<why>" for a
# parse, or an item, that is wrong for the entity although the rules pass.
HAND_CHECK: dict[str, str] = {
    # 2026-11-01: every lead parse read against its article's first sentences
    **{q: "ok" for q in (
        "Q242270", "Q18277266", "Q4220766", "Q6656338", "Q8071190", "Q62059928", "Q7572005", "Q21665587",
        "Q717497", "Q208215", "Q311820", "Q701552", "Q272180", "Q3303037", "Q137652474", "Q89434711",
        "Q469785", "Q372361", "Q6553598", "Q3536611", "Q497911", "Q3090626", "Q4195288", "Q10742496",
        "Q1059956", "Q20639228", "Q4269914", "Q60790350", "Q613587", "Q94504", "Q4260268", "Q2603229",
        "Q13141797", "Q382276", "Q1463732", "Q29378297", "Q12415690", "Q2622828", "Q2348316", "Q7273018",
        "Q5255100", "Q10900403", "Q462987", "Q960462", "Q433440", "Q243118", "Q230898")},
    "Q48726684": "reject:reign_not_life",       # Yasodaman II (317–332) is his rule as sub-king
    "Q4907223": "reject:reign_not_life",        # Bijjala II (1130–1167) is the Kalachuri reign
    "Q3107477": "reject:reign_not_life",        # Sanjaya (716–746) is the Mataram reign
    "Q115868007": "reject:life_or_reign_unsure",  # Letya Min Nan (1068–1109) vs restored to the throne in 1118
    "Q612787": "reject:qid_namesake",           # the Pythagorean philosopher; the entity is the tyrant of Leontini
    "Q42296521": "reject:qid_namesake",         # Sir George Maclean the commissary general; the entity is the
                                                # Gold Coast governor (1801-1847)
}


class PoliteClient(WikidataClient):
    """The audit client with maxlag=5 on every API call (the quota is shared),
    backing off while the servers report lag."""

    def _get(self, url, params, timeout=60):
        if url.endswith("api.php"):
            params = {**params, "maxlag": "5"}
        for attempt in range(10):
            resp = super()._get(url, params, timeout)
            if url.endswith("api.php"):
                try:
                    err = (resp.json() or {}).get("error") or {}
                except ValueError:
                    err = {}
                if err.get("code") == "maxlag":
                    time.sleep(min(5 * 2 ** attempt, 120))
                    continue
            return resp
        raise RuntimeError(f"kept reporting maxlag: {url}")


def time_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── Wikidata statements ───────────────────────────────────────────────────────
def _time_of(snak: Any) -> dict | None:
    """{'y', 'p', 't'} of a time-valued snak, None for anything else."""
    if not isinstance(snak, dict) or snak.get("snaktype") != "value":
        return None
    value = (snak.get("datavalue") or {}).get("value")
    if not isinstance(value, dict):
        return None
    parsed = _parse_time(value)
    if not parsed or parsed[0] == 0:
        return None
    return {"y": parsed[0], "p": parsed[1], "t": value.get("time", "")}


def parse_statement(st: dict[str, Any]) -> dict[str, Any] | None:
    """A non-deprecated statement of a time property: rank 'r', 'some' for an
    unknown value, else 'y'/'p'/'t'; item qualifiers in 'q' ({prop: [ids]});
    earliest/latest-date qualifiers in 'lo'/'hi' as {'y', 'p', 't'}."""
    if not isinstance(st, dict) or st.get("rank") == "deprecated":
        return None
    snak = st.get("mainsnak") or {}
    out: dict[str, Any] = {"r": st.get("rank", "normal")}
    if snak.get("snaktype") == "somevalue":
        out["some"] = True
    elif snak.get("snaktype") == "value":
        tv = _time_of(snak)
        if tv is None:
            return None
        out.update(tv)
    else:
        return None  # novalue
    quals = st.get("qualifiers") or {}
    q: dict[str, list] = {}
    for prop, snaks in quals.items():
        if prop in (EARLIEST, LATEST):
            times = [t for t in (_time_of(s) for s in snaks) if t]
            if times:
                out["lo" if prop == EARLIEST else "hi"] = times[0]
            continue
        ids = []
        for s in snaks:
            v = ((s.get("datavalue") or {}).get("value")) if isinstance(s, dict) else None
            ids.append(v.get("id") if isinstance(v, dict) else None)
        q[prop] = ids
    if q:
        out["q"] = q
    return out


def parse_claims(ent: dict[str, Any]) -> dict[str, Any]:
    claims = ent.get("claims") or {}
    dates = {}
    for prop in PROPS:
        vals = [v for v in (parse_statement(s) for s in claims.get(prop) or []) if v]
        if vals:
            dates[prop] = vals
    enwiki = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
    return {"status": "ok", "v": CACHE_VERSION, "dates": dates, "enwiki": enwiki}


def fetch_claims(client: WikidataClient, qids: list[str]) -> dict[str, dict[str, Any]]:
    """Birth, death, floruit and work-period statements with their qualifiers,
    plus the enwiki title, for each item (cached, 50 ids a call)."""
    cache = {q: r for q, r in client._load_jsonl(CLAIMS_CACHE, "qid").items()
             if r.get("status") != "ok" or r.get("v") == CACHE_VERSION}
    todo = sorted({q for q in qids if QID_RE.match(q) and q not in cache}, key=lambda q: int(q[1:]))
    if client.offline:
        todo = []  # uncached items plan as qid_missing
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        data = client._get(API, {"action": "wbgetentities", "ids": "|".join(batch), "format": "json",
                                 "props": "info|claims|sitelinks", "sitefilter": "enwiki"}).json()
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
        for q in batch:
            got.setdefault(q, {"status": "missing"})
        stamp = time_stamp()
        new = [{"qid": q, "fetched": stamp, **r} for q, r in got.items() if q not in cache]
        for rec in new:
            cache[rec["qid"]] = rec
        client._append(CLAIMS_CACHE, new)
        print(f"   claims {min(i + 50, len(todo))}/{len(todo)}", flush=True)
    return cache


def resolve(cache: dict[str, dict], qid: str) -> tuple[str, dict | None]:
    seen: set[str] = set()
    rec = cache.get(qid)
    while rec and rec.get("status") == "redirect" and qid not in seen:
        seen.add(qid)
        qid = rec["redirect_to"]
        rec = cache.get(qid)
    return qid, rec


# ── enwiki intros ─────────────────────────────────────────────────────────────
def fetch_intros(client: WikidataClient, titles: list[str]) -> dict[str, dict[str, Any]]:
    """{title: {'extract', 'final'}} of each article's lead as plain text
    (TextExtracts allows 20 intros a call; redirects followed), cached."""
    cache = client._load_jsonl(INTRO_CACHE, "t")
    todo = [] if client.offline else sorted({t for t in titles if t and t not in cache})
    for i in range(0, len(todo), 20):
        batch = todo[i:i + 20]
        data = client._get(ENWIKI_API, {
            "action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
            "exlimit": "20", "redirects": "1", "titles": "|".join(batch),
            "format": "json", "formatversion": "2"}).json()
        query = data.get("query") or {}
        alias = {n["from"]: n["to"] for n in query.get("normalized", [])}
        redirect = {r["from"]: r["to"] for r in query.get("redirects", [])}
        pages = {p.get("title"): p for p in query.get("pages", [])}
        stamp = time_stamp()
        rows = []
        for t in batch:
            final = alias.get(t, t)
            final = redirect.get(final, final)
            page = pages.get(final) or {}
            rows.append({"t": t, "fetched": stamp, "final": final,
                         "missing": bool(page.get("missing")) or not page,
                         "extract": page.get("extract") or ""})
        if "continue" in data:
            # extracts are paged when the batch is long; fetch the rest singly
            for r in rows:
                if not r["missing"] and not r["extract"]:
                    r.update(_fetch_one_intro(client, r["t"]), fetched=stamp)
        for r in rows:
            cache[r["t"]] = r
        client._append(INTRO_CACHE, rows)
        print(f"   intros {min(i + 20, len(todo))}/{len(todo)}", flush=True)
    return cache


def _fetch_one_intro(client: WikidataClient, title: str) -> dict[str, Any]:
    data = client._get(ENWIKI_API, {
        "action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
        "redirects": "1", "titles": title, "format": "json", "formatversion": "2"}).json()
    pages = (data.get("query") or {}).get("pages", [])
    page = pages[0] if pages else {}
    return {"final": page.get("title", title), "missing": bool(page.get("missing")) or not page,
            "extract": page.get("extract") or ""}


# ── enwiki lead parsing ───────────────────────────────────────────────────────
_MONTH1 = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
           r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?")
_MONTH = rf"{_MONTH1}(?:\s*(?:/|or)\s*{_MONTH1})?"
_DAY = r"\d{1,2}(?:\s*(?:/|or)\s*\d{1,2})?"
_ERA = r"(?:B\.?\s?C\.?\s?E\.?|B\.?\s?C\.?|A\.?\s?D\.?|C\.?\s?E\.?)(?![A-Za-z])"
_DATE = rf"""
    (?:(?:on|in)\s+)?
    (?:(?P<bound>before|after|by|bef\.|aft\.|not\ before|not\ after|no\ later\ than|no\ earlier\ than)\s*)?
    (?:(?P<approx>c\.|ca\.|circa|approximately|approx\.|about|around|probably|possibly)\s*)?
    (?:(?P<pre_era>AD|A\.D\.|CE)\s+)?
    (?:(?P<day1>{_DAY})\s+(?P<mon1>{_MONTH})\s+
      |(?P<mon2>{_MONTH})\s+(?:(?P<day2>{_DAY}),?\s+)?
      |(?P<part>early|mid|late|mid-|spring|summer|autumn|fall|winter)[\s-]+(?:of\s+)?)?
    (?P<year>\d{{1,4}})(?P<decade>s)?
    (?:\s*(?:/|\ or\ )\s*(?:c\.\s*)?(?P<alt>\d{{1,4}}))?
    (?:\s*(?P<era>{_ERA}))?
    (?:\s*(?P<q>\?))?
"""
DATE_RE = re.compile(rf"^{_DATE}$", re.X | re.I)
COARSE_RE = re.compile(r"(?:century|centuries|millennium|\d(?:st|nd|rd|th)\b)", re.I)
UNKNOWN_SIDE = {"?", "??", "unknown", "", "?)"}
_PREFIX = {
    "floruit": re.compile(r"^(?:fl\.?|floruit|flourished|active|lived)\s*:?\s*", re.I),
    "reign": re.compile(r"^(?:r\.|reigned|reign|ruled|regnal\s+years|in\s+office|term)\s*:?\s*", re.I),
    "born": re.compile(r"^(?:born|b\.)\s*:?\s*", re.I),
    "died": re.compile(r"^(?:died|d\.|killed|executed|murdered|assassinated)\s*:?\s*", re.I),
}
_PLACE_TAIL = re.compile(r"\s+(?:in|at|near)\s+[A-Z].*$")
STOP_WORDS = re.compile(r"\s(?:was|is|were|are|became|served|ruled|reigned|had|held|during|who|which|whose)\s")
_INNER_RANGE = re.compile(r"\d\s*(?:–|—|−|-)\s*(?:c\.\s*)?\d")
SEG_SPLIT = re.compile(r";|,\s*(?=(?:r\.|reigned|ruled|died|d\.|born|b\.|fl\.|floruit)\s)", re.I)


def lead_groups(extract: str) -> list[str]:
    """The top-level parentheticals of the lead's first sentence (up to the
    first top-level 'was'/'is'… or sentence end), nested parentheses flattened."""
    text = re.sub(r"\s+", " ", (extract or "").replace("\xa0", " ")).strip()
    groups: list[str] = []
    depth, start = 0, 0
    for i, ch in enumerate(text):
        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
            if depth == 0:
                groups.append(text[start:i].replace("(", ";").replace(")", ";"))
        elif depth == 0:
            if text.startswith(". ", i) or STOP_WORDS.match(text, i):
                break
        if i > 1500:
            break
    return groups


def parse_date(s: str) -> dict | None:
    """One date: {'n', 'alt' (unsigned years; alt for '1603/4', '1341 or c.
    1320', '1290s' -> the decade's end), 'era' ('BC'|'AD'|None), 'why' (what
    makes it approximate)}. None unless it is one dated year."""
    s = s.strip().strip(",").strip()
    m = DATE_RE.match(s) if s else None
    if not m:
        return None
    year = int(m.group("year"))
    era = m.group("era") or m.group("pre_era")
    era = None if not era else ("BC" if era.upper().replace(".", "").replace(" ", "").startswith("B") else "AD")
    if year == 0 or (year > 2030 and era != "BC"):
        return None
    alt = year
    if m.group("decade") and not m.group("year").endswith("0"):
        return None  # '1294s'
    if m.group("alt"):
        a = m.group("alt")
        alt = int(m.group("year")[: max(0, len(m.group("year")) - len(a))] + a)
    why = [k for k in ("approx", "bound", "decade", "alt", "q", "part") if m.group(k)]
    if any(x in (m.group("day1") or "") + (m.group("day2") or "") + (m.group("mon1") or "") +
           (m.group("mon2") or "") for x in ("/", " or ")):
        why.append("day_alt")
    return {"n": year, "alt": alt, "era": era, "why": why, "bound": (m.group("bound") or "").lower()}


def _years(d: dict, era: str | None, role: str) -> int:
    """The signed year a date gives as a birth (its earliest reading) or a
    death (its latest): a stated range is stored as its outer bounds."""
    bc = (d["era"] or era) == "BC"
    lo, hi = sorted((-d["n"], -d["alt"]) if bc else (d["n"], d["alt"]))
    return lo if role == "birth" else hi


def _side(txt: str, role: str) -> tuple[dict | None, list[str]]:
    """A range side: (date or None for unknown, flags). Raises ValueError when
    the side is text that is not a date."""
    t = txt.strip().strip(",").strip()
    flags: list[str] = []
    pref = _PREFIX["born" if role == "birth" else "died"].match(t)
    if pref:
        t, flags = t[pref.end():], ["side_prefix"]
    if t.lower() in UNKNOWN_SIDE:
        return None, flags + ["unknown_side"]
    d = parse_date(t)
    if d is None and COARSE_RE.search(t):
        return None, flags + ["coarse_side"]
    if d is None:
        raise ValueError(t)
    return d, flags


def parse_range(seg: str) -> dict | None:
    """'c. 332 – c. January 257 BC' -> birth -332, death -257. A side may be
    unknown ('?') or a century (dropped); a spaced dash splits before an
    unspaced one, so 'c. 1240–1250 – 1314' is a birth range then a death."""
    s = seg.strip()
    for rx in (r"\s+(?:–|—|−|‐|-)\s+|\s+to\s+", r"\s*(?:–|—|−|‐|-)\s*"):
        parts = re.split(rx, s)
        if len(parts) == 2:
            break
        if len(parts) == 3 and rx.startswith(r"\s*"):
            parts = []
    else:
        return None
    if len(parts) != 2:
        return None
    a_txt, b_txt = parts
    if re.search(r"\s(?:–|—|−|-)\s", a_txt) or re.search(r"\s(?:–|—|−|-)\s", b_txt):
        return None
    try:
        a, fa = (_range_side if _INNER_RANGE.search(a_txt) else _side)(a_txt, "birth")
        b, fb = (_range_side if _INNER_RANGE.search(b_txt) else _side)(b_txt, "death")
    except ValueError:
        return None
    if a is None and b is None:
        return None
    flags = fa + fb
    a_era = a["era"] if a else None
    b_era = b["era"] if b else None
    if a and b:
        if a_era is None and b_era == "BC":      # 'c. 332 – 257 BC': both BC
            a_era = "BC"
        elif a_era == "BC" and b_era is None:    # '63 BC – 14' (AD 14): checked by hand
            flags.append("era_ambiguous")
            b_era = "AD"
    birth = _years(a, a_era, "birth") if a else None
    death = _years(b, b_era, "death") if b else None
    if birth is not None and death is not None and birth > death:
        return None
    return {"birth": birth, "death": death,
            "b_why": sorted(set(a["why"]) | ({"bound"} if a["bound"] else set())) if a else [],
            "d_why": sorted(set(b["why"]) | ({"bound"} if b["bound"] else set())) if b else [],
            "bounds": [x["bound"] for x in (a, b) if x and x["bound"]], "flags": sorted(set(flags))}


def _range_side(txt: str, role: str) -> tuple[dict, list[str]]:
    """A side that is itself a range ('c. 1240–1250'): its outer bound, approximate."""
    t = txt.strip()
    pref = _PREFIX["born" if role == "birth" else "died"].match(t)
    flags = ["side_range"] + (["side_prefix"] if pref else [])
    if pref:
        t = t[pref.end():]
    m = re.match(r"^(.*?\d)\s*(?:–|—|−|-)\s*(.+)$", t)
    if not m:
        raise ValueError(t)
    lo, hi = parse_date(m.group(1)), parse_date(m.group(2))
    if lo is None or hi is None:
        raise ValueError(t)
    era = hi["era"] or lo["era"]
    span = sorted((-lo["n"], -hi["alt"]) if era == "BC" else (lo["n"], hi["alt"]))
    n, alt = (abs(span[1]), abs(span[0])) if era == "BC" else (span[0], span[1])
    return {"n": n, "alt": alt, "era": era, "why": sorted(set(lo["why"] + hi["why"] + ["range"])),
            "bound": lo["bound"] or hi["bound"]}, flags


def parse_segment(seg: str) -> dict | None:
    """Classify one piece of a lead parenthetical: kind 'life', 'born',
    'died', 'floruit' or 'reign', with signed years."""
    s = seg.strip().strip(",").strip()
    if not s or not (re.search(r"\d", s) or re.match(r"(?:fl\.|floruit|flourished|r\.|reigned)\s", s, re.I)):
        return None
    for kind, rx in _PREFIX.items():
        m = rx.match(s)
        if not m:
            continue
        rest = s[m.end():].strip()
        if kind in ("floruit", "reign"):
            r = parse_range(rest)
            d = parse_date(rest) if r is None else None
            if r is None and d is None:
                return {"kind": kind, "text": s, "coarse": True}
            years = (r["birth"], r["death"]) if r else (_years(d, None, "birth"), _years(d, None, "death"))
            return {"kind": kind, "text": s, "years": years}
        if kind == "born":
            r = parse_range(rest)  # 'born before 657 – c. 679', 'born 1294, died 1336'
            if r is None and re.search(r",\s*(?:died|d\.)\s", rest):
                r = parse_range(re.sub(r",\s*(?=(?:died|d\.)\s)", " – ", rest, count=1))
            if r is not None:
                return {"kind": "life", "text": s, **r, "flags": r["flags"] + ["born_prefix"]}
        flags: list[str] = []
        place = _PLACE_TAIL.search(rest)
        if place:
            rest, flags = rest[:place.start()], ["place"]
        role = "birth" if kind == "born" else "death"
        try:
            d, f = (_range_side if _INNER_RANGE.search(rest) else _side)(rest, role)
        except ValueError:
            d, f = None, []
        if d is None:
            if "," in rest:  # 'died in Dutch Ceylon, 1734', 'd. 1254, Cairo', 'born 1944, Khmer: …'
                hits = [x for x in (parse_date(piece) for piece in rest.split(",")) if x]
                d, f = (hits[0], ["place"]) if len(hits) == 1 else (None, [])
            if d is None:
                return {"kind": kind, "text": s, "unparsed": True}
        why = sorted(set(d["why"]) | ({"bound"} if d["bound"] else set()))
        year = _years(d, None, role)
        out = {"kind": kind, "text": s, "birth": None, "death": None, "b_why": [], "d_why": [],
               "bounds": [d["bound"]] if d["bound"] else [], "flags": sorted(set(flags + f))}
        out["birth" if kind == "born" else "death"] = year
        out["b_why" if kind == "born" else "d_why"] = why
        return out
    r = parse_range(s)
    if r:
        return {"kind": "life", "text": s, **r}
    return None


def parse_lead(extract: str) -> dict:
    """What the lead's opening parentheses say about the life: {'kind': life |
    born | died | floruit | reign | ambiguous | none, 'birth', 'death',
    'b_why'/'d_why' (approximations), 'flags', 'clean', 'text', 'others'
    (floruit/reign pieces seen)}.

    Each parenthetical is split on ';' (language glosses come first) and before
    a ', r.'/', died' piece; a piece that is not a date on its own is retried
    on what follows its last comma ('Mongolian: …, 1300 – August 24, 1327'),
    which is never clean. Clean means a bare 'YYYY – YYYY' with nothing
    approximate, on its own."""
    found: list[dict] = []
    for g in lead_groups(extract):
        for seg in SEG_SPLIT.split(g):
            p = parse_segment(seg)
            tail = False
            if p is None and "," in seg:
                pieces = re.split(r",\s+", seg)
                for k in range(1, len(pieces)):
                    p = parse_segment(", ".join(pieces[k:]))
                    if p and not p.get("unparsed") and not p.get("coarse"):
                        tail = True
                        break
                    p = None
            if p:
                p["tail"] = tail
                found.append(p)
    life = [p for p in found if p["kind"] in ("life", "born", "died") and not p.get("unparsed")]
    others = [p for p in found if p["kind"] in ("floruit", "reign")]
    out: dict[str, Any] = {"others": [o["text"] for o in others], "birth": None, "death": None,
                           "b_why": [], "d_why": [], "flags": [],
                           "unparsed": [p["text"] for p in found if p.get("unparsed")]}
    kinds = sorted(p["kind"] for p in life)
    if kinds == ["born", "died"]:  # 'born c. 540 BC, died 11 August 480 BC' as two pieces
        b, d = sorted(life, key=lambda p: p["kind"])
        if b["birth"] <= d["death"]:
            life = [{**b, "kind": "life", "text": f"{b['text']}; {d['text']}", "death": d["death"],
                     "d_why": d["d_why"], "bounds": b["bounds"] + d["bounds"],
                     "flags": sorted(set(b["flags"] + d["flags"] + ["combined"])),
                     "tail": b["tail"] or d["tail"]}]
    if len(life) > 1:
        return {**out, "kind": "ambiguous", "text": " | ".join(p["text"] for p in life), "clean": False}
    if not life:
        if others:
            o = others[0]
            return {**out, "kind": o["kind"], "text": o["text"], "years": o.get("years"), "clean": False}
        return {**out, "kind": "none", "text": "", "clean": False}
    p = life[0]
    flags = p["flags"] + (["tail"] if p["tail"] else [])
    clean = (p["kind"] == "life" and p["birth"] is not None and p["death"] is not None
             and not p["b_why"] and not p["d_why"] and not flags)
    return {**out, "kind": p["kind"], "text": p["text"], "birth": p["birth"], "death": p["death"],
            "b_why": p["b_why"], "d_why": p["d_why"], "flags": flags, "clean": clean}


# ── planning ──────────────────────────────────────────────────────────────────
TOL = 5             # years two sources (or a source and the row) may differ by: the audit's person tolerance
BOUND_WIDTH = 20    # an earliest/latest-date pair at most this wide is a usable range
SHORT_LIFE = 15     # a shorter lifespan is more likely a reign or office: hand-checked
SCOPE_QUALIFIERS = {"P518", "P642", "P1013", "P5102", "P3831", "P2868", "P794", "P2210", "P276"}
APPROX_QUALIFIERS = {"P1480", "P4241"}
DISPUTED = "Q18912752"
GREGORIAN_PRE_1584 = "Q26961029"
CONF_RANK = {"low": 0, "medium": 1, "high": 2}
REIGN_WORDS = re.compile(r"\b(?:reign\w*|ruled?|ruling|throne|succeeded|accession|crowned|enthroned|"
                         r"became\s+(?:king|queen|emperor|sultan|khan|pope|shah)|in\s+office|r\.)\W", re.I)


def interval(year: int, precision: int) -> tuple[int, int]:
    """The years a Wikidata value can mean ('-0480' at decade precision is 489-480 BCE)."""
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


def _gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, max(a[0], b[0]) - min(a[1], b[1]))


def wd_values(values: list[dict]) -> dict[str, Any]:
    """Sort an item's birth (or death) statements into usable year ranges
    ('cands'), limits that only bound the year ('limits': a century, a wide or
    one-sided earliest/latest pair) and whether an 'unknown value' is among them.

    Statements about a part or aspect, or marked disputed, are ignored."""
    out: dict[str, Any] = {"cands": [], "limits": [], "unknown": False}
    for v in values:
        q = v.get("q") or {}
        if SCOPE_QUALIFIERS & set(q) or any(x != GREGORIAN_PRE_1584 for x in q.get("P31", [])):
            continue
        if DISPUTED in q.get("P1480", []):
            continue
        lo_q, hi_q = v.get("lo"), v.get("hi")
        lo = interval(lo_q["y"], lo_q["p"])[0] if lo_q else None
        hi = interval(hi_q["y"], hi_q["p"])[1] if hi_q else None
        approx = bool(APPROX_QUALIFIERS & set(q)) or lo is not None or hi is not None
        rank = v.get("r", "normal")
        if "y" not in v and rank == "preferred" and lo is None and hi is None:
            out["pref_unknown"] = True  # Wikidata's best answer is "unknown"
        if "y" in v and v["p"] >= 8:
            a, b = interval(v["y"], v["p"])
            how = "value" if v["p"] >= 9 else "decade"
            out["cands"].append({"lo": a, "hi": b, "y": v["y"], "how": how, "r": rank,
                                 "approx": approx or how == "decade", "ev": _ev(v)})
        elif lo is not None and hi is not None and lo <= hi and hi - lo <= BOUND_WIDTH:
            out["cands"].append({"lo": lo, "hi": hi, "how": "bounds", "r": rank, "approx": True, "ev": _ev(v)})
        else:
            if "y" not in v:
                out["unknown"] = True
            a, b = interval(v["y"], v["p"]) if "y" in v else (None, None)
            lim_lo = max(x for x in (a, lo) if x is not None) if (a is not None or lo is not None) else None
            lim_hi = min(x for x in (b, hi) if x is not None) if (b is not None or hi is not None) else None
            if lim_lo is not None or lim_hi is not None:
                out["limits"].append({"lo": lim_lo, "hi": lim_hi, "ev": _ev(v)})
    return out


def _ev(v: dict) -> str:
    """'unknown value [earliest 945, latest 950]', '1195 (precision 7, circa)'."""
    head = "unknown value" if "y" not in v else (f"{v['y']}" + (f" (precision {v['p']})" if v["p"] != 9 else ""))
    bits = []
    if v.get("lo"):
        bits.append(f"earliest {v['lo']['y']}")
    if v.get("hi"):
        bits.append(f"latest {v['hi']['y']}")
    if APPROX_QUALIFIERS & set(v.get("q") or {}):
        bits.append("circa")
    if v.get("r") == "preferred":
        bits.append("preferred")
    return head + (f" [{', '.join(bits)}]" if bits else "")


def pick_wd(w: dict, role: str) -> tuple[dict | None, str]:
    """The year an item's statements give for a birth (a range's earliest
    year) or death (its latest), as {'year', 'conf', 'ev'}, or None and why:
    'none', 'unknown', 'limits_only' (only a century or a one-sided/wide
    bound), 'conflict' (statements more than TOL apart, or outside a limit)."""
    cands = w["cands"]
    if not cands:
        if w["limits"]:
            return None, "limits_only"
        return None, "unknown" if w["unknown"] else "none"
    if any(_gap((a["lo"], a["hi"]), (b["lo"], b["hi"])) > TOL for i, a in enumerate(cands) for b in cands[i + 1:]):
        return None, "conflict"
    pool = [c for c in cands if c["r"] == "preferred"] or cands
    best = min(pool, key=lambda c: (c["how"] != "value", c["hi"] - c["lo"]))
    year = best["y"] if best["how"] == "decade" else (best["lo"] if role == "birth" else best["hi"])
    if not within_limits(year, w["limits"]):
        return None, "conflict"
    approx = (best["approx"] or best["how"] != "value" or w["unknown"] or bool(w["limits"])
              or len({(c["lo"], c["hi"]) for c in cands}) > 1)
    conf = "low" if approx else "high"
    ev = "; ".join(c["ev"] for c in cands) + ("; also unknown value" if w["unknown"] else "")
    span = (min(c["lo"] for c in cands), max(c["hi"] for c in cands))
    # Wikidata itself doubts the value: its best-ranked answer is "unknown", or
    # an "unknown value" stands beside a value of no higher rank
    doubt = bool(w.get("pref_unknown")) or (w["unknown"] and best["r"] != "preferred")
    return {"year": year, "conf": conf, "ev": ev, "how": best["how"], "span": span, "doubt": doubt}, ""


def refine(wd: dict | None, lead_year: int | None) -> bool:
    """The lead's year refines Wikidata's: Wikidata gives only a range (an
    earliest/latest pair, or several values) and the lead's year lies inside it."""
    return (wd is not None and lead_year is not None and wd["span"][0] < wd["span"][1]
            and wd["span"][0] <= lead_year <= wd["span"][1])


def within_limits(year: int, limits: list[dict]) -> bool:
    return all((lim["lo"] is None or year >= lim["lo"] - TOL) and (lim["hi"] is None or year <= lim["hi"] + TOL)
               for lim in limits)


def agrees(year: int, w: dict) -> bool:
    """A year from another source agrees with an item's statements: within TOL
    of each usable one and inside every limit."""
    return (all(_gap((year, year), (c["lo"], c["hi"])) <= TOL for c in w["cands"])
            and within_limits(year, w["limits"]))


def floruit_text(dates: dict, lead: dict | None) -> str:
    """Floruit / work period / reign the sources give (listed, never stored)."""
    bits = []
    for prop, label in (("P1317", "fl."), ("P2031", "work from"), ("P2032", "work until")):
        ys = sorted({v["y"] for v in dates.get(prop, []) if "y" in v})
        if ys:
            bits.append(f"WD {label} {'/'.join(map(str, ys))}")
    if lead:
        bits += [f"enwiki '{t}'" for t in lead.get("others", [])]
        if lead.get("kind") in ("floruit", "reign") and lead.get("text") and f"enwiki '{lead['text']}'" not in bits:
            bits.append(f"enwiki '{lead['text']}'")
    return "; ".join(bits)


def reign_starts(facts: list[tuple]) -> set[int]:
    return {lo for lo, _hi, label in facts if lo is not None and label.startswith("rel rules")}


def year_in_reign_context(extract: str, year: int) -> bool:
    """The lead names the year again after a reign word ('ruled from 716')."""
    n = str(abs(year))
    for m in re.finditer(rf"(?<![\d–-]){n}(?!\d)", extract or ""):
        if REIGN_WORDS.search(extract[max(0, m.start() - 60):m.start()]):
            return True
    return False


def wd_ev(values: list[dict]) -> str:
    return "; ".join(_ev(v) for v in values)


def _min_conf(*confs: str | None) -> str:
    return min((c for c in confs if c), key=CONF_RANK.get)


def plan_person(e: dict, rec: dict | None, lead: dict | None, extract: str, facts: list[tuple],
                excluded: str | None = None, hand: str | None = None) -> dict:
    """The row to write for one undated person, or why not.

    e: entity_id, wikidata_id, verification_status, flags, range_id,
       row_end_year, row_end_date, date_confidence.
    rec: the item's claims record (redirects followed); lead: parse_lead() of
    its enwiki intro (None without one); facts: (start, end, label) of its
    dated facts in the DB; excluded: why another agent owns it; hand: the
    HAND_CHECK verdict for its QID."""
    def skip(reason: str, action: str = "skip", **kw) -> dict:
        return {**info, "action": action, "reason": reason, **kw}

    info: dict[str, Any] = {"lead_text": (lead or {}).get("text", ""), "lead_kind": (lead or {}).get("kind", ""),
                            "clean": bool((lead or {}).get("clean")), "row_end": e.get("row_end_year")}
    if excluded:
        return skip(excluded)
    if in_doubt(e):
        return skip("qid_in_doubt")
    if not rec or rec.get("status") != "ok":
        return skip("qid_missing")
    dates = rec.get("dates") or {}
    info.update(wd_birth=wd_ev(dates.get("P569", [])), wd_death=wd_ev(dates.get("P570", [])),
                floruit=floruit_text(dates, lead))
    if hand and hand.startswith("reject"):
        return skip("hand_check:" + hand.split(":", 1)[-1])
    wb, wdd = wd_values(dates.get("P569", [])), wd_values(dates.get("P570", []))
    b_wd, b_why = pick_wd(wb, "birth")
    d_wd, d_why = pick_wd(wdd, "death")
    if b_why == "conflict":
        return skip("wd_birth_conflict")
    if d_why == "conflict":
        return skip("wd_death_conflict")
    lead = lead or {}

    # ── birth: Wikidata first, then the lead; both must agree ───────────────
    birth = None
    if b_wd:
        birth = {"year": b_wd["year"], "conf": b_wd["conf"],
                 "src": "P569" + ("-bounds" if b_wd["how"] == "bounds" else "")}
    lead_used = False
    if lead.get("birth") is not None and "bound" in lead["b_why"]:
        info["lead_note"] = "birth is a one-sided bound"
        lead = {**lead, "birth": None}
    if lead.get("death") is not None and "bound" in lead["d_why"]:
        info["lead_note"] = "death is a one-sided bound"
        lead = {**lead, "death": None}
    if lead.get("birth") is not None:
        if not agrees(lead["birth"], wb):
            return skip("birth_sources_disagree" if birth else "lead_birth_outside_wikidata")
        if birth is None:
            birth = {"year": lead["birth"], "conf": "low" if lead["b_why"] else "medium", "src": "enwiki"}
            lead_used = True
        elif refine(b_wd, lead["birth"]):  # Wikidata 815-830, the lead 'c. 830'
            birth = {"year": lead["birth"], "conf": "low", "src": "enwiki+P569"}
            lead_used = True
    if b_wd and b_wd["doubt"] and lead.get("birth") is None:
        return skip("wd_birth_in_doubt")  # backfill_dates' rule, lifted when the lead agrees

    # ── death: the row's own end wins; every source must agree with it ──────
    row_end = e.get("row_end_year")
    death = None
    if row_end is not None:
        if not agrees(row_end, wdd):
            return skip("row_end_disagrees_with_wikidata")
        death = {"year": row_end, "conf": None, "src": "row"}
    elif d_wd:
        death = {"year": d_wd["year"], "conf": d_wd["conf"],
                 "src": "P570" + ("-bounds" if d_wd["how"] == "bounds" else "")}
    if lead.get("death") is not None:
        if death and abs(lead["death"] - death["year"]) > TOL:
            return skip("death_sources_disagree")
        if not agrees(lead["death"], wdd):
            return skip("lead_death_outside_wikidata")
        if death is None:
            death = {"year": lead["death"], "conf": "low" if lead["d_why"] else "medium", "src": "enwiki"}
            lead_used = True
        elif death["src"] != "row" and refine(d_wd, lead["death"]):
            death = {"year": lead["death"], "conf": "low", "src": "enwiki+P570"}
            lead_used = True
    if death and death["src"].startswith("P570") and d_wd["doubt"] and lead.get("death") is None:
        return skip("wd_death_in_doubt")

    if birth is None and (death is None or death["src"] == "row"):
        if info["floruit"]:  # a floruit or reign is not a lifespan, and the spec has no place for one
            return skip("floruit_or_reign_only", action="list")
        return skip(f"no_birth:wd_{b_why}/lead_{lead.get('kind') or 'no_enwiki'}")
    plan = {"start": birth["year"] if birth else None, "end": death["year"] if death else None,
            "start_src": birth["src"] if birth else "", "end_src": death["src"] if death else ""}
    plan["start_date"] = str(plan["start"]) if birth else None
    plan["end_date"] = ((e.get("row_end_date") or str(row_end)) if death and death["src"] == "row"
                        else (str(plan["end"]) if death else None))
    plan["confidence"] = _min_conf(birth and birth["conf"], death and death["conf"],
                                   e.get("date_confidence") if death and death["src"] == "row" else None)
    if lead_used:  # the spec's enum has no Wikipedia value: dates read from article text are NLP tiers
        plan["method"] = "nlp_approximate" if plan["confidence"] == "low" else "nlp_direct"
    else:
        plan["method"] = "source_database"
    flags: list[str] = []

    # ── a lifespan, not a reign or an office ────────────────────────────────
    if birth is None:
        flags.append("end_only")
    elif death is None:
        if birth["year"] < ALIVE_BORN_AFTER:
            return skip("no_death_date", action="list" if info["floruit"] else "skip", **plan)
    else:
        if death["year"] < birth["year"]:
            return skip("end_before_start", **plan)
        if death["year"] - birth["year"] > MAX_LIFESPAN:
            return skip("lifespan_over_120", **plan)
        if death["year"] - birth["year"] < SHORT_LIFE:
            flags.append("short_life")
    if birth and birth["src"] == "enwiki":
        if birth["year"] in reign_starts(facts):
            return skip("birth_is_reign_start", **plan)
        fl_starts = {v["y"] for p in ("P1317", "P2031") for v in dates.get(p, []) if "y" in v}
        if birth["year"] in fl_starts:
            return skip("birth_is_floruit_start", **plan)
        if year_in_reign_context(extract, birth["year"]):
            flags.append("reign_context")
    if lead.get("flags"):
        flags += [f for f in lead["flags"] if f not in flags]

    # ── the person's own dated facts ────────────────────────────────────────
    earliest, latest = fact_bounds(facts)
    plan["earliest"] = f"{earliest[0]} {earliest[1]}" if earliest else ""
    plan["latest"] = f"{latest[0]} {latest[1]}" if latest else ""
    if birth and earliest and birth["year"] > earliest[0]:
        return skip("start_after_evidence", **plan)
    lo = plan["start"] if birth else plan["end"] - MAX_LIFESPAN
    hi = plan["end"] if death else plan["start"] + 100
    if facts and not any(_touches(f_lo, f_hi, lo, hi) for f_lo, f_hi, _ in facts):
        return skip("lifespan_misses_evidence", **plan)
    plan["flags"] = flags

    # ── a lead parse is used only once checked by hand: a clean '(1130–1167)'
    #    is a reign often enough (Bijjala II, Yasodaman II) ─────────────────
    if lead_used and hand != "ok":
        return skip("awaiting_hand_check", **plan)
    plan["action"] = "update" if e.get("range_id") else "insert"
    plan["reason"] = "end_only" if birth is None else ""
    plan["hand"] = hand or ""
    return {**info, **plan}


# ── DB ────────────────────────────────────────────────────────────────────────
def load_state(cur) -> list[dict]:
    """People with a QID and no range with a start year, plus their primary row."""
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
        WHERE e.entity_type = 'person' AND e.wikidata_id IS NOT NULL AND e.wikidata_id <> ''
          AND NOT EXISTS (SELECT 1 FROM entity_temporal_ranges x
                          WHERE x.entity_id = e.entity_id AND x.start_year IS NOT NULL)
        ORDER BY e.entity_id
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_exclusions(path: Path) -> set[str]:
    """Survivors and losers of the merge review (another agent merges them)."""
    out: set[str] = set()
    if path.exists():
        with path.open(newline="") as f:
            for row in csv.DictReader(f):
                out.update(x for x in (row.get("survivor_id"), row.get("loser_id")) if x)
    return out


def excluded_why(entity_id: str, merge_ids: set[str]) -> str | None:
    if entity_id in merge_ids:
        return "excluded:merge_review"
    if entity_id.startswith(USER_DECISION_PREFIXES):
        return "excluded:user_decision"
    return None


def apply_plan(cur, plans: list[tuple[dict, dict]], merge_ids: set[str]) -> Counter:
    """Write each planned row unless the entity changed since it was planned:
    its QID was re-pointed, it got a start year, or its primary row moved."""
    done: Counter = Counter()
    for e, p in plans:
        if excluded_why(e["entity_id"], merge_ids):
            done["excluded_at_apply"] += 1
            continue
        guard = ("EXISTS (SELECT 1 FROM entities WHERE entity_id = %(eid)s::uuid AND wikidata_id = %(qid)s) "
                 "AND NOT EXISTS (SELECT 1 FROM entity_temporal_ranges WHERE entity_id = %(eid)s::uuid "
                 "AND start_year IS NOT NULL)")
        args = {"eid": e["entity_id"], "qid": e["wikidata_id"], "sd": p["start_date"], "ed": p["end_date"],
                "conf": p["confidence"], "notes": p["notes"], "method": p["method"], "rid": p["range_id"],
                "dur": p["duration_type"], "old_end": e.get("row_end_date"), "old_notes": e.get("notes")}
        if p["action"] == "update":
            cur.execute(f"""
                UPDATE entity_temporal_ranges
                SET start_date = %(sd)s, end_date = %(ed)s, date_method = %(method)s,
                    date_confidence = %(conf)s, notes = %(notes)s, duration_type = %(dur)s,
                    updated_at = now()
                WHERE temporal_range_id = %(rid)s::uuid AND is_primary AND start_year IS NULL
                  AND end_date IS NOT DISTINCT FROM %(old_end)s::text
                  AND notes IS NOT DISTINCT FROM %(old_notes)s::text AND {guard}
            """, args)
        else:
            cur.execute(f"""
                INSERT INTO entity_temporal_ranges
                    (temporal_range_id, entity_id, range_type, start_date, end_date, duration_type,
                     date_method, date_confidence, is_primary, notes, created_at, updated_at)
                SELECT %(rid)s::uuid, %(eid)s::uuid, 'primary', %(sd)s::text, %(ed)s::text, %(dur)s::text,
                       %(method)s::text, %(conf)s::text, true, %(notes)s::text, now(), now()
                WHERE NOT EXISTS (SELECT 1 FROM entity_temporal_ranges
                                  WHERE entity_id = %(eid)s::uuid AND is_primary) AND {guard}
            """, args)
        done[p["action"] if cur.rowcount else "changed_since_plan"] += 1
        p["applied"] = bool(cur.rowcount)
    return done


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def write_rollback(path: Path, plans: list[tuple[dict, dict]]) -> None:
    """Guarded undo statements: inserted rows are deleted, updated rows get
    their old columns back; each is a no-op unless the row still carries this
    script's note."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(f"-- backfill_person_dates run {time_stamp()}: undo {len(plans)} planned rows\nBEGIN;\n")
        inserts = [p["range_id"] for _, p in plans if p["action"] == "insert"]
        for i in range(0, len(inserts), 500):
            ids = ", ".join(_lit(x) for x in inserts[i:i + 500])
            f.write(f"DELETE FROM entity_temporal_ranges WHERE notes LIKE '{NOTE}:%' "
                    f"AND temporal_range_id IN ({ids});\n")
        for e, p in plans:
            if p["action"] != "update":
                continue
            f.write("UPDATE entity_temporal_ranges SET "
                    f"start_date = NULL, end_date = {_lit(e['row_end_date'])}, "
                    f"date_method = {_lit(e['date_method'])}, date_confidence = {_lit(e['date_confidence'])}, "
                    f"notes = {_lit(e['notes'])}, duration_type = {_lit(e['duration_type'])}, "
                    f"updated_at = {_lit(e['updated_at'])} "
                    f"WHERE temporal_range_id = {_lit(p['range_id'])} AND notes LIKE '{NOTE}:%';\n")
        f.write("COMMIT;\n-- then rebuild their timelines: php artisan timeline:rebuild <entity_id> for each "
                "entity_id in applied.csv\n\n")


def rebuild_timelines(entity_ids: list[str]) -> None:
    """entity_timeline_entries falls back to the range for an entity with no
    geometry or dated relationships (observers do not fire on raw SQL)."""
    for i in range(0, len(entity_ids), 200):
        ids = ",".join(f"'{x}'" for x in entity_ids[i:i + 200] if re.fullmatch(r"[0-9a-f-]{36}", x))
        php = ("$a = app(App\\Actions\\Timeline\\ProjectEntityTimelineAction::class); $n = 0; "
               f"foreach ([{ids}] as $id) {{ $a->rebuildForEntity($id); $n++; }} "
               "echo \"rebuilt {$n} timelines\\n\";")
        subprocess.run([*COMPOSE, "exec", "-T", "app", "php", "artisan", "tinker", "--execute", php], check=True)


# ── CSV and report ────────────────────────────────────────────────────────────
CSV_COLS = ["entity_id", "name", "qid", "enwiki", "action", "reason", "start_year", "end_year", "start_date",
            "end_date", "confidence", "date_method", "start_src", "end_src", "flags", "hand_check",
            "lead_kind", "lead_clean", "lead_text", "wd_birth_P569", "wd_death_P570", "row_end",
            "floruit_or_reign", "earliest_fact", "latest_fact", "note"]


def csv_row(e: dict, p: dict, enwiki: str) -> list:
    return [e["entity_id"], e["name"], e["wikidata_id"], enwiki, p["action"], p.get("reason", ""),
            p.get("start"), p.get("end"), p.get("start_date"), p.get("end_date"), p.get("confidence"),
            p.get("method"), p.get("start_src", ""), p.get("end_src", ""), " ".join(p.get("flags", [])),
            p.get("hand", ""), p.get("lead_kind", ""), "y" if p.get("clean") else "", p.get("lead_text", ""),
            p.get("wd_birth", ""), p.get("wd_death", ""), p.get("row_end"), p.get("floruit", ""),
            p.get("earliest", ""), p.get("latest", ""), p.get("lead_note", "")]


def write_csv(path: Path, results: list[tuple[dict, dict, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for e, p, enwiki in results:
            w.writerow(csv_row(e, p, enwiki))


def finish_plan(e: dict, p: dict) -> dict:
    """Row id, note and duration of a planned write."""
    p["range_id"] = e["range_id"] or str(uuid.uuid4())
    note = f"{NOTE}:{p['start_src'] or '-'}" + (f",{p['end_src']}" if p["end_src"] else "")
    p["notes"] = note if not e.get("notes") else f"{note} | {e['notes']}"
    p["duration_type"] = "period" if p["start_date"] and p["end_date"] else e.get("duration_type")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write rows (default: dry run)")
    ap.add_argument("--no-timelines", action="store_true", help="skip the timeline rebuild after --apply")
    ap.add_argument("--offline", action="store_true", help="use the caches only")
    ap.add_argument("--cache", type=Path, default=_REPO_ROOT / "output" / "audit" / "cache")
    ap.add_argument("--out", type=Path,
                    default=_REPO_ROOT / "output" / "audit" / f"person-dates-{date.today():%Y%m%d}")
    args = ap.parse_args()

    conn = psycopg.connect(DSN)
    cur = conn.cursor()
    rows = load_state(cur)
    merge_ids = load_exclusions(MERGE_VERDICTS)
    print(f"{len(rows)} people with a QID and no start year")

    client = PoliteClient(args.cache, max_rps=1.0, workers=1, offline=args.offline)
    qids = sorted({r["wikidata_id"] for r in rows if QID_RE.match(r["wikidata_id"])})
    claims = fetch_claims(client, qids)
    recs = {q: resolve(claims, q)[1] for q in qids}
    titles = {q: (r or {}).get("enwiki") for q, r in recs.items()}
    intros = fetch_intros(client, [t for t in titles.values() if t])
    facts = load_facts(cur, rows)

    results: list[tuple[dict, dict, str]] = []
    for e in rows:
        qid = e["wikidata_id"]
        title = titles.get(qid) or ""
        extract = (intros.get(title) or {}).get("extract", "") if title else ""
        lead = parse_lead(extract) if extract else None
        p = plan_person(e, recs.get(qid), lead, extract, facts.get(e["entity_id"], []),
                        excluded_why(e["entity_id"], merge_ids), HAND_CHECK.get(qid))
        if p["action"] in ("insert", "update"):
            finish_plan(e, p)
        results.append((e, p, title))
    write_csv(args.out / "planned.csv", results)
    planned = [(e, p) for e, p, _ in results if p["action"] in ("insert", "update")]

    print("\n" + "=" * 72)
    print("PERSON DATE BACKFILL" + ("  (APPLYING)" if args.apply else "  (DRY RUN)"))
    print("=" * 72)
    dated = sum(1 for _, p in planned if p["start"] is not None)
    print(f"Rows to write: {len(planned)} / {len(rows)}  ({dated} get a start year, "
          f"{len(planned) - dated} only an end)   plan: {args.out / 'planned.csv'}")
    for label, key in (("by action", "action"), ("by confidence", "confidence"), ("by method", "method"),
                       ("by start source", "start_src")):
        print(f"  {label}: " + ", ".join(f"{k} {n}" for k, n in Counter(p[key] for _, p in planned).most_common()))
    print("Not written:")
    for reason, n in Counter(p["reason"].split(":")[0] + (":" + p["reason"].split(":")[1].split("/")[0]
                                                          if p["reason"].startswith("no_birth") else "")
                             for _, p, _ in results if p["action"] in ("skip", "list")).most_common():
        print(f"   {reason:40s} {n}")

    if args.apply and planned:
        stamp = f"{datetime.now():%H%M%S}"
        dump = args.out / f"pre-apply-{stamp}.dump"
        subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_dump", "-U", "history-mapped", "-Fc",
                        "-t", "entity_temporal_ranges", "-t", "entity_timeline_entries", "history-mapped"],
                       stdout=dump.open("wb"), check=True)
        write_rollback(args.out / "rollback.sql", planned)
        print(f"\nBackup {dump}; applying in one transaction (undo: {args.out / 'rollback.sql'})")
        try:
            counts = apply_plan(cur, planned, merge_ids)
            conn.commit()
            print("  committed: " + ", ".join(f"{k} {n}" for k, n in counts.items()))
        except Exception:
            conn.rollback()
            print("  ROLLED BACK on error.")
            raise
        applied = [(e, p) for e, p in planned if p.get("applied")]
        path = args.out / "applied.csv"
        new = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(CSV_COLS + ["temporal_range_id", "applied_at"])
            for e, p in applied:
                w.writerow(csv_row(e, p, titles.get(e["wikidata_id"]) or "") + [p["range_id"], time_stamp()])
        if applied and not args.no_timelines:
            print(f"Rebuilding {len(applied)} timelines…")
            rebuild_timelines([e["entity_id"] for e, _ in applied])
    elif not args.apply:
        print("\nDry run: re-run with --apply to write.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
