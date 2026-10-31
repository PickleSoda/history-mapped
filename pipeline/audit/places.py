"""Same-name places: a city row whose QID is a namesake elsewhere.

C2 cannot see these: the name is exact, the class fits and places carry no
dates to compare ('Boston' the Puritan colony capital on Q311975, Boston in
Lincolnshire). The signal is geographic: the row's text names where it is,
and the QID's description names somewhere else. A row is flagged when none
of the places in its QID's description appear in its text; a candidate is
proposed when exactly one other same-named place's description does. The
candidates are only proposals: about a third were wrong on review (an airport
or railway station of the right city, the modern town on an ancient site), so
the verified ones are applied as pins.
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.agent.tools.disambiguation import names_equal
from pipeline.audit import classes as C
from pipeline.audit.qid import wd_names

PLACE_ROW_TYPES = {"city"}
# words in descriptions that are not places
_STOP = {"the", "and", "of", "in", "on", "near", "former", "ancient", "city", "town", "village", "capital",
         "human", "settlement", "commune", "municipality", "county", "district", "province", "state", "region",
         "island", "port", "area", "largest", "seat", "department", "historic", "historical", "site", "river",
         "census", "place", "unincorporated", "community", "metropolitan", "borough", "parish", "civil", "hamlet",
         "rural", "urban", "administrative", "centre", "center", "north", "south", "east", "west", "northern",
         "southern", "eastern", "western", "central", "upper", "lower", "national", "heritage", "republic",
         "kingdom", "people's", "federal", "autonomous", "oblast", "raion", "governorate", "prefecture", "u.s.",
         "us", "usa", "uk", "united", "states", "location", "located", "situated", "archaeological", "ruins",
         "british", "english", "french", "spanish", "portuguese", "dutch", "german", "roman", "greek", "ottoman"}


def place_words(description: str) -> set[str]:
    """Capitalised words naming where a place is: 'town and port in
    Lincolnshire, England, UK' -> {'lincolnshire', 'england'}."""
    if not description:
        return set()
    m = re.search(r"\b(?:in|of|near|on)\b(.*)$", description)
    tail = m.group(1) if m else description
    words = re.findall(r"[A-ZÀ-Þ][\w'’-]+", tail)
    return {w.casefold() for w in words if len(w) >= 4 and w.casefold() not in _STOP}


def text_mentions(text: str, words: set[str]) -> bool:
    low = text.casefold()
    return any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in words)


def check_places(rows: dict[str, Any], client, closure_fn, held: dict[str, str]) -> list[dict[str, Any]]:
    """Flag place rows whose QID's location is not in their text; propose the
    one same-named place whose location is."""
    suspects = []
    for r in rows.values():
        if r.type not in PLACE_ROW_TYPES or not r.qid:
            continue
        _, rec = client.resolved(r.qid)
        if not rec or rec.get("status") != "ok":
            continue
        own = {t.casefold() for n in r.names for t in re.findall(r"[\w'’-]+", n)}
        words = place_words(rec.get("description", "")) - own  # 'village in Kimberley and ...'
        text = r.text
        if words and text and not text_mentions(text, words):
            suspects.append((r, rec, words))
    client.search_many([r.name for r, _, _ in suspects])
    hits = {r.id: [h["qid"] for h in client.search(r.name, limit=10) if h["qid"] != r.qid] for r, _, _ in suspects}
    client.get_entities({q for qs in hits.values() for q in qs})
    recs = {q: client.resolved(q)[1] for qs in hits.values() for q in qs}
    closure = closure_fn([c for rec in recs.values() if rec for c in rec.get("p31", [])])
    out = []
    for r, rec, words in suspects:
        own = {t.casefold() for n in r.names for t in re.findall(r"[\w'’-]+", n)}
        good = []
        for q in hits[r.id]:
            alt = recs.get(q)
            if not alt or alt.get("status") != "ok" or not alt.get("enwiki"):
                continue
            if not any(names_equal(n, w) for n in r.names for w in wd_names(alt)):
                continue
            if C.classify(r.type, alt.get("p31", []), closure) != "ok" or C.never_historical(
                    r.type, alt.get("p31", []), closure) or C.admin_area_for_city(r.type, alt.get("p31", []), closure):
                continue
            alt_words = place_words(alt.get("description", "")) - own
            if alt_words and text_mentions(r.text, alt_words):
                good.append((q, alt, alt_words))
        res = {"entity_id": r.id, "name": r.name, "entity_type": r.type, "qid": r.qid,
               "wd_description": rec.get("description", ""), "qid_places": sorted(words),
               "summary": r.summary[:200], "proposed_qid": "", "proposed_description": "", "held_by": "",
               "action": "flag"}
        if len(good) == 1:
            q, alt, alt_words = good[0]
            res.update(proposed_qid=q, proposed_description=alt.get("description", ""),
                       held_by=held.get(q, ""), action="pin_candidate" if not held.get(q) else "duplicate")
        elif good:
            res["proposed_description"] = "; ".join(f"{q} {a.get('description')}" for q, a, _ in good[:3])
            res["action"] = "ambiguous"
        out.append(res)
    return out
