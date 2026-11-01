"""C6: text consistency (report only).

* text_era   — the summary/description names years and none of them falls
               within the row's dates ± the C2 tolerance (dated types only);
* text_type  — the summary's leading descriptor names another kind of thing
               ('City in …' on a battle row, 'German conductor …' on a polity);
* dup_text   — the summary is identical to another row's.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from pipeline.audit.dates import DATED_TYPES, row_range, text_years, tolerance

LEXICON: dict[str, set[str]] = {
    "person": set("""king queen emperor empress general commander admiral philosopher poet writer author historian
        scholar scientist mathematician astronomer physician conductor composer painter sculptor architect pharaoh
        sultan caliph shah khan pope bishop archbishop saint monk nun priest prophet statesman politician president
        minister consul senator tyrant satrap prince princess duke duchess earl baron nobleman noblewoman merchant
        explorer navigator inventor engineer monarch chieftain warlord soldier officer jurist theologian mystic
        diplomat ambassador regent vizier courtier usurper dictator emir raja rajah maharaja shogun daimyo governor
        viceroy legate tribune praetor missionary reformer geographer alchemist physicist chemist economist novelist
        playwright dramatist musician singer actor actress journalist banker industrialist aviator astronaut
        mercenary pretender lawyer abbot patriarch rabbi imam guru disciple apostle concubine consort wife husband
        son daughter brother sister mother father grandson granddaughter nephew niece heir queen-consort
        crown-prince co-emperor co-regent ruler""".split()),
    "battle": set("battle siege skirmish engagement ambush sack".split()),
    "war": set("war wars conflict crusade invasion conquest uprising revolt rebellion revolution coup mutiny".split()),
    "treaty": set("treaty pact truce armistice accord".split()),
    "settlement": set("city town village port capital settlement metropolis oasis harbour harbor hamlet".split()),
    "polity": set("""empire kingdom sultanate caliphate khanate principality duchy republic emirate confederation
        chiefdom polity realm""".split()),
    "structure": set("""temple palace castle fortress fort citadel bridge canal aqueduct pyramid tomb mausoleum church
        cathedral basilica mosque monastery abbey shrine stupa tower lighthouse amphitheatre amphitheater
        stadium""".split()),
    "work": set("book poem epic novel treatise painting sculpture opera symphony manuscript film".split()),
}
_ALL = {w: k for k, ws in LEXICON.items() for w in ws}
_STOP = re.compile(r"\b(who|which|that|where|whose|whom|in|of|on|at|from|during|between|by|for|under|near|to|with|"
                   r"against|founded|built|led|ruled|fought|known|and|after|before|was|is)\b|[,.;:(]", re.I)

# kind of the leading descriptor -> row types it contradicts
CONFLICTS: dict[str, set[str]] = {
    "person": {"city", "political_entity", "event_battle", "event_war", "event_treaty", "event_rebellion",
               "infrastructure_monument", "cultural_work", "language", "technology", "trade_route",
               "natural_resource", "religious_text", "legal_code", "educational_institution"},
    "battle": {"person", "city", "political_entity", "dynasty", "infrastructure_monument", "cultural_work",
               "language", "technology", "religious_text", "natural_resource"},
    "war": {"person", "city", "dynasty", "infrastructure_monument", "cultural_work", "language", "technology",
            "religious_text", "natural_resource"},
    "treaty": {"person", "city", "infrastructure_monument", "event_battle", "dynasty", "language"},
    "settlement": {"person", "event_battle", "event_war", "event_treaty", "event_rebellion", "cultural_work",
                   "language", "technology", "dynasty", "religious_text", "legal_code"},
    "polity": {"person", "event_battle", "event_treaty", "cultural_work", "language", "technology",
               "infrastructure_monument", "religious_text"},
    "structure": {"person", "event_battle", "event_war", "political_entity", "dynasty", "language"},
    "work": {"person", "city", "event_battle", "event_war", "political_entity", "dynasty"},
}


def head_kind(summary: str) -> tuple[str | None, str]:
    """(kind, head word) of a summary's leading descriptor, e.g.
    'Naval battle in 480 BCE where…' -> ('battle', 'battle')."""
    s = (summary or "").strip()
    s = re.sub(r"^(an?|the)\s+", "", s, flags=re.I)
    rel = re.match(r"^((?:[^\s,.;]+\s+){0,7}?)([A-Za-z][A-Za-z\-]*)\s+(who|whose|which|that)\b", s)
    if rel:  # 'Church of the East monk who …' -> monk
        words = [rel.group(2)]
    else:
        m = _STOP.search(s)
        head = s[:m.start()] if m else s[:60]
        words = re.findall(r"[A-Za-z][A-Za-z\-]*", head)
        if len(words) > 4:  # a sentence, not a descriptor ('Sucre defeated Viceroy …')
            return None, ""
    if not words:
        return None, ""
    last = words[-1].lower()
    for w in (last, last.rstrip("s")):
        if w in _ALL:
            return _ALL[w], w
    return None, last


def text_flags(rows) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        span = row_range(r.type, r.start, r.end)
        if r.type in DATED_TYPES and span:
            years = text_years(r.text)
            tol = tolerance(r.type) or 25
            if years:
                lo, hi = span
                dist = [0 if lo - tol <= y <= hi + tol else min(abs(y - lo), abs(y - hi)) for y in years]
                if min(dist) > 0:
                    out.append({"entity_id": r.id, "name": r.name, "entity_type": r.type, "qid": r.qid,
                                "check": "text_era", "row_span": r.span, "text_years": sorted(set(years))[:8],
                                "detail": f"no year in the text is within {tol}y of the row's dates; nearest {min(dist)}y off",
                                "severity": "high" if min(dist) > 100 else "medium",
                                "summary": r.summary[:200]})
        kind, word = head_kind(r.summary)
        if kind and r.type in CONFLICTS.get(kind, set()):
            out.append({"entity_id": r.id, "name": r.name, "entity_type": r.type, "qid": r.qid,
                        "check": "text_type", "row_span": r.span, "text_years": [],
                        "detail": f"summary describes a {kind} ('{word}')", "severity": "medium",
                        "summary": r.summary[:200]})
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        key = " ".join(r.summary.lower().split())
        if len(key) >= 40:
            groups[key].append(r)
    for key, members in groups.items():
        if len(members) < 2:
            continue
        for r in members:
            others = [m for m in members if m.id != r.id]
            out.append({"entity_id": r.id, "name": r.name, "entity_type": r.type, "qid": r.qid,
                        "check": "dup_text", "row_span": r.span, "text_years": [],
                        "detail": "same summary as " + "; ".join(f"{o.name} ({o.id[:8]})" for o in others[:4]),
                        "severity": "medium", "summary": r.summary[:200]})
    return out
