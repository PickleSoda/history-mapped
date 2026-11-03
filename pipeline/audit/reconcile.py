"""Reconcile: find the Wikidata item of a row that has no QID (``--only reconcile``).

This is C3 run over QID-less rows, and stricter than C3 for wrong rows. A QID
brings an image, a map point and dates; a wrong one corrupts all three, so a
missing QID is much cheaper than a wrong one. A candidate is accepted only
when it is the one item that passes every check its type requires and no
other candidate is a plausible rival.

Candidates: ``wbsearchentities`` on the row's name (top 20) plus the item
whose English Wikipedia article has exactly that title.

Checks (each candidate):

* name  - the row's name equals the item's label, an alias or its enwiki title
          (case, diacritics and punctuation aside). A trailing parenthetical on
          the Wikidata side ('Siege of Rhodes (1522)', 'Gaur (city)') is dropped;
          a year in it must fit the row.
* class - the P31 kinds fit the type (``classes.classify`` ok; not a concept, a
          film, an article or fiction; a city is a settlement and not a district;
          a battle row is a battle, siege or campaign).
* dates - ``own``: the row's dates agree with the item's within the audit's
          tolerances (people ±5, events ±2, polities ±25, other types ±25 on the
          start), from year- or decade-precise values. ``anchors``: the row has
          no dates, but the years of its contemporaneous relations, its related
          one-off events and its text all fall inside the item's life or span.
          ``conflict``: the dates disagree (the item is out, whatever else fits).
* place - a location, admin area or country of the item, or a place named in
          its description, is named in the row's text or is a related row.
* war   - the item is part of (P361/P607) a war that a related row carries, or
          that war's name is in the row's text or a related row's name.
* link  - one of the item's links (``wd.LINK_PROPS`` but continent, country and
          period) is the QID of a related row, or a related row's item links to it.

Requirements (``requirement``):

* person: dates own or anchors. A one-word name ('Draco') also needs the enwiki
  article of exactly that name, or a matching precise birth and death; a match
  through an alias alone also needs place or link.
* event_battle: dates own, and place, war or link.
* other events: dates own.
* city, infrastructure_monument, extraction_infra, educational_institution,
  trade_route: place below the country level or a link (a country alone only
  for the enwiki article of exactly that name); an alias alone needs a link.
* places and battles: an item more than FAR_KM from every related place (a
  related city, monument or battle, by DB point or Wikidata coordinates) is
  out, and no rival. This also catches Wikidata's own slips that a link follows.
* everything else (polities, dynasties, works, codes, movements, ...): a link,
  or dates own/anchors (archaeological cultures: century precision will do)
  together with place or the enwiki article of exactly that name.

Rivals: another candidate with the same name and a fitting class whose dates
don't rule it out. An undated namesake is a rival. For a place whose winner has
a link, only a namesake that also has place or link evidence is. One rival is
enough to give up. A place named like the row itself never counts as place
evidence.

Guards after the match (``settle``): a QID already on another row makes the
row a duplicate candidate, not a set_qid; so does a QID that two QID-less rows
both resolve to. A QID the row once rejected (``_rejected_wikidata_id``) never
wins, but it is scored and blocks as a rival when it still fits; the accepted
QID must pass C2 (``qid.check_row``) clean.
"""
from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from typing import Any, Callable, Iterable

from pipeline.agent.tools.disambiguation import CONTEMPORANEOUS_RELATION_TYPES, _name_tokens, names_equal
from pipeline.audit import classes as C
from pipeline.audit.dates import (DATED_TYPES, DEEP_ANTIQUITY, DEEP_ANTIQUITY_EXTRA, EVENT_TYPES, PRECISION_SLACK,
                                  compare_dates, text_years, tolerance, wd_bounds)
from pipeline.audit.places import place_words
from pipeline.audit.qid import check_row, wd_names

SEARCH_LIMIT = 20
PLACE_TYPES = {"city", "infrastructure_monument", "extraction_infra", "educational_institution", "trade_route"}
POLITY_LIKE = {"political_entity", "dynasty", "military_unit", "diplomatic_relationship"}
PLACE_PROPS = ("P276", "P131", "P706", "P17")  # most specific first; P17 (country) is weakest
# related rows whose location is a point: a candidate place or battle far from all of them is another one
POINT_TYPES = {"city", "infrastructure_monument", "extraction_infra", "educational_institution", "event_battle"}
FAR_KM = 500
WAR_PROPS = ("P361", "P607")
WEAK_LINK_PROPS = {"P30", "P17", "P2348"}  # continent, country, period: too broad to identify anything
LOOSE_TOL = 25        # types without a date tolerance (works, buildings, codes): the start ±25
ANCHOR_TOL = 2        # a relation year may sit this far outside a life or span
# kinds a candidate must reach, narrower than classes.TYPE_RULES for these types
STRICT_KINDS: dict[str, set[str]] = {
    "person": C.HUMAN | C.PERSONLIKE,
    "event_battle": C.BATTLE,
    "city": C.SETTLEMENT | {"Q839954", "Q133442"},  # settlement, archaeological site, city-state
}

FIELDS = ["entity_id", "name", "entity_type", "status", "no_wikidata_match", "row_start", "row_end", "anchors",
          "outcome", "why", "qid", "wd_label", "wd_description", "wd_enwiki", "wd_start", "wd_end", "name_match",
          "date_check", "place_check", "war_check", "link_check", "c2", "rivals", "candidates", "action",
          "held_by", "created_by"]


@dataclasses.dataclass
class Context:
    """What a row's neighbourhood says about it."""
    anchors: list[int]
    related_qids: set[str]
    hay: list[str]                      # normalised token strings: the row's text, related rows' names
    reverse: set[str] = dataclasses.field(default_factory=set)  # QIDs that related rows' items link to
    related_types: dict[str, str] = dataclasses.field(default_factory=dict)  # related QID -> its row's type
    points: list[tuple[float, float]] = dataclasses.field(default_factory=list)  # (lat, lon) of related places
    point_qids: list[str] = dataclasses.field(default_factory=list)  # related places with no DB point

    def mentions(self, phrase: str) -> bool:
        toks = _name_tokens(phrase)
        if not toks:
            return False
        needle = f" {' '.join(toks)} "
        return any(needle in h for h in self.hay)


def _norm(text: str) -> str:
    return f" {' '.join(_name_tokens(text))} "


def build_contexts(targets: Iterable[Any], rows: dict[str, Any], rels: list[dict[str, Any]]) -> dict[str, Context]:
    """Anchors, related QIDs and the text haystack of each target row."""
    by_row: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for rel in rels:
        by_row[rel["source"]].append((rel, rel["target"]))
        by_row[rel["target"]].append((rel, rel["source"]))
    out = {}
    for r in targets:
        anchors: list[int] = []
        qids: set[str] = set()
        hay = [_norm(r.text)] if r.text else []
        points: list[tuple[float, float]] = []
        point_qids: list[str] = []
        types: dict[str, str] = {}
        for rel, other in by_row.get(r.id, []):
            o = rows.get(other)
            if o is None or o.id == r.id:
                continue
            if o.qid:
                qids.add(o.qid)
                types[o.qid] = o.type
            if o.type in POINT_TYPES:
                if o.point:
                    points.append((o.point[1], o.point[0]))  # Row.point is (lon, lat)
                elif o.qid:
                    point_qids.append(o.qid)
            hay.extend(_norm(n) for n in o.names[:3])
            if rel["type"] in CONTEMPORANEOUS_RELATION_TYPES:
                anchors += [y for y in (rel["start"], rel["end"]) if y is not None]
                # a one-off event the row took part in (a battle, a treaty); not a war's whole span
                if o.type in EVENT_TYPES and o.span and o.span[1] - o.span[0] <= 5:
                    anchors += list(o.span)
        if r.start is None and r.end is None:
            anchors += text_years(r.text)
        out[r.id] = Context(sorted(set(anchors)), qids, hay, related_types=types, points=points,
                            point_qids=point_qids)
    return out


def km_between(a, b) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    import math

    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def geo_far(rec: dict[str, Any], ctx: Context) -> float | None:
    """km to the nearest related place when every one of them is over FAR_KM
    away, else None. Catches Wikidata's own slips that a link would follow: the
    Wari Empire's capital set to Huari village in Ancash (530 km from Wari),
    the Siege of Alamut located at a quarter of Bozdoğan in Turkey."""
    c = rec.get("coord")
    if not c or not ctx.points:
        return None
    d = min(km_between(tuple(c), p) for p in ctx.points)
    return d if d > FAR_KM else None


# ── name ────────────────────────────────────────────────────────────────────
_QUAL = re.compile(r"^(.*\S)\s*\(([^()]*)\)\s*$")


def split_qualifier(name: str) -> tuple[str, str]:
    """'Siege of Rhodes (1522)' -> ('Siege of Rhodes', '1522')."""
    m = _QUAL.match(name or "")
    return (m.group(1), m.group(2).strip()) if m else (name or "", "")


def qualifier_years(qual: str) -> list[int]:
    q = qual.strip()
    m = re.fullmatch(r"(?:c\.\s*)?(\d{1,4})(?:\s*[–-]\s*(\d{1,4}))?\s*(BCE|BC|CE|AD)?", q, re.I)
    if m:
        sign = -1 if (m.group(3) or "").upper().startswith("B") else 1
        return [sign * int(g) for g in m.groups()[:2] if g]
    return text_years(q)


def name_match(row_name: str, rec: dict[str, Any]) -> tuple[str, str, str] | None:
    """(how, item qualifier, row qualifier) when the row's name is one of the
    item's names exactly, else None. ``how`` is 'label' | 'enwiki' | 'alias'; a
    qualifier is a parenthetical dropped to make the names equal ('' when the
    names are equal as they stand)."""
    full = row_name or ""
    base, rq = split_qualifier(full)
    for kind, names in (("label", [rec.get("label")]), ("enwiki", [rec.get("enwiki")]),
                        ("alias", rec.get("aliases") or [])):
        for n in names:
            if n and names_equal(full, n):
                return kind, "", ""
    for kind, names in (("label", [rec.get("label")]), ("enwiki", [rec.get("enwiki")]),
                        ("alias", rec.get("aliases") or [])):
        for n in names:
            if not n:
                continue
            if names_equal(base, n):
                return kind, "", rq
            nb, nq = split_qualifier(n)
            if nq and names_equal(base, nb):
                return kind, nq, rq
    return None


# generic words a qualifier may consist of for a row of the type ('Gaur (city)')
TYPE_WORDS: dict[str, set[str]] = {
    "city": {"city", "town", "village", "settlement", "ancient", "port", "capital", "modern"},
    "person": {"king", "queen", "emperor", "empress", "sultan", "pharaoh", "prince", "princess", "ruler",
               "general", "caliph", "khan", "pope", "bishop", "saint", "monarch", "chief", "consort"},
    "dynasty": {"dynasty", "family", "house", "clan"},
    "political_entity": {"state", "kingdom", "polity", "empire", "country", "people", "tribe", "ancient"},
    "event_battle": {"battle", "siege"},
}
_QUAL_STOP = {"of", "the", "and", "in", "on", "at", "a", "an", "de", "von", "van", "al", "el"}


def _qual_words(qual: str) -> set[str]:
    return {t for t in _name_tokens(qual) if t not in _QUAL_STOP and not t.isdigit()}


def qualifier_ok(qual: str, row, ctx: "Context", other_text: str = "", *, years_needed: bool = True) -> bool:
    """A dropped qualifier must not say something the row doesn't.

    A year in it must fit the row ('Siege of Rhodes (1522)'); words must be
    generic for the row's type ('Gaur (city)') or named in ``other_text`` (for
    an item qualifier: the row's text and related names; for a row qualifier:
    the item's label, aliases and description). 'Harfleur (Samian Ware
    Discovery Site)' fails for a town row."""
    if not qual:
        return True
    years = qualifier_years(qual)
    if years:
        span = row.span or ((min(ctx.anchors), max(ctx.anchors)) if ctx.anchors else None)
        if span is None:
            return not years_needed
        tol = tolerance(row.type) or LOOSE_TOL
        return any(span[0] - tol <= y <= span[1] + tol for y in years)
    rest = _qual_words(qual) - TYPE_WORDS.get(row.type, set())
    if not rest:
        return True
    hays = [_norm(other_text)] if other_text else ctx.hay
    return all(any(f" {w} " in h for h in hays) for w in rest)


# ── class ───────────────────────────────────────────────────────────────────
def class_fits(row_type: str, rec: dict[str, Any], closure: dict[str, set[str]]) -> bool:
    p31 = rec.get("p31") or []
    if not p31 or C.junk_label(p31):
        return False
    if C.classify(row_type, p31, closure) != "ok":
        return False
    if C.is_generic_class(row_type, rec) or C.never_historical(row_type, p31, closure):
        return False
    if C.admin_area_for_city(row_type, p31, closure):
        return False
    strict = STRICT_KINDS.get(row_type)
    return not strict or bool(C.kinds_of(p31, closure) & strict)


# ── dates ───────────────────────────────────────────────────────────────────
def _allow(tol: int, bound: tuple[int, int]) -> int:
    allow = tol + PRECISION_SLACK.get(bound[1], 0)
    return allow + (DEEP_ANTIQUITY_EXTRA if bound[0] < DEEP_ANTIQUITY else 0)


def _inside(years: list[int], start, end, tol: int) -> bool:
    lo = start[0] - _allow(tol, start) if start else None
    hi = end[0] + _allow(tol, end) if end else None
    return all((lo is None or y >= lo) and (hi is None or y <= hi) for y in years)


def date_signal(row, rec: dict[str, Any], anchors: list[int]) -> tuple[str, str]:
    """('own' | 'coarse' | 'anchors' | 'unknown' | 'none' | 'conflict', detail)."""
    dates = rec.get("dates") or {}
    start, end = wd_bounds(row.type, dates)
    wd = f"{start[0] if start else ''}..{end[0] if end else ''}"
    if row.start is not None or row.end is not None:
        mine = f"{row.start if row.start is not None else ''}..{row.end if row.end is not None else ''}"
        if row.type in DATED_TYPES:
            cmp = compare_dates(row.type, row.start, row.end, dates)
            if cmp["verdict"] == "ok":
                used = [b for y, b in ((row.start, start), (row.end, end)) if y is not None and b]
                precise = bool(used) and all(b[1] >= 8 for b in used)
                return ("own" if precise else "coarse"), f"{mine} ~ {wd}"
            if cmp["verdict"] == "unknown":
                return "unknown", f"{mine} vs item {wd or 'undated'}"
            if row.type == "person" and start and end and start[1] >= 8 and end[1] >= 8 and _inside(
                    [y for y in (row.start, row.end) if y is not None], start, end, ANCHOR_TOL):
                return "anchors", f"row span {mine} inside the life {wd} (reign dates?)"
            return "conflict", f"{mine} vs {wd} ({cmp['verdict']})"
        used = [(y, b) for y, b in ((row.start, start), (row.end, end)) if y is not None and b]
        if not used:
            return "unknown", f"{mine} vs item {wd or 'undated'}"
        if all(abs(y - b[0]) <= _allow(LOOSE_TOL, b) for y, b in used):
            return ("own" if all(b[1] >= 8 for _, b in used) else "coarse"), f"{mine} ~ {wd}"
        return "conflict", f"{mine} vs {wd}"
    if not anchors:
        return "none", ""
    lo_hi = f"anchors {anchors[0]}..{anchors[-1]} ({len(anchors)})"
    if row.type == "person":
        if not (start and end) or start[1] < 8 or end[1] < 8:
            return "unknown", f"{lo_hi}; item lacks a precise birth and death"
        ok = _inside(anchors, start, end, ANCHOR_TOL)
    else:
        if not start or start[1] < 8 or (end and end[1] < 8):
            return "unknown", f"{lo_hi}; item lacks precise dates"
        ok = _inside(anchors, start, end, tolerance(row.type) or LOOSE_TOL)
    return ("anchors" if ok else "conflict"), f"{lo_hi} vs {wd}"


# ── place, war, link ────────────────────────────────────────────────────────
def place_signal(rec: dict[str, Any], ctx: Context, names_of: Callable[[str], list[str]],
                 own_name: str = "") -> str:
    """Where the item is, as the row's text or related rows say. A place named
    like the row itself confirms nothing: 'Salo', a village in Indonesia whose
    district is also 'Salo', against a row about Salò whose related row is the
    'Republic of Salo'."""
    links = rec.get("links") or {}
    own = set(_name_tokens(own_name))
    countries = {t for q in links.get("P17", []) for n in names_of(q) for t in _name_tokens(n)}
    found = ""
    for p in PLACE_PROPS:
        vals = links.get(p, [])
        hit = sorted(set(vals) & ctx.related_qids)
        if hit:
            found = f"related:{hit[0]}"
        else:
            found = next((f"text:{n}" for q in vals for n in names_of(q)
                          if len(n) >= 4 and not names_equal(n, own_name) and ctx.mentions(n)), "")
        if found:
            return ("country:" if p == "P17" else "") + found
        if p == "P706":  # before the country: the places the description names
            words = sorted(place_words(rec.get("description", "")) - own)
            for w in sorted(words, key=lambda w: w in countries):
                if ctx.mentions(w):
                    return ("country:" if w in countries else "") + f"description:{w}"
    return ""


def war_signal(rec: dict[str, Any], ctx: Context, names_of: Callable[[str], list[str]]) -> str:
    links = rec.get("links") or {}
    vals = [q for p in WAR_PROPS for q in links.get(p, [])]
    hit = sorted(set(vals) & ctx.related_qids)
    if hit:
        return f"related:{hit[0]}"
    for q in vals:
        for n in names_of(q):
            if len(_name_tokens(n)) >= 2 and ctx.mentions(n):
                return f"text:{n}"
    return ""


def link_signal(qid: str, rec: dict[str, Any], ctx: Context) -> str:
    """A link that identifies: one of the item's links is a related row's QID.
    Located-in links (P276/P131/P706) count only to a point-like related row
    (a city, a monument, a battle); located in Scotland is place, not identity
    ('Lothian' the 1018 region took the Lothian health board that way)."""
    for prop, vals in sorted((rec.get("links") or {}).items()):
        if prop in WEAK_LINK_PROPS:
            continue
        hit = sorted(q for q in set(vals) & ctx.related_qids
                     if prop not in PLACE_PROPS or ctx.related_types.get(q) in POINT_TYPES)
        if hit:
            return f"{prop}:{hit[0]}"
    return "reverse" if qid in ctx.reverse else ""


def reverse_links(related: Iterable[str], client) -> set[str]:
    """QIDs that the items of ``related`` link to (strong properties only)."""
    out: set[str] = set()
    for q in related:
        _, rec = client.resolved(q)
        if rec and rec.get("status") == "ok":
            for prop, vals in (rec.get("links") or {}).items():
                if prop not in WEAK_LINK_PROPS:
                    out.update(vals)
    return out


# ── scoring ─────────────────────────────────────────────────────────────────
def requirement(row, *, dates: str, place: str, war: str, link: str, one_word: bool, primary: bool,
                both_dates: bool = False, alias_only: bool = False) -> str:
    """'' when the type's evidence requirement is met, else what is missing.

    ``primary``: the item's enwiki article has exactly the row's name.
    ``both_dates``: the row's start and end both matched the item's precise
    start and end (a birth and a death, not just one of them)."""
    t = row.type
    if dates == "conflict":
        return "dates disagree"
    if t == "person":
        if dates not in ("own", "anchors"):
            return f"person needs date agreement ({dates})"
        if one_word and not primary and not (dates == "own" and both_dates):
            # 'Theodore' (Heraclius' brother, 590-650) took Pope Theodore I on his death year alone
            return "one-word name: needs the enwiki article of that name or a matching birth and death"
        if alias_only and not (place or link):
            # dates within ±5 years can coincide: 'Charles Dawes' (1865-1951) vs a
            # photographer whose alias it is (1867-1947)
            return "matched only through an alias: needs place or link as well"
        return ""
    if t == "event_battle":
        if dates != "own":
            return f"battle needs its own dates to agree ({dates})"
        return "" if place or war or link else "battle needs place or war context"
    if t in EVENT_TYPES:
        return "" if dates == "own" else f"event needs its own dates to agree ({dates})"
    if t in PLACE_TYPES:
        if link or (place and not place.startswith("country:")) or (place and primary):
            return ""
        # a country alone: the Pony Express roller coaster at Knott's Berry Farm (USA)
        return "needs place agreement below the country, a link, or the enwiki article of that name"
    if link:
        return ""
    # polities, works, codes, movements, ...: dates alone are loose (±25), so they
    # need a second voice. 'Movement to Protect the Constitution' (Japan, 1912)
    # took China's 1917 movement on an alias and the loose date alone.
    fits = ("own", "coarse", "anchors") if t == "archaeological_culture" else ("own", "anchors")
    if dates not in fits:
        return f"needs date agreement or a link ({dates})"
    return "" if place or primary else "dates agree, but no place, link or enwiki article of that name"


def score(row, qid: str, rec: dict[str, Any], ctx: Context, closure, names_of) -> dict[str, Any]:
    nm = name_match(row.name, rec)
    item_text = " ".join([*wd_names(rec), rec.get("enwiki") or "", rec.get("description") or ""])
    if nm and not (qualifier_ok(nm[1], row, ctx) and qualifier_ok(nm[2], row, ctx, item_text or " ",
                                                                  years_needed=False)):
        nm = None
    klass = class_fits(row.type, rec, closure)
    dates, ddetail = date_signal(row, rec, ctx.anchors)
    place = place_signal(rec, ctx, names_of, split_qualifier(row.name)[0])
    war = war_signal(rec, ctx, names_of) if row.type in EVENT_TYPES else ""
    link = link_signal(qid, rec, ctx)
    base = split_qualifier(row.name)[0]
    primary = bool(rec.get("enwiki")) and names_equal(rec["enwiki"], base)
    b_start, b_end = wd_bounds(row.type, rec.get("dates") or {})
    both = (dates == "own" and row.start is not None and row.end is not None and bool(b_start) and bool(b_end)
            and b_start[1] >= 9 and b_end[1] >= 9 and (row.type != "person" or "P569" in (rec.get("dates") or {})))
    need = requirement(row, dates=dates, place=place, war=war, link=link,
                       one_word=len(_name_tokens(base)) == 1, primary=primary, both_dates=both,
                       alias_only=bool(nm) and nm[0] == "alias")
    if not need and nm and nm[0] == "alias" and row.type in PLACE_TYPES and not link:
        # an alias alone ('Tlalancaleca' on the modern municipal seat) plus a
        # place word in the text, or a country, is too little for a place
        # (a related admin area or location is a link: it is not P17)
        need = "place matched only through an alias, without a link"
    far = geo_far(rec, ctx) if row.type in POINT_TYPES else None
    if far is not None:
        need = f"{far:.0f} km from every related place"
    ok = bool(nm) and klass and not need
    rival = bool(nm) and klass and dates != "conflict" and far is None
    start, end = wd_bounds(row.type, rec.get("dates") or {})
    how = ""
    if nm:
        how = nm[0] + "".join(f"({q})" for q in nm[1:] if q)
    return {"qid": qid, "label": rec.get("label", ""), "description": rec.get("description", ""),
            "enwiki": rec.get("enwiki") or "", "name": how,
            "class": klass, "dates": dates, "date_detail": ddetail, "place": place, "war": war, "link": link,
            "need": need, "ok": ok, "rival": rival,
            "wd_start": start[0] if start else None, "wd_end": end[0] if end else None}


def _summary(s: dict[str, Any]) -> str:
    bits = [b for b in (s["name"] and f"name={s['name']}", s["class"] and "class", f"dates={s['dates']}",
                        s["place"] and "place", s["war"] and "war", s["link"] and "link") if b]
    return f"{s['qid']} {s['label']!r} {'+'.join(bits)}"


def decide(row, scored: list[dict[str, Any]]) -> dict[str, Any]:
    """The outcome for one row from its scored candidates."""
    winners = [s for s in scored if s["ok"]]
    rivals = [s for s in scored if s["rival"]]
    if row.type in PLACE_TYPES and len(winners) == 1 and winners[0]["link"]:
        # a graph link (the item's admin area or location is a related row, or
        # a related row's item points to it) outweighs a namesake with no
        # evidence; a place word in the text does not: Salò on Lake Garda had
        # none, and 'Salo' in Indonesia won on its district's name
        rivals = [s for s in rivals if s["place"] or s["link"] or s is winners[0]]
    scored = sorted(scored, key=lambda s: (s["ok"], s["rival"], bool(s["name"]), s["class"]), reverse=True)
    cands = [_summary(s) for s in scored[:5]]
    if len(winners) == 1 and [r["qid"] for r in rivals] == [winners[0]["qid"]]:
        return {"outcome": "accepted", "win": winners[0], "candidates": cands, "rivals": 0}
    if winners:
        return {"outcome": "ambiguous", "candidates": cands, "rivals": len(rivals),
                "why": f"{len(winners)} pass, {len(rivals)} plausible"}
    named = [s for s in scored if s["name"] and s["class"]]
    why = named[0]["need"] if named else ("no exact name + class match" if scored else "")
    return {"outcome": "none_pass" if scored else "no_candidates", "candidates": cands,
            "rivals": len(rivals), "why": why}


def c2_passes(c2: dict[str, Any], win: dict[str, Any]) -> bool:
    """The accepted QID must pass C2 clean. Two suspects are what reconcile
    already weighed: S8 (C2's name axis knows no enwiki titles: 'Henry the
    Proud' is the article of 'Henry X') when the match is the enwiki title,
    and S6 (dates outside tolerance) when the person's row dates are a reign
    inside the item's lifespan."""
    if c2["verdict"] == "ok":
        return True
    if c2["verdict"] != "suspect":
        return False
    rule = c2.get("rule", "")[:2]
    return ((rule == "S8" and win["name"].startswith("enwiki"))
            or (rule == "S6" and win["dates"] == "anchors" and "reign" in win["date_detail"]))


def eligible(row, ctx: Context) -> str:
    """'' when the row can be reconciled at all, else why not (saves a search)."""
    dated = row.start is not None or row.end is not None
    if row.type in EVENT_TYPES and not dated:
        return "event without dates"
    if row.type == "person" and not dated and not ctx.anchors:
        return "person without dates or dated relations"
    if not _name_tokens(row.name):
        return "empty name"
    return ""


def reconcile_rows(targets: list[Any], rows: dict[str, Any], rels: list[dict[str, Any]], client,
                   closure_fn: Callable[[Iterable[str]], dict[str, set[str]]], log=print) -> list[dict[str, Any]]:
    """Score every target row; return one outcome record per row (see FIELDS)."""
    ctxs = build_contexts(targets, rows, rels)
    todo = []
    out: list[dict[str, Any]] = []
    for r in targets:
        why = eligible(r, ctxs[r.id])
        if why:
            out.append(_record(r, ctxs[r.id], {"outcome": "skipped", "why": why, "candidates": [], "rivals": 0}))
        else:
            todo.append(r)
    names = sorted({split_qualifier(r.name)[0] for r in todo})
    log(f"reconcile: {len(todo)} rows to search ({len(targets) - len(todo)} skipped), {len(names)} names")
    client.by_titles(names, progress=True)
    client.search_many(names, limit=SEARCH_LIMIT)
    cands: dict[str, list[str]] = {}
    for r in todo:
        base = split_qualifier(r.name)[0]
        qs = [h["qid"] for h in client.search(base, limit=SEARCH_LIMIT)]
        if client.titles.get(base):
            qs.append(client.titles[base])
        reject = (r.attributes or {}).get("_rejected_wikidata_id")
        # the rejected QID is scored too: it never wins, but it is a rival
        cands[r.id] = [q for q in dict.fromkeys([*qs, reject]) if q]
    all_q = {q for qs in cands.values() for q in qs}
    log(f"reconcile: fetching {len(all_q)} candidate items")
    client.get_entities(all_q, progress=True, need_links=True)
    client.get_entities([rec["redirect_to"] for q in all_q
                         if (rec := client.entities.get(q, {})).get("status") == "redirect"], need_links=True)
    recs: dict[str, dict[str, Any]] = {}
    for q in all_q:
        fq, rec = client.resolved(q)
        if rec and rec.get("status") == "ok":
            recs[q] = rec
    closure = closure_fn([c for rec in recs.values() for c in rec.get("p31", [])])
    linked = {v for rec in recs.values() for p in PLACE_PROPS + WAR_PROPS for v in (rec.get("links") or {}).get(p, [])}
    related = {q for r in todo for q in ctxs[r.id].related_qids}
    log(f"reconcile: fetching {len(linked)} place/war items and {len(related)} related rows' items")
    client.get_entities(linked)
    client.get_entities(related, need_links=True)
    for r in todo:
        ctx = ctxs[r.id]
        for q in ctx.point_qids:
            _, rec = client.resolved(q)
            if rec and rec.get("coord"):
                ctx.points.append(tuple(rec["coord"]))

    def names_of(q: str) -> list[str]:
        _, rec = client.resolved(q)
        return wd_names(rec) if rec and rec.get("status") == "ok" else []

    for r in todo:
        ctx = ctxs[r.id]
        ctx.reverse = reverse_links(ctx.related_qids, client)
        scored, seen = [], set()
        reject = (r.attributes or {}).get("_rejected_wikidata_id")
        for q in cands[r.id]:
            fq, rec = client.resolved(q)
            if q not in recs or fq in seen:
                continue
            seen.add(fq)
            s = score(r, fq, rec, ctx, closure, names_of)
            if reject and (fq == reject or q == reject):
                # once rejected for this row, never set again; but when it still
                # fits, the row is too close to it for a namesake to win ('Charles
                # Dawes' lost Q184565 Charles G. Dawes, then matched a photographer)
                s.update(ok=False, need="rejected for this row (_rejected_wikidata_id)")
            scored.append(s)
        res = decide(r, scored)
        if res["outcome"] == "accepted":
            c2 = check_row(dataclasses.replace(r, qid=res["win"]["qid"]), client, closure)
            res["c2"] = c2["verdict"] + (f" {c2['rule']}" if c2["rule"] else "")
            if not c2_passes(c2, res["win"]):
                res["outcome"], res["why"] = "c2_rejected", res["c2"]
        out.append(_record(r, ctx, res))
    return out


def _record(r, ctx: Context, res: dict[str, Any]) -> dict[str, Any]:
    win = res.get("win") or {}
    flags = (r.attributes or {}).get("validation_flags") or []
    return {"entity_id": r.id, "name": r.name, "entity_type": r.type, "status": r.status,
            "no_wikidata_match": "no_wikidata_match" in flags, "row_start": r.start, "row_end": r.end,
            "anchors": f"{ctx.anchors[0]}..{ctx.anchors[-1]} ({len(ctx.anchors)})" if ctx.anchors else "",
            "outcome": res["outcome"], "why": res.get("why", ""), "qid": win.get("qid", ""),
            "wd_label": win.get("label", ""), "wd_description": win.get("description", ""),
            "wd_enwiki": win.get("enwiki", ""), "wd_start": win.get("wd_start"), "wd_end": win.get("wd_end"),
            "name_match": win.get("name", ""), "date_check": f"{win['dates']}: {win['date_detail']}" if win else "",
            "place_check": win.get("place", ""), "war_check": win.get("war", ""), "link_check": win.get("link", ""),
            "c2": res.get("c2", ""), "rivals": res.get("rivals", 0), "candidates": res.get("candidates", []),
            "action": "", "held_by": "", "created_by": r.created_by}


def settle(records: list[dict[str, Any]], rows: dict[str, Any]) -> None:
    """Set ``action`` on accepted records: ``set_qid``, or ``duplicate_of:<ids>``
    when the QID is already on another row or two QID-less rows resolve to it
    (no two rows ever end up with one QID)."""
    held: dict[str, list[str]] = defaultdict(list)
    for r in rows.values():
        if r.qid:
            held[r.qid].append(r.id)
    wanted: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if rec["outcome"] == "accepted":
            wanted[rec["qid"]].append(rec)
    for qid, group in wanted.items():
        for rec in group:
            holders = [h for h in held.get(qid, []) if h != rec["entity_id"]]
            others = [g["entity_id"] for g in group if g is not rec]
            if holders or others:
                rec["action"] = "duplicate_of:" + ",".join(holders + others)
                rec["held_by"] = ",".join(holders) if holders else "(contested: " + ",".join(others) + ")"
            else:
                rec["action"] = "set_qid"
