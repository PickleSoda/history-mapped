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
