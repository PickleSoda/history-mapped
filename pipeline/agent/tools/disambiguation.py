"""Era- and type-aware Wikidata disambiguation helpers.

The label/keyword ranking in ``_rank_candidates`` is era- and type-blind:

* Era: "Philip II of Macedon" and "Philip II of Spain" score the same for the
  search term "Philip II", so the wrong one (Spain, 1527-1598) gets picked for a
  4th-century-BCE context. ``rerank_by_era`` adds a temporal signal.
* Type: "Amerigo Vespucci" the explorer and a *tall ship* of the same name both
  match the label exactly, so the ship (or a statuette of Cleopatra, or an insect
  genus named "Actium") can win on label alone. ``rerank_by_type`` adds a
  Wikidata-type signal — it boosts candidates whose P31 (instance of) matches the
  entity's kind, penalises ones that can never be the historical subject (taxa,
  given/family names, disambiguation pages; and for people, anything non-human),
  and adds a sitelink-count popularity prior so the famous subject beats an
  obscure namesake.

The pure scoring (``rerank_by_era`` / ``rerank_by_type``) is separated from the
network fetch so it can be unit-tested without hitting Wikidata.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Any

from pipeline.agent.date_utils import normalize_historical_date

# ── Type signal (P31 "instance of") ─────────────────────────────────────────
# Affirmative P31 sets per entity_type: a candidate whose "instance of" lands in
# the set is very likely the right kind of thing. Not exhaustive — absence just
# means "no type boost", we still rank on label + popularity. QIDs are the common
# instance-of targets (incl. key superclasses) for each kind.
_Q_HUMAN = "Q5"
EXPECTED_P31: dict[str, set[str]] = {
    "person": {_Q_HUMAN},
    # Settlements + the historical-place classes that famous ancient sites carry
    # (Q15661340 "ancient city" — Carthage/Babylon/Memphis; Q839954 archaeological
    # site; Q185113 cape) so a real ancient place isn't out-boosted by a modern
    # namesake that happens to be a plain Q515 city.
    "city": {"Q515", "Q3957", "Q486972", "Q15284", "Q5119", "Q839954", "Q532",
             "Q188509", "Q1549591", "Q1093829", "Q15078955", "Q15661340",
             "Q133442", "Q655593", "Q185113", "Q970",  "Q177634"},
    "political_entity": {"Q6256", "Q3024240", "Q48349", "Q417175", "Q7270",
                          "Q1250464", "Q1048835", "Q56061", "Q1520223", "Q3624078",
                          "Q7269", "Q1763527", "Q4204501"},
    "dynasty": {"Q164950", "Q13417114", "Q12759603"},
    "military_unit": {"Q176799", "Q4358176"},
    "event_battle": {"Q178561", "Q188055", "Q1261499", "Q645883"},
    "event_war": {"Q198", "Q8465", "Q103495", "Q350604", "Q831663"},
    "event_rebellion": {"Q124734", "Q1006311", "Q3024240"},
    "event_treaty": {"Q131569", "Q625298", "Q1149055"},
    "epidemic_disease": {"Q12136", "Q18123741", "Q3241045", "Q44512"},
    "religious_movement": {"Q9174", "Q13414953", "Q1530022", "Q9134"},
    "religious_text": {"Q1779582", "Q571", "Q47461344", "Q2188189"},
    "legal_code": {"Q820655", "Q1518534", "Q7748", "Q60520801"},
    "cultural_work": {"Q571", "Q3305213", "Q860861", "Q179700", "Q7725634",
                       "Q47461344", "Q838948", "Q11424", "Q482994"},
    "technology": {"Q11016", "Q2424752", "Q17517"},
    "intellectual_movement": {"Q2198855", "Q49773", "Q968159", "Q2455533"},
    "trade_route": {"Q1067164"},
    "language": {"Q34770", "Q33215", "Q1288568"},
}

# P31 values that are (almost) never the historical subject of a transcript —
# penalise heavily regardless of entity_type.
UNIVERSAL_BLOCK_P31: set[str] = {
    "Q4167410",   # Wikimedia disambiguation page
    "Q13406463",  # Wikimedia list article
    "Q4167836",   # Wikimedia category
    "Q11266439",  # Wikimedia template
    "Q202444",    # given name
    "Q12308941",  # male given name
    "Q11879590",  # female given name
    "Q3409032",   # unisex given name
    "Q101352",    # family name
    "Q16521",     # taxon
    "Q4886",      # taxon (legacy)
}

# entity_types whose subject MUST be a human (Q5). A best candidate that is some
# other kind of thing (ship, statuette, cognomen, settlement) is simply wrong.
_HUMAN_ONLY_TYPES = {"person"}

_LEADING_YEAR_RE = re.compile(r"^(-?\d{1,6})")


def era_year(date_str: Any) -> int | None:
    """Parse a signed year from a date string ('334 BCE' -> -334, '1453' -> 1453)."""
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    norm = normalize_historical_date(date_str) or ""
    match = _LEADING_YEAR_RE.match(norm.strip())
    return int(match.group(1)) if match else None


def context_era(events: list[Any]) -> int | None:
    """Median year across the parsed events — the transcript's temporal centre.

    Used as a fallback era for entities the extractor didn't date.
    """
    years: list[int] = []
    for event in events:
        for date in (getattr(event, "start_date", None), getattr(event, "end_date", None)):
            year = era_year(date)
            if year is not None:
                years.append(year)
    if not years:
        return None
    return int(median(sorted(years)))


def rerank_by_era(
    candidates: list[dict[str, Any]],
    target_era: int | None,
    dates_by_qid: dict[str, dict[str, Any]],
    *,
    close: int = 150,
    far: int = 400,
    bonus: float = 0.3,
    penalty: float = 0.4,
) -> list[dict[str, Any]]:
    """Adjust candidate scores by temporal proximity, then re-sort.

    ``dates_by_qid`` maps qid -> {'start_date': ..., 'end_date': ...} (already
    fetched). A candidate within ``close`` years of ``target_era`` gets +``bonus``;
    one more than ``far`` years away gets -``penalty``. Candidates with no usable
    date are left untouched. Mutates ``score`` and annotates ``era_year``/``era_diff``.
    """
    if target_era is None:
        return candidates

    for cand in candidates:
        info = dates_by_qid.get(cand.get("qid"), {})
        cand_era = era_year(info.get("start_date"))
        if cand_era is None:
            cand_era = era_year(info.get("end_date"))
        if cand_era is None:
            continue
        diff = abs(target_era - cand_era)
        cand["era_year"] = cand_era
        cand["era_diff"] = diff
        score = cand.get("score", 0.0)
        if diff <= close:
            cand["score"] = round(min(1.0, score + bonus), 3)
        elif diff >= far:
            cand["score"] = round(max(0.0, score - penalty), 3)

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates


def is_ambiguous(candidates: list[dict[str, Any]], gap: float = 0.25) -> bool:
    """True when the top two candidates are within ``gap`` — worth era-disambiguating."""
    if len(candidates) < 2:
        return False
    return (candidates[0].get("score", 0.0) - candidates[1].get("score", 0.0)) < gap


def _popularity_boost(sitelinks: int, weight: float) -> float:
    """Diminishing-returns popularity prior from Wikipedia sitelink count.

    A famous historical subject has many language editions (Cicero ~200, Cleopatra
    ~170); an obscure namesake (a statuette, a training ship) has a handful. The
    ratio form saturates so a hugely-linked entity can't dominate purely on fame:
    10→0.25w, 30→0.5w, 100→0.77w, 200→0.87w of ``weight``.
    """
    if sitelinks <= 0:
        return 0.0
    return round((sitelinks / (sitelinks + 30)) * weight, 3)


def type_matches(entity_type: str, p31: list[str] | set[str]) -> bool:
    """True when any of the candidate's P31 ids is an expected instance-of for the
    entity_type. False when we have no expectations for the type (caller decides)."""
    expected = EXPECTED_P31.get(entity_type)
    if not expected:
        return False
    return bool(expected & set(p31))


def rerank_by_type(
    candidates: list[dict[str, Any]],
    entity_type: str,
    meta_by_qid: dict[str, dict[str, Any]],
    *,
    bonus: float = 0.35,
    block_penalty: float = 0.6,
    wrong_kind_penalty: float = 0.5,
    pop_weight: float = 0.4,
) -> list[dict[str, Any]]:
    """Adjust candidate scores by Wikidata type (P31) + popularity, then re-sort.

    ``meta_by_qid`` maps qid -> {'p31': [...], 'sitelinks': int}. For each candidate:
      + ``bonus``                 if its P31 matches EXPECTED_P31[entity_type]
      - ``block_penalty``         if its P31 is in UNIVERSAL_BLOCK_P31 (taxon, name, …)
      - ``wrong_kind_penalty``    if entity_type must be human but the candidate
                                  has a P31 and none of it is Q5 (ship/statuette/…)
      + popularity prior          scaled from sitelink count
    Candidates with no metadata are left untouched. Annotates ``p31``/``sitelinks``.
    """
    human_only = entity_type in _HUMAN_ONLY_TYPES
    for cand in candidates:
        meta = meta_by_qid.get(cand.get("qid"))
        if not meta:
            continue
        p31 = list(meta.get("p31", []) or [])
        sitelinks = int(meta.get("sitelinks", 0) or 0)
        cand["p31"] = p31
        cand["sitelinks"] = sitelinks
        score = cand.get("score", 0.0)

        if type_matches(entity_type, p31):
            score += bonus
        if set(p31) & UNIVERSAL_BLOCK_P31:
            score -= block_penalty
        if human_only and p31 and _Q_HUMAN not in p31:
            score -= wrong_kind_penalty

        score += _popularity_boost(sitelinks, pop_weight)
        cand["score"] = round(max(0.0, score), 3)

    candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return candidates


_ORDINAL_WORDS = {
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
    "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
    "eighteenth", "nineteenth", "twentieth", "thirtieth",
}
_ROMAN = re.compile(r"x{0,3}(ix|iv|v?i{0,3})")


# Apostrophes / ayn-hamza marks are dropped, not word breaks ("al-Ma'mun" ~
# "al-Maʾmun", "Qur'an" ~ "Quran"); letters NFKD can't decompose are
# transliterated so they aren't silently lost ("Đại Việt" ~ "Dai Viet"), and
# Unicode dashes split words. PHP gets the same from Str::ascii plus the same
# apostrophe strip.
_APOSTROPHES = re.compile("[\u0027\u0060\u00b4\u2018\u2019\u02bb\u02bc\u02be\u02bf]")
_TRANSLIT = str.maketrans({
    "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L",
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i", "þ": "th", "Þ": "Th", "ħ": "h",
    # Unicode dashes / no-break space separate words (ASCII-folding would glue
    # "Soviet–Afghan" into one token).
    "\u2010": " ", "\u2011": " ", "\u2012": " ", "\u2013": " ", "\u2014": " ", "\u2015": " ", "\u00a0": " ",
})


def _name_tokens(name: str) -> list[str]:
    import unicodedata

    plain = _APOSTROPHES.sub("", (name or "").translate(_TRANSLIT))
    ascii_name = unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", ascii_name) if t]


def _name_markers(tokens: list[str]) -> list[str]:
    return sorted(t for t in tokens if t.isdigit() or t in _ORDINAL_WORDS or _ROMAN.fullmatch(t))


def names_compatible(a: str, b: str) -> bool:
    """Whether two names plausibly denote the same entity.

    Mirrors App\\Services\\EntityReferenceResolver::namesCompatible (keep in sync):
    after normalising case/diacritics/punctuation one name is a whole-word run
    inside the other AND their regnal/ordinal markers (roman numerals, digits,
    ordinal words) are identical. Guards QID hits against wrong pipeline QIDs —
    "World War I" carrying World War II's QID, "Malik-Shah" → "Malik-Shah II",
    "Qi" → "Qing dynasty" — while accepting "Eighteenth Dynasty of Egypt" ~
    "Eighteenth Dynasty" and "Philip II of France" ~ "Philip II".
    """
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb or _name_markers(ta) != _name_markers(tb):
        return False
    sa, sb = f" {' '.join(ta)} ", f" {' '.join(tb)} "
    return sa in sb or sb in sa


# ── Name identity guard (QID / OHM candidate vs the item's own names) ───────
# names_compatible() answers "may these be the same entity?" (lenient: a
# whole-word sub-phrase). The guard below adds the *positive* disagreement
# signals that Wikidata's prefix search and the type/popularity/era rerank keep
# producing — 'World War I' → World War II, 'Mithridates VI' → Mithridates V,
# 'Qi' → Qing dynasty, 'Julian' → Queen Juliana, OHM 'Romagna' → Romania — and
# the decision rules built on them. Mirrored in PHP by
# App\Services\EntityReferenceResolver::namesConflict / recordMatchesRow (keep
# in sync).

# A token that extends a shorter one by one of these is the same name inflected
# (plural / demonym / adjective: 'Ottoman'→'Ottomans', 'Assyria'→'Assyrian',
# 'Frank'→'Frankish'). Any other extension is a different name ('Qi'→'Qing',
# 'Julian'→'Juliana', 'Gaza'→'Gazala').
_PLURAL_SUFFIXES = ("s", "es")
_DERIVED_SUFFIXES = ("n", "ns", "an", "ans", "ian", "ians", "ic", "ics", "ish", "ese")
# Two different tokens this similar (1 - levenshtein / longer length) are a
# near-miss, not a spelling of the same name: Romagna/Romania 0.71,
# Prussia/Russia 0.86, Lydia/Lycia 0.8. Transliteration variants (Asoka/Ashoka)
# also land here, so callers check aliases (names_compatible) FIRST.
_NEAR_MISS_SIMILARITY = 0.7

# Lifetime-bounded kinds whose Wikidata dates are a fair identity signal (unlike
# cities/regions, whose inception is often deep-BCE or absent).
BOUNDED_LIFETIME_TYPES = {
    "person", "dynasty", "political_entity", "military_unit",
    "event_war", "event_battle", "event_treaty", "event_rebellion",
    "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease",
}


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _is_inflection(base: str, suffix: str) -> bool:
    if suffix in _PLURAL_SUFFIXES:
        return len(base) >= 3
    return suffix in _DERIVED_SUFFIXES and len(base) >= 4


def _tokens_near_miss(x: str, y: str) -> bool:
    """Two different tokens that look like the same name but are not."""
    if x == y:
        return False
    short, long_ = (x, y) if len(x) <= len(y) else (y, x)
    if long_.startswith(short):
        return len(short) >= 2 and not _is_inflection(short, long_[len(short):])
    if len(short) < 4:
        return False
    return 1 - _levenshtein(x, y) / len(long_) >= _NEAR_MISS_SIMILARITY


def names_conflict(a: str, b: str) -> str | None:
    """Why two names positively denote DIFFERENT entities, or None.

    'markers'   — both carry regnal/ordinal markers and they differ (World War I
                  vs II, Mithridates VI vs V, Eighteenth vs Nineteenth Dynasty).
    'near_miss' — a token one name has and the other lacks is a non-inflectional
                  extension or a near-spelling of the other's (Qi vs Qing dynasty,
                  Julian vs Queen Juliana, Romagna vs Romania).
    Wholly different names ('Byzantine Empire' vs 'Imperium Romanum
    Orientale') are NOT a conflict — that is the 'unrelated' case.
    """
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return None
    ma, mb = _name_markers(ta), _name_markers(tb)
    if ma and mb and ma != mb:
        return "markers"
    sa, sb = set(ta), set(tb)
    only_a = [t for t in sa - sb if t not in ma]
    only_b = [t for t in sb - sa if t not in mb]
    for x in only_a:
        for y in only_b:
            if _tokens_near_miss(x, y):
                return "near_miss"
    return None


def names_equal(a: str, b: str) -> bool:
    """Same name after case/diacritic/punctuation normalisation."""
    ta = _name_tokens(a)
    return bool(ta) and ta == _name_tokens(b)


def name_identity(names: list[str], cand_names: list[str]) -> str:
    """Classify a candidate's names against an item's names.

    ``names[0]`` / ``cand_names[0]`` are the primary labels; the rest are
    aliases. Returns 'compatible' (some name pair passes names_compatible),
    else the primaries' names_conflict reason ('markers' | 'near_miss'), else
    'unrelated'.
    """
    names = [n for n in names if n and n.strip()]
    cand_names = [c for c in cand_names if c and c.strip()]
    if not names or not cand_names:
        return "unrelated"
    if any(names_compatible(n, c) for n in names for c in cand_names):
        return "compatible"
    return names_conflict(names[0], cand_names[0]) or "unrelated"


def candidate_name_ok(names: list[str], cand_names: list[str], *, search_match: str = "") -> tuple[bool, str]:
    """Whether a Wikidata candidate may be assigned to an item, with the reason.

    Accepted when some item name (label/alias) is compatible with some candidate
    name (label/alias), or — failing that — when Wikidata's search matched the
    item's full name exactly (``search_match``: its match.text, e.g. a label in
    another language, 'Coptos' for Qift) and the labels don't disagree on a
    regnal/ordinal marker. A prefix-only search hit ('Qi' → 'Qing dynasty') or
    a different name that only the type/popularity rerank promoted is rejected.
    """
    verdict = name_identity(names, cand_names)
    if verdict == "compatible":
        return True, verdict
    exact_hit = bool(search_match) and any(names_equal(search_match, n) for n in names if n)
    if exact_hit and verdict != "markers":
        return True, "exact_search_hit"
    return False, verdict


def era_distance(target: int | None, start: int | None, end: int | None) -> int | None:
    """Years between ``target`` and a [start, end] span (0 = inside), BCE/CE
    sign-insensitive (the extractor mis-signs years; see _sign_corrected)."""
    if target is None or (start is None and end is None):
        return None
    lo = start if start is not None else end
    hi = end if end is not None else start
    lo, hi = min(lo, hi), max(lo, hi)

    def _dist(t: int) -> int:
        return 0 if lo <= t <= hi else min(abs(t - lo), abs(t - hi))

    return min(_dist(target), _dist(-target))


def screen_candidates(
    candidates: list[dict[str, Any]],
    label: str,
    aliases: list[str] | None,
    meta_by_qid: dict[str, dict[str, Any]],
    *,
    target_era: int | None = None,
    era_tolerance: int = 400,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """Split ranked Wikidata candidates into (kept, [(rejected, reason)]), order kept.

    Rejects a candidate when:
      * its P31 is never a historical subject (disambiguation page, given or
        family name, taxon — UNIVERSAL_BLOCK_P31);
      * its names fail candidate_name_ok against the item's label + aliases
        (search label/aliases, meta label/aliases and the search match text are
        all considered);
      * its label differs from the item's label (an alias / sub-phrase / foreign
        exact hit carried it) and its Wikidata dates lie more than
        ``era_tolerance`` years from ``target_era`` — 'Julian' (c. 360) must not
        become Julian of Norwich (1343-1416). Pass ``target_era=None`` for
        persistent places whose dates mislead.
    """
    names = [label, *(aliases or [])]
    kept: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], str]] = []
    for cand in candidates:
        meta = meta_by_qid.get(cand.get("qid")) or {}
        p31 = set(meta.get("p31") or cand.get("p31") or [])
        if p31 & UNIVERSAL_BLOCK_P31:
            rejected.append((cand, "blocked_p31"))
            continue
        primary = meta.get("label") or cand.get("label") or ""
        cand_names = [primary, cand.get("label") or "", *(cand.get("aliases") or []),
                      *(meta.get("aliases") or [])]
        ok, reason = candidate_name_ok(names, cand_names, search_match=cand.get("match_text") or "")
        if ok and target_era is not None and not names_equal(label, primary):
            dist = era_distance(target_era, era_year(meta.get("start_date")), era_year(meta.get("end_date")))
            if dist is not None and dist > era_tolerance:
                ok, reason = False, f"far_era({dist}y)"
        if ok:
            kept.append(cand)
        else:
            rejected.append((cand, reason))
    return kept, rejected


def record_matches_row(name: str, alt_names: list[str] | None, row_names: list[str]) -> bool:
    """Whether an import record may merge into a row found by QID / OHM id.

    Mirrors App\\Services\\EntityReferenceResolver::recordMatchesRow (keep in
    sync). ``row_names[0]`` is the row's name, the rest its aliases. True when
    the record's name is compatible with the row's name or an alias (the
    EntityReferenceResolver relation guard); or when one of the record's
    alternative names is, and the record's name does not positively conflict
    with the row's name (so 'Zhu Di' [alias 'Yongle Emperor'] merges into
    'Yongle Emperor', but 'Romagna' [OHM alias 'Romania'] does not merge into
    'Romania').
    """
    row_names = [r for r in row_names if r and r.strip()]
    if not name or not row_names:
        return False
    if any(names_compatible(name, r) for r in row_names):
        return True
    if names_conflict(name, row_names[0]):
        return False
    return any(names_compatible(a, r) for a in (alt_names or []) if a for r in row_names)


# ── Temporal identity guard (same name, different era) ──────────────────────
# The name guards above cannot tell namesakes apart: 'Philip II' (Macedon,
# 382-336 BCE) and 'Philip II' (Spain, 1527-1598) are the SAME name. Dates can:
# a candidate / relation endpoint matched to an existing row by name, alias or
# QID is rejected when both sides are dated and their spans are clearly
# incompatible, and among several same-name rows the date-compatible one wins.
# Mirrored in PHP by App\Services\EntityReferenceResolver::temporalFit /
# pickNamesake (keep in sync: the tolerances, the deep-antiquity widening, the
# round-century blur, the sign-insensitivity, the tiering and the
# contemporaneous relation types).

# Max years between two non-overlapping spans that may still be the same
# entity, per entity_type. Types absent here are never date-checked: polities,
# places and cultural things carry fuzzy or open-ended spans, and one generic
# row ('Egypt') legitimately serves many eras.
NAMESAKE_TOLERANCE_YEARS: dict[str, int] = {
    "person": 60,
    "dynasty": 150,
    "military_unit": 100,
    "event_battle": 50,
    "event_war": 50,
    "event_treaty": 50,
    "event_rebellion": 50,
    "event_natural_disaster": 50,
    "event_legal_reform": 50,
    "event_tech_adoption": 50,
    "migration": 100,
    "epidemic_disease": 100,
}
# Before 1000 BCE, chronologies disagree by decades (Mesopotamian middle vs
# short chronology ~60y), so the tolerance widens.
DEEP_ANTIQUITY_YEAR = -1000
DEEP_ANTIQUITY_EXTRA_YEARS = 75
# A lone round-century year ('-800', '100') is usually a Wikidata
# century-precision date stored as one year (Catualda c. 19 CE as '100'), so it
# stands for ±100 years, not a point.
ROUND_CENTURY_BLUR_YEARS = 100

# Relation types whose date implies every dated endpoint existed then (a ruler
# rules while alive). Others (influenced_by, inspired, caused, spread_to, …) may
# link a long-dead person and are not used as a temporal signal.
CONTEMPORANEOUS_RELATION_TYPES = frozenset({
    "rules", "governed_by", "vassal_of", "suzerain_of", "allied_with", "at_war_with",
    "succeeded_by", "preceded_by", "born_in", "died_in", "resided_in", "commanded",
    "founded", "authored", "commissioned", "married_to", "parent_of", "child_of",
    "sibling_of", "mentor_of", "student_of", "assassinated_by", "member_of_dynasty",
    "patron_of", "participated_in", "fought_at", "defeated_at", "victorious_at",
    "stationed_at", "recruited_from", "commanded_by", "controlled_by", "minted_by",
    "persecuted_by", "built_by", "destroyed_by", "restored_by", "invented", "taught_at",
    "signed_by", "violated_by", "guaranteed_by", "mediated_by", "enforced_by", "adheres_to",
})

# Tiers, best first. 'conflict' rows are rejected outright.
_FIT_ORDER = ("match", "near", "unknown")
NAMESAKE_AMBIGUOUS = "namesake_ambiguous"

Span = tuple[int, int]


def year_span(start: int | None, end: int | None) -> Span | None:
    """(lo, hi) from optional start/end years; one bound alone is a point."""
    lo = start if start is not None else end
    hi = end if end is not None else start
    if lo is None or hi is None:
        return None
    return (min(lo, hi), max(lo, hi))


def span_of_dates(start: Any, end: Any) -> Span | None:
    """year_span from date strings / ints ('-382', '1556-01-01', 1598)."""
    def _year(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return era_year(value) if isinstance(value, str) else None

    return year_span(_year(start), _year(end))


def union_spans(spans: list[Span | None]) -> Span | None:
    """Smallest span covering every given span (None when there are none)."""
    known = [s for s in spans if s is not None]
    if not known:
        return None
    return (min(s[0] for s in known), max(s[1] for s in known))


def temporal_gap(a: Span | None, b: Span | None) -> int | None:
    """Years between two spans (0 = they overlap); None when either is unknown.

    Sign-insensitive like era_distance: the extractor mis-signs years
    ('Augustus rules Gallia 27' for 27 BCE), so ``a`` is also compared with its
    BCE/CE mirror image and the smaller gap counts.
    """
    if a is None or b is None:
        return None

    def _gap(x: Span, y: Span) -> int:
        return max(0, max(x[0], y[0]) - min(x[1], y[1]))

    return min(_gap(a, b), _gap((-a[1], -a[0]), b))


def temporal_tolerance(entity_type: str | None, a: Span, b: Span) -> int | None:
    """Allowed gap for ``entity_type`` (None = type not date-checked)."""
    base = NAMESAKE_TOLERANCE_YEARS.get(entity_type or "")
    if base is None:
        return None
    if min(a[0], b[0]) < DEEP_ANTIQUITY_YEAR:
        base += DEEP_ANTIQUITY_EXTRA_YEARS
    return base


def temporal_fit(entity_type: str | None, a: Span | None, b: Span | None) -> str:
    """How two dated spans of one ``entity_type`` relate as an identity signal.

    'match'    — they overlap;
    'near'     — they don't, but are within the type's tolerance (same person,
                 slightly different dates: a reign vs a lifespan, two chronologies);
    'conflict' — clearly different eras: not the same entity;
    'unknown'  — a side is undated, or the type is not date-checked.
    """
    if a is None or b is None:
        return "unknown"
    a, b = _blur_round_century(a), _blur_round_century(b)
    tolerance = temporal_tolerance(entity_type, a, b)
    if tolerance is None:
        return "unknown"
    gap = temporal_gap(a, b)
    if gap == 0:
        return "match"
    return "near" if gap <= tolerance else "conflict"


def _blur_round_century(span: Span) -> Span:
    """A single round-century year (century precision) as ±ROUND_CENTURY_BLUR_YEARS."""
    year = span[0]
    if span[0] == span[1] and year != 0 and year % 100 == 0:
        return (year - ROUND_CENTURY_BLUR_YEARS, year + ROUND_CENTURY_BLUR_YEARS)
    return span


def temporally_incompatible(entity_type: str | None, a: Span | None, b: Span | None) -> bool:
    return temporal_fit(entity_type, a, b) == "conflict"


def row_span(row: dict[str, Any]) -> Span | None:
    """Span of a DB row dict carrying start_year / end_year."""
    return year_span(row.get("start_year"), row.get("end_year"))


def pick_namesake(
    rows: list[dict[str, Any]],
    span: Span | None,
    *,
    entity_type: str | None = None,
    unique: bool = False,
) -> tuple[dict[str, Any] | None, str]:
    """Choose among same-name rows (in preference order) by date compatibility.

    Mirrors App\\Services\\EntityReferenceResolver::pickNamesake (keep in sync).
    Each row's own ``entity_type`` (else ``entity_type``) sets the tolerance;
    ``span`` is the reference: the candidate's dates, or a relation's / chronicle
    entry's dates. Rows in 'conflict' are dropped; the best non-empty tier
    (match > near > unknown) is kept. Returns (row, fit) on success, else
    (None, reason):
      'none'                — no rows;
      'namesake_ambiguous'  — every row is date-incompatible, or the best tier
                              holds rows that are date-incompatible with EACH
                              OTHER (two dated namesakes, nothing to choose by);
      'ambiguous'           — ``unique`` (alias lookups) and the best tier holds
                              more than one row.
    Rows that are mutually compatible (or undated) are presumed duplicates of
    one entity, and the first wins — the pre-guard behaviour.
    """
    if not rows:
        return None, "none"
    tiers: dict[str, list[dict[str, Any]]] = {fit: [] for fit in _FIT_ORDER}
    for row in rows:
        fit = temporal_fit(row.get("entity_type") or entity_type, span, row_span(row))
        if fit != "conflict":
            tiers[fit].append(row)
    for fit in _FIT_ORDER:
        best = tiers[fit]
        if not best:
            continue
        if unique and len(best) > 1:
            return None, "ambiguous"
        for i, first in enumerate(best):
            for second in best[i + 1:]:
                if temporally_incompatible(first.get("entity_type") or entity_type,
                                           row_span(first), row_span(second)):
                    return None, NAMESAKE_AMBIGUOUS
        return best[0], fit
    return None, NAMESAKE_AMBIGUOUS
