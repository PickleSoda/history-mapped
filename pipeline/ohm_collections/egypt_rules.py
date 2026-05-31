from __future__ import annotations

import unicodedata
from typing import Any


_EGYPT_TERMS = (
    "upper egypt",
    "lower egypt",
    "egyptian",
    "aegyptus",
    "egypt",
    "kemet",
)

_DEFAULT_TYPES = {
    "battle",
    "city",
    "dynasty",
    "event",
    "geographic_region",
    "historical_period",
    "place",
    "political_entity",
    "region",
    "state",
    "war",
}

_CONDITIONAL_TYPES = {
    "culture",
    "currency",
    "religion",
    "script",
    "writing_system",
}

_WEAK_SUMMARY_MARKERS = (
    "also traded in egypt",
    "traded in egypt",
    "trade with egypt",
    "traded with egypt",
    "also used in egypt",
)

_STRONG_SUMMARY_MARKERS = (
    "egyptian",
    " in egypt",
    " of egypt",
    " from egypt",
    " practiced in egypt",
    " used in egypt",
    " located in egypt",
)


def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized_types = _normalized_entity_types(candidate)
    structural_terms = _matched_terms(_structural_texts(candidate))
    summary_terms = _matched_terms(_summary_texts(candidate))
    matched_terms = sorted(structural_terms | summary_terms)
    reasons: list[str] = []

    if matched_terms:
        reasons.append("lexical_match")

    include = False
    if normalized_types & _DEFAULT_TYPES:
        reasons.append("default_type")
        include = bool(structural_terms or _summary_indicates_primary_domain(candidate))
    elif normalized_types & _CONDITIONAL_TYPES:
        if structural_terms or _summary_indicates_primary_domain(candidate):
            include = True
            reasons.append("conditional_strong_link")
        elif summary_terms:
            reasons.append("weak_incidental_match")
        else:
            reasons.append("no_egypt_link")
    else:
        include = bool(structural_terms)
        if include:
            reasons.append("untyped_lexical_match")
        else:
            reasons.append("no_egypt_link")

    if normalized_types & _CONDITIONAL_TYPES and not include and "weak_incidental_match" not in reasons and summary_terms:
        reasons.append("weak_incidental_match")

    return {
        "include": include,
        "matched_terms": matched_terms,
        "reasons": reasons,
        "score": len(matched_terms) + (2 if include else 0),
        "ambiguity": [],
    }


def _normalized_entity_types(candidate: dict[str, Any]) -> set[str]:
    raw_types = candidate.get("entity_types") or []
    if isinstance(raw_types, str):
        raw_types = [raw_types]
    normalized_types = set()
    for raw_type in raw_types:
        normalized = _normalize_text(raw_type)
        if normalized is not None:
            normalized_types.add(normalized.replace(" ", "_"))
    return normalized_types


def _structural_texts(candidate: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ("name", "description"):
        value = candidate.get(key)
        if isinstance(value, str):
            texts.append(value)

    alternative_names = candidate.get("alternative_names") or []
    if isinstance(alternative_names, str):
        alternative_names = [alternative_names]
    for value in alternative_names:
        if isinstance(value, str):
            texts.append(value)

    raw_tags = candidate.get("raw_tags") or {}
    if isinstance(raw_tags, dict):
        for value in raw_tags.values():
            if isinstance(value, str):
                texts.append(value)

    return texts


def _summary_texts(candidate: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ("summary",):
        value = candidate.get(key)
        if isinstance(value, str):
            texts.append(value)
    return texts


def _matched_terms(texts: list[str]) -> set[str]:
    matches: set[str] = set()
    normalized_texts = [_normalize_text(text) for text in texts]
    for normalized_text in normalized_texts:
        if normalized_text is None:
            continue
        for term in _EGYPT_TERMS:
            if term in normalized_text:
                matches.add(term)
    return matches


def _summary_indicates_primary_domain(candidate: dict[str, Any]) -> bool:
    for text in _summary_texts(candidate):
        normalized_text = _normalize_text(text)
        if normalized_text is None:
            continue
        if any(marker in normalized_text for marker in _WEAK_SUMMARY_MARKERS):
            return False
        if any(marker in normalized_text for marker in _STRONG_SUMMARY_MARKERS):
            return True
    return False


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    collapsed = unicodedata.normalize("NFC", stripped).casefold().replace("-", " ")
    return " ".join(collapsed.split())
