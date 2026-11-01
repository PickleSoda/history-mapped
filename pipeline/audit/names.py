"""C5: name consistency.

``conventions`` counts the conventions in use; ``name_issues`` lists every
name that departs from them. Only ``mechanical_rename`` results are ever
applied, and only where the dominant convention is clear (DOMINANCE) and the
new name collides with no other row of the same type:

* whitespace: trim, collapse runs, no-break spaces → spaces;
* a whole name wrapped in quotes;
* 'Battle Of X' / 'Siege Of X' / 'The Battle of X' → 'Battle of X';
* an epithet's 'The' inside a person's name ('Alexander The Great') when
  lower-case 'the' dominates;
* era suffixes BC→BCE / AD→CE (or back) when one style dominates.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

DOMINANCE = 0.9
_ERA = re.compile(r"\b(\d{1,4})\s?(BCE|BC|CE|AD|B\.C\.|A\.D\.)(?![A-Za-z])")
_PRE_ERA = re.compile(r"\b(AD|A\.D\.)\s?(\d{1,4})\b")
_QUAL = re.compile(r"\(([^()]*)\)\s*$")
_WRAPPED = re.compile(r'^\s*["“”](.+)["“”]\s*$')
_MEDIA_QUALIFIERS = {"film", "album", "song", "novel", "tv series", "television series", "video game", "band",
                     "play", "opera", "magazine", "newspaper", "ship", "horse", "racehorse", "musician",
                     "footballer", "rapper", "singer", "actor", "actress"}
_ROMAN = re.compile(r"^[IVXLCDM]+$")
_BATTLE_PREFIX = re.compile(r"^(?:the\s+)?(battle|siege)\s+of\s+", re.I)


def conventions(rows) -> dict[str, Counter]:
    c: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        n = r.name
        for m in _ERA.finditer(n):
            c["era_suffix"][m.group(2).replace(".", "")] += 1
        for m in _PRE_ERA.finditer(n):
            c["era_suffix"]["AD (prefix)"] += 1
        q = _QUAL.search(n)
        if q:
            inner = q.group(1)
            if re.fullmatch(r"\d{1,4}(\s?[–-]\s?\d{1,4})?", inner):
                c["qualifier"]["(year, no era)"] += 1
            elif re.search(r"\d", inner):
                c["qualifier"]["(year + era)"] += 1
            else:
                c["qualifier"]["(word)"] += 1
        if r.type == "person":
            for m in re.finditer(r" (the|The) [A-Z]", n):
                c["epithet_article"][m.group(1)] += 1
        if r.type == "event_battle":
            if n.startswith("Battle of "):
                c["battle_form"]["Battle of X"] += 1
            elif n.startswith("Siege of "):
                c["battle_form"]["Siege of X"] += 1
            elif _BATTLE_PREFIX.match(n):
                c["battle_form"]["variant prefix"] += 1
            elif re.match(r"^(First|Second|Third|Fourth|Fifth) (Battle|Siege) of ", n):
                c["battle_form"]["Nth Battle of X"] += 1
            else:
                c["battle_form"]["descriptive"] += 1
        if n[:1].islower():
            c["lower_first"][r.type] += 1
    return c


def dominant(counter: Counter, a: str, b: str) -> str | None:
    total = counter.get(a, 0) + counter.get(b, 0)
    if not total:
        return None
    if counter.get(a, 0) / total >= DOMINANCE:
        return a
    if counter.get(b, 0) / total >= DOMINANCE:
        return b
    return None


def mechanical_rename(name: str, entity_type: str, conv: dict[str, Counter]) -> tuple[str, list[str]]:
    """(new name, reasons). Returns the name unchanged when nothing applies."""
    reasons: list[str] = []
    new = name.replace(" ", " ")
    new = " ".join(new.split())
    if new != name:
        reasons.append("whitespace")
    m = _WRAPPED.match(new)
    if m:
        new = m.group(1).strip()
        reasons.append("wrapping quotes")
    if entity_type == "event_battle":
        m = _BATTLE_PREFIX.match(new)
        if m:
            canon = f"{m.group(1).capitalize()} of "
            if new[:m.end()] != canon:
                new = canon + new[m.end():]
                reasons.append("battle/siege prefix")
    if entity_type == "person" and dominant(conv.get("epithet_article", Counter()), "the", "The") == "the":
        fixed = re.sub(r" The (?=[A-Z])", " the ", new)
        if fixed != new:
            new = fixed
            reasons.append("epithet article")
    era = conv.get("era_suffix", Counter())
    bce = dominant(era, "BCE", "BC")
    ce = dominant(era, "CE", "AD")
    if bce == "BCE":
        fixed = re.sub(r"\b(\d{1,4})\s?(BC|B\.C\.)(?![A-Za-z])", r"\1 BCE", new)
        if fixed != new:
            new, _ = fixed, reasons.append("era suffix BC→BCE")
    if ce == "CE":
        fixed = re.sub(r"\b(\d{1,4})\s?(AD|A\.D\.)(?![A-Za-z])", r"\1 CE", new)
        fixed = re.sub(r"\b(?:AD|A\.D\.)\s?(\d{1,4})\b", r"\1 CE", fixed)
        if fixed != new:
            new, _ = fixed, reasons.append("era suffix AD→CE")
    return new, reasons


def name_issues(rows, conv) -> list[dict[str, Any]]:
    """Every departure worth a look (borderline ones are report-only)."""
    out = []
    by_name_type = Counter((r.name, r.type) for r in rows)
    for r in rows:
        n = r.name
        issues = []
        new, reasons = mechanical_rename(n, r.type, conv)
        if reasons:
            issues.append("mechanical: " + ", ".join(reasons))
        letters = re.sub(r"[^A-Za-z]", "", n)
        if len(letters) >= 4 and letters.isupper() and not all(_ROMAN.match(w) for w in re.findall(r"[A-Z]+", n)):
            issues.append("all caps (acronym?)")
        q = _QUAL.search(n)
        if q and not re.search(r"\d", q.group(1)):
            qual = q.group(1).strip().lower()
            issues.append(("media disambiguator: wrong entity?" if qual in _MEDIA_QUALIFIERS
                           else "wikipedia disambiguator") + f" '({q.group(1)})'")
        if re.fullmatch(r"\d{1,4}( (BCE|CE|BC|AD))?", n):
            issues.append("name is only a year")
        if n[:1].islower() and not re.match(r"^(al|el|as|ad|an|ar|at|az|ibn|bin|ben|de|di|da|du|van|von|der|le|la|'t|'s)[-' ]", n):
            issues.append(f"lower-case first word ({r.type})")
        if r.type == "event_battle" and _BATTLE_PREFIX.match(n) is None and re.search(r"\b(battle|siege)\b", n, re.I) \
                and not re.match(r"^(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth) ", n):
            issues.append("battle name not 'Battle of X'/'Siege of X'")
        if r.type == "person" and re.search(r"\b[A-Z][a-z]+ \d{1,2}$", n):
            issues.append("regnal number in arabic digits")
        if len(n) > 90:
            issues.append("very long name")
        if not issues:
            continue
        collision = reasons and by_name_type.get((new, r.type), 0) > 0 and new != n
        out.append({"entity_id": r.id, "name": n, "entity_type": r.type, "qid": r.qid, "issues": issues,
                    "proposed_name": new if reasons and not collision else "",
                    "apply": bool(reasons) and not collision,
                    "note": "collides with an existing row: merge instead" if collision else ""})
    return out
