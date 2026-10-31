"""C2 (QID identity check) and C3 (find the correct QID).

C2 compares each row with its QID on four axes and turns the signals into a
verdict:

* name  — ``candidate_name_ok`` over the row's name+aliases and the QID's
          label+aliases (compatible / exact search hit / near_miss / markers /
          unrelated);
* class — ``classes.classify`` (ok / unmatched / contradiction / unknown), plus
          ``generic`` when an individual-type row carries a class QID;
* dates — ``dates.compare_dates`` (ok / out_of_tolerance / conflict / sign);
* state — the QID is missing (deleted), a redirect, or a disambiguation/name item.

A QID is judged **wrong** (rules W1-W8 below) only when the row's own identity
— its name, type, dates and text — disagrees with it decisively. Everything
else that disagrees is a **suspect** flag for a human.
"""
from __future__ import annotations

from typing import Any

from pipeline.agent.tools.disambiguation import _is_inflection, _name_tokens, candidate_name_ok, names_conflict, names_equal
from pipeline.audit import classes as C
from pipeline.audit.dates import DATED_TYPES, compare_dates, text_years, tolerance, wd_bounds, years_fit

NAME_BAD = {"markers", "near_miss"}
# Years by which a row and its QID must miss each other for the dates alone to
# decide (two lifetimes 50+ years apart are two people). Polities excluded:
# their spans are fuzzy and one generic row serves many eras.
FAR_GAP = {"person": 50, "event_battle": 50, "event_war": 50, "event_treaty": 50, "event_rebellion": 50,
           "event_natural_disaster": 50, "event_legal_reform": 50, "military_unit": 150, "dynasty": 150,
           "diplomatic_relationship": 100}


def wd_names(rec: dict[str, Any]) -> list[str]:
    label = rec.get("label") or ""
    return [label, *[a for a in rec.get("aliases", []) if a != label]] if label else list(rec.get("aliases", []))


def inflected_equal(a: str, b: str) -> bool:
    """Same words up to plural/demonym inflection: 'Khokhars' ~ 'Khokhar',
    'Assyrians' ~ 'Assyrian' (the name guard calls these unrelated)."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or len(ta) != len(tb) or ta == tb:
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        short, long_ = (x, y) if len(x) <= len(y) else (y, x)
        if not (long_.startswith(short) and _is_inflection(short, long_[len(short):])):
            return False
    return True


def name_verdict(row_names: list[str], rec: dict[str, Any]) -> str:
    names = wd_names(rec)
    if not names:
        return "no_label"
    ok, why = candidate_name_ok(row_names, names)
    if ok:
        return "exact" if any(names_equal(n, w) for n in row_names for w in names) else "compatible"
    if any(inflected_equal(n, w) for n in row_names for w in names):
        return "inflected"  # same words up to a plural/demonym ending
    conflict = names_conflict(row_names[0], names[0])
    return conflict or why  # markers / near_miss / unrelated


def text_supports_row(row, rec: dict[str, Any]) -> bool | None:
    """Whether the row's text dates the row's era rather than the QID's.

    True when the text names years, some fit the row's span and none fits the
    QID's; False when some fit the QID's and none the row's; None otherwise."""
    years = text_years(row.text)
    tol = tolerance(row.type) or 25
    if not years or row.span is None:
        return None
    start, end = wd_bounds(row.type, rec.get("dates") or {})
    if not start and not end:
        return None
    wd_span = (min(x[0] for x in (start, end) if x), max(x[0] for x in (start, end) if x))
    fit_row = any(years_fit(years, row.span, tol))
    fit_wd = any(years_fit(years, wd_span, tol))
    if fit_row and not fit_wd:
        return True
    if fit_wd and not fit_row:
        return False
    return None


def check_row(row, client, closure: dict[str, set[str]]) -> dict[str, Any]:
    """C2 for one row with a QID. Returns the flag record (``verdict`` 'ok' when clean)."""
    out: dict[str, Any] = {
        "entity_id": row.id, "name": row.name, "entity_type": row.type, "qid": row.qid,
        "row_start": row.start, "row_end": row.end, "rels": row.rels, "status": row.status,
        "issues": [], "verdict": "ok", "rule": "", "resolved_qid": row.qid,
    }
    final, rec = client.resolved(row.qid)
    first = client.entities.get(row.qid) or {}
    if first.get("status") == "redirect":
        out["issues"].append(f"redirect->{final}")
        out["resolved_qid"] = final
    if rec is None or rec.get("status") == "missing":
        out.update(state="missing", verdict="wrong", rule="W1 deleted QID", severity="high")
        out["issues"].append("missing")
        return out
    out["wd_label"] = rec.get("label", "")
    out["wd_description"] = rec.get("description", "")
    out["wd_kinds"] = C.kind_label(C.kinds_of(rec.get("p31", []), closure))
    junk = C.junk_label(rec.get("p31", []))
    if junk:
        out.update(state=junk, verdict="wrong", rule=f"W2 QID is a {junk}", severity="high")
        out["issues"].append(junk.replace(" ", "_"))
        return out

    name = name_verdict(row.names, rec)
    klass = C.classify(row.type, rec.get("p31", []), closure)
    strength = C.contradiction_strength(row.type, rec.get("p31", []), closure)
    generic = C.is_generic_class(row.type, rec)
    generic_hard = C.generic_decides(row.type, row.name, rec)
    dates = compare_dates(row.type, row.start, row.end, rec.get("dates") or {})
    # read the QID's dates as its own kind (a human's birth/death, a battle's day)
    qkinds = C.kinds_of(rec.get("p31", []), closure)
    # (a type without a date tolerance - an idea, a technology - is read at ±25)
    as_kind = ("person" if "Q5" in (rec.get("p31") or []) else
               "event_battle" if qkinds & (C.BATTLE | C.WAR | C.REBELLION) else
               row.type if tolerance(row.type) is not None else "military_unit")
    own_dates = compare_dates(as_kind, row.start, row.end, rec.get("dates") or {})["verdict"]
    dated = row.start is not None or row.end is not None
    same_dates = own_dates == "ok" and dated
    long_exact = name == "exact" and len(_name_tokens(row.name)) >= 3 and own_dates in ("ok", "unknown")
    if strength == "decisive" and (
            (name == "exact" and (same_dates or long_exact
                                  or (row.type == "person" and C.org_kind(rec.get("p31", []), closure))))
            or (name == "compatible" and same_dates)
            or (name == "exact" and not C.absolute_contradiction(row.type, rec, row.name, closure))):
        # the same name and agreeing dates (or a distinctive name with no date
        # against it, or a group QID on a person row) make a mistyped row more
        # likely than a wrong QID: 'Montaperti', a city row dated 1260, carrying
        # the Battle of Montaperti; 'The Beatles' as an intellectual_movement
        strength = "soft"
    out.update(name_check=name, class_check=f"{klass}:{strength}" if strength else klass, generic=generic,
               date_check=dates["verdict"], wd_start=dates["wd_start"], wd_end=dates["wd_end"],
               date_off=dates["off"])
    name_ok = name in ("exact", "compatible", "inflected")
    if not name_ok:
        out["issues"].append(f"name:{name}")
    if klass in ("contradiction", "unmatched"):
        out["issues"].append(f"class:{klass}" + (f"({strength})" if strength else ""))
    if generic:
        out["issues"].append("generic_class")
    if dates["verdict"] in ("out_of_tolerance", "conflict", "sign"):
        out["issues"].append(f"dates:{dates['verdict']}")

    support = text_supports_row(row, rec) if dates["verdict"] == "conflict" else None
    out["text_supports_row"] = support
    date_bad = dates["verdict"] in ("out_of_tolerance", "conflict")
    # near_miss also catches transliterations (Muawiya/Muawiyah), and a reign
    # vs a lifespan is out of tolerance, so near_miss needs a hard second signal
    # a concept QID on a row named exactly like the concept, whose class fits,
    # is the row being that concept ('Caliphate' -> caliphate): not decisive
    # (a plural row name - 'Departments of France' - is itself a concept row)
    generic_hard = generic_hard and name != "inflected" and not same_dates and (
        klass in ("contradiction", "unmatched") or name != "exact")
    # polity dates are fuzzy (a generic 'Egypt' row; a modern state's inception)
    era_conflict = dates["verdict"] == "conflict" and row.type != "political_entity"
    hard = strength == "decisive" or era_conflict or generic_hard
    rule = ""
    if strength == "decisive":
        rule = f"W4 QID is a {out['wd_kinds']}, never a {row.type}"
    elif (name == "markers" and (hard or date_bad)) or (name == "near_miss" and hard):
        rule = f"W3 name {name} + " + ("concept QID" if generic_hard else f"dates {dates['verdict']}")
    elif dates["verdict"] == "conflict" and not name_ok:
        rule = "W5 different era + name not compatible"
    elif dates["verdict"] == "conflict" and support is True and row.type != "political_entity":
        # (a generic polity row - 'Egypt' - legitimately spans many eras)
        rule = "W6 different era + row text dates the row's era"
    elif generic_hard:
        rule = "W7 concept QID (lower-case class) on a proper-named row"
    elif (dates["verdict"] == "conflict" and support is not False and row.type in FAR_GAP
          and (dates.get("gap") or 0) > FAR_GAP[row.type]):
        rule = f"W8 far era ({dates.get('gap')}y apart): another {row.type} of the same name"
    if rule:
        out.update(verdict="wrong", rule=rule)
    elif out["issues"] and out["issues"] != [f"redirect->{final}"]:
        out["verdict"] = "suspect"
        out["rule"] = _suspect_reason(name, klass, generic, dates["verdict"], support, name_ok)
    elif out["issues"]:
        out["verdict"] = "redirect"
    out["severity"] = _severity(out)
    return out


def _suspect_reason(name, klass, generic, dates, support, name_ok=True) -> str:
    if klass == "contradiction":
        return ("S1 class contradicts type (type or QID wrong)" if name_ok
                else "S1 class contradicts type and names disagree")
    if generic:
        return "S2 class QID (concept) for an individual-type row"
    if dates == "conflict":
        return "S3 different era, names agree (namesake?)" + (
            "; row text fits the QID's era (row dates wrong?)" if support is False else "")
    if name in NAME_BAD:
        return f"S4 name {name} with the QID label"
    if dates == "sign":
        return "S5 row dates have the wrong BCE/CE sign"
    if dates == "out_of_tolerance":
        return "S6 dates outside tolerance"
    if klass == "unmatched":
        return "S7 class not in the type's allowed classes"
    if name in ("unrelated", "no_label"):
        return "S8 names share nothing (transliteration?)"
    return "S9 other"


def _severity(out: dict[str, Any]) -> str:
    if out["verdict"] == "wrong":
        return "high"
    rule = out.get("rule", "")
    if rule[:2] in ("S1", "S2", "S3", "S4"):
        return "medium"
    if out["verdict"] == "suspect":
        return "low"
    return "info"


# ── C3: find the correct QID ────────────────────────────────────────────────
def search_names(row) -> list[str]:
    names = [row.name]
    for a in row.aliases[:2]:
        if a and a not in names and not names_equal(a, row.name):
            names.append(a)
    return names


def score_candidate(row, qid: str, rec: dict[str, Any], closure, *, match_text: str = "") -> dict[str, Any]:
    """Which checks a candidate passes for ``row``."""
    names = wd_names(rec)
    ok, why = candidate_name_ok(row.names, names, search_match=match_text) if names else (False, "no_label")
    klass = C.classify(row.type, rec.get("p31", []), closure)
    dates = compare_dates(row.type, row.start, row.end, rec.get("dates") or {})
    need_dates = row.type in DATED_TYPES
    date_ok = dates["verdict"] == "ok" or (not need_dates and dates["verdict"] == "unknown")
    loose = date_ok  # a coarse-dated candidate still counts as a rival to the winner
    if date_ok and dates["verdict"] == "ok":
        # the bounds that confirmed the dates must be precise: a century-precision
        # date ('13th century') confirms nothing to ±5 years
        start, end = wd_bounds(row.type, rec.get("dates") or {})
        compared = [b for y, b in ((row.start, start), (row.end, end)) if y is not None and b]
        date_ok = bool(compared) and all(b[1] >= 8 for b in compared)
    exact = any(names_equal(n, w) or inflected_equal(n, w) for n in row.names for w in names)
    if ok and row.type != "person" and len(_name_tokens(row.name)) == 1 and not exact:
        ok, why = False, "one-word name, no exact label/alias"  # 'Majlis' ~ 'Majlis al-Shura' is not enough
    if ok and row.start is None and row.end is None and len(row.names) > 1 and names \
            and not candidate_name_ok([row.name], names, search_match=match_text)[0]:
        # no dates to back it up: a match on one of the row's aliases alone
        # is not enough ('Valabhi' carries the alias 'Bhati', a Delhi town)
        ok, why = False, "undated row, matched only through an alias"
    class_loose = (klass == "ok" and not C.junk_label(rec.get("p31", [])) and not C.is_generic_class(row.type, rec)
                   and not C.never_historical(row.type, rec.get("p31", []), closure))
    checks = {
        "name": ok,
        "class": class_loose and not C.admin_area_for_city(row.type, rec.get("p31", []), closure),
        "dates": date_ok,
        "enwiki": bool(rec.get("enwiki")),
    }
    return {"qid": qid, "label": rec.get("label", ""), "description": rec.get("description", ""),
            "checks": checks, "passes": all(checks.values()), "exact": exact,
            "near": checks["name"] and checks["class"] and checks["dates"],
            "rival": checks["name"] and class_loose and loose,  # a district still rivals a town
            "date_check": dates["verdict"], "class_check": klass, "name_check": why}


def prefetch_candidates(pairs, client, closure_fn) -> None:
    """Batch C3's network work for many rows: all searches, one entity fetch,
    one subclass-closure pass. ``pairs`` is [(row, exclude)]."""
    client.search_many([n for row, _ in pairs for n in search_names(row)])
    qids = {h["qid"] for row, ex in pairs for n in search_names(row) for h in client.search(n) if h["qid"] not in ex}
    client.get_entities(qids, progress=True)
    client.get_entities([r["redirect_to"] for q in qids if (r := client.entities.get(q, {})).get("status") == "redirect"])
    closure_fn([c for q in qids for c in (client.resolved(q)[1] or {}).get("p31", [])])


def find_correct_qid(row, client, closure_fn, *, exclude: set[str]) -> dict[str, Any]:
    """C3: search Wikidata by name, score every candidate, accept only a unique
    winner whose runner-up is clearly worse (fails name, class or dates)."""
    cands: dict[str, str] = {}
    for name in search_names(row):
        for hit in client.search(name, limit=10):
            if hit["qid"] not in exclude:
                cands.setdefault(hit["qid"], hit.get("match_text") or "")
    if not cands:
        return {"outcome": "no_candidates", "candidates": []}
    recs = client.get_entities(cands)
    final: dict[str, tuple[dict, str]] = {}
    for q, mt in cands.items():
        fq, rec = client.resolved(q)
        if rec and rec.get("status") == "ok" and fq not in exclude:
            final.setdefault(fq, (rec, mt))
    closure = closure_fn([c for rec, _ in final.values() for c in rec.get("p31", [])])
    scored = [score_candidate(row, q, rec, closure, match_text=mt) for q, (rec, mt) in final.items()]
    scored.sort(key=lambda s: (s["passes"], s["near"], s["exact"], sum(s["checks"].values())), reverse=True)
    passing = [s for s in scored if s["passes"]]
    near = [s for s in scored if s["near"] or s["rival"]]
    summary = [f"{s['qid']} {s['label']!r} {'+'.join(k for k, v in s['checks'].items() if v) or '-'}"
               for s in scored[:5]]
    if len(passing) == 1 and len(near) == 1:
        return {"outcome": "high", "qid": passing[0]["qid"], "label": passing[0]["label"],
                "description": passing[0]["description"], "candidates": summary}
    if len(passing) > 1 or len(near) > 1:
        return {"outcome": "ambiguous", "candidates": summary}
    return {"outcome": "none_pass", "candidates": summary}
