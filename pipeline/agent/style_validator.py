"""Style validation for generated entity summaries and relation descriptions.

Checks content against the rules defined in style_guide.md and returns
structured feedback that the generate_content node can use for self-correction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleViolation:
    rule: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class StyleValidationResult:
    content_type: str  # "entity_summary" | "relation_description"
    passed: bool
    violations: list[StyleViolation] = field(default_factory=list)


# ─── Entity Summary Rules ────────────────────────────────────────────────────

MAX_SUMMARY_SENTENCES = 2
MAX_SUMMARY_CHARS = 280

SELF_NAMING_PATTERNS = [
    re.compile(rf"^{re.escape(name)}\b", re.IGNORECASE)
    for name in [
        "this entity", "this person", "this state", "this city",
        "this battle", "this event", "this culture", "this dynasty",
        "this polity", "this kingdom", "this empire",
    ]
]

VAGUE_PHRASES = [
    "played a role", "was involved", "was important", "was significant",
    "played an important role", "played a significant role",
    "was a key figure", "was a major figure", "was instrumental",
    "was crucial", "was essential", "was vital",
]

WEAK_VERBS = ["was", "is", "were", "are", "had", "has", "did"]

TEMPORAL_KEYWORDS = [
    "from", "to", "in", "on", "around", "during", "by", "until", "before", "after",
    "century", "BCE", "CE", "AD", "BC", "period", "era", "reign",
]

BCE_EXPOSURE_PATTERN = re.compile(r"(?:^|\s)-\d{1,4}(?:\s|$|[,.;])")


# Pre-built regex patterns for temporal detection
_TEMPORAL_PATTERNS = [
    # Year ranges: from 1089 to 1125
    re.compile(r"\bfrom\s+\d{1,4}\s+to\s+\d{1,4}\b", re.IGNORECASE),
    # In/on year: in 1121, on August 12, 1121
    re.compile(r"\b(?:in|on|around|by|until|before|after)\s+(?:the\s+)?(?:early\s+|mid\s+|late\s+)?(?:\d{1,4}|\w+\s+\d{1,4})\b", re.IGNORECASE),
    # Century: in the early 12th century
    re.compile(r"\b(?:in|during|by)\s+the\s+(?:early\s+|mid\s+|late\s+)?\d{1,2}(?:th|st|nd|rd)\s+century\b", re.IGNORECASE),
    # Era/period: during the Middle Kingdom period
    re.compile(r"\b(?:during|in|throughout)\s+the\s+\w+(?:\s+\w+){0,3}\s+(?:period|era|epoch|age)\b", re.IGNORECASE),
    # Reign: during the reign of X
    re.compile(r"\b(?:during|under|in)\s+the\s+reign\s+of\b", re.IGNORECASE),
    # BCE/CE: around 2000 BCE
    re.compile(r"\b\d{1,4}\s*(?:BCE|CE|BC|AD)\b", re.IGNORECASE),
    # Just a 4-digit year standing alone (e.g. "in 1121")
    re.compile(r"\b(?:in|on|around|by)\s+\d{3,4}\b", re.IGNORECASE),
]

# ─── Relation Description Rules ──────────────────────────────────────────────

MAX_RELATION_SENTENCES = 2
MAX_RELATION_CHARS = 220

VAGUE_RELATION_PHRASES = [
    "was related to", "was connected with", "was involved in",
    "was associated with", "had a relationship with",
    "was linked to", "was tied to",
]

PASSIVE_PATTERNS = [
    re.compile(r"\bwas\s+\w+ed\b", re.IGNORECASE),  # was defeated, was founded
    re.compile(r"\bwere\s+\w+ed\b", re.IGNORECASE),
    re.compile(r"\bbeen\s+\w+ed\b", re.IGNORECASE),
]


# ─── Validation Functions ────────────────────────────────────────────────────

def _sentence_count(text: str) -> int:
    """Rough sentence count based on sentence-ending punctuation."""
    return len(re.findall(r"[.!?]+", text))


def _starts_with_entity_name(text: str, entity_name: str) -> bool:
    """Check if text begins with the entity's own name."""
    clean = entity_name.strip().rstrip(".")
    # Handle multi-word names
    first_words = clean.split()
    if len(first_words) <= 3:
        pattern = rf"^{re.escape(clean)}\b"
        return bool(re.match(pattern, text.strip(), re.IGNORECASE))
    # For longer names, just check the first word
    return bool(re.match(rf"^{re.escape(first_words[0])}\b", text.strip(), re.IGNORECASE))


def validate_entity_summary(summary: str, entity_name: str) -> StyleValidationResult:
    """Validate an entity summary against the style guide.

    Parameters
    ----------
    summary: The generated summary text.
    entity_name: The canonical name of the entity (to check for self-naming).

    Returns
    -------
    StyleValidationResult with violations found.
    """
    violations: list[StyleViolation] = []

    # Length checks
    if not summary or not summary.strip():
        violations.append(StyleViolation(
            rule="non_empty",
            message="Summary is empty.",
            severity="error",
        ))
        return StyleValidationResult("entity_summary", False, violations)

    text = summary.strip()
    sentences = _sentence_count(text)

    if sentences > MAX_SUMMARY_SENTENCES:
        violations.append(StyleViolation(
            rule="max_sentences",
            message=f"Summary has {sentences} sentences; maximum is {MAX_SUMMARY_SENTENCES}.",
            severity="error",
        ))

    if len(text) > MAX_SUMMARY_CHARS:
        violations.append(StyleViolation(
            rule="max_length",
            message=f"Summary is {len(text)} characters; recommended maximum is {MAX_SUMMARY_CHARS}.",
            severity="warning",
        ))

    # Self-naming check
    if _starts_with_entity_name(text, entity_name):
        violations.append(StyleViolation(
            rule="no_self_name",
            message="Summary begins with the entity's own name.",
            severity="error",
        ))

    # Generic self-reference check
    for pattern in SELF_NAMING_PATTERNS:
        if pattern.search(text):
            violations.append(StyleViolation(
                rule="no_generic_self_reference",
                message="Summary uses generic self-reference like 'This entity...' or 'This person...'",
                severity="error",
            ))
            break

    # Vague phrase check
    for phrase in VAGUE_PHRASES:
        if phrase.lower() in text.lower():
            violations.append(StyleViolation(
                rule="no_vague_phrases",
                message=f"Summary contains vague phrase: '{phrase}'.",
                severity="error",
            ))

    # Temporal presence check
    has_temporal = any(p.search(text) for p in _TEMPORAL_PATTERNS)
    if not has_temporal:
        violations.append(StyleViolation(
            rule="temporal_scope",
            message="Summary lacks temporal scope (date, era, reign period, or century).",
            severity="warning",
        ))

    # BCE exposure check
    if BCE_EXPOSURE_PATTERN.search(text):
        violations.append(StyleViolation(
            rule="bce_format",
            message="Summary exposes internal negative-year notation (e.g. '-2000'). Use '2000 BCE' instead.",
            severity="error",
        ))

    # Overuse of weak verbs (heuristic: more than 3 weak verbs in a short text)
    weak_count = sum(1 for verb in WEAK_VERBS if f" {verb} " in f" {text.lower()} ")
    if weak_count > 3:
        violations.append(StyleViolation(
            rule="active_verbs",
            message=f"Summary overuses weak verbs (was/is/had/did). Found {weak_count} instances. Prefer active, specific verbs.",
            severity="warning",
        ))

    passed = not any(v.severity == "error" for v in violations)
    return StyleValidationResult("entity_summary", passed, violations)


def validate_relation_description(description: str) -> StyleValidationResult:
    """Validate a relation description against the style guide.

    Parameters
    ----------
    description: The generated relation description text.

    Returns
    -------
    StyleValidationResult with violations found.
    """
    violations: list[StyleViolation] = []

    if not description or not description.strip():
        violations.append(StyleViolation(
            rule="non_empty",
            message="Description is empty.",
            severity="error",
        ))
        return StyleValidationResult("relation_description", False, violations)

    text = description.strip()
    sentences = _sentence_count(text)

    if sentences > MAX_RELATION_SENTENCES:
        violations.append(StyleViolation(
            rule="max_sentences",
            message=f"Description has {sentences} sentences; maximum is {MAX_RELATION_SENTENCES}.",
            severity="error",
        ))

    if len(text) > MAX_RELATION_CHARS:
        violations.append(StyleViolation(
            rule="max_length",
            message=f"Description is {len(text)} characters; recommended maximum is {MAX_RELATION_CHARS}.",
            severity="warning",
        ))

    # Vague relation phrases
    for phrase in VAGUE_RELATION_PHRASES:
        if phrase.lower() in text.lower():
            violations.append(StyleViolation(
                rule="no_vague_phrases",
                message=f"Description contains vague phrase: '{phrase}'.",
                severity="error",
            ))

    # Passive voice check (heuristic)
    passive_count = sum(1 for pattern in PASSIVE_PATTERNS if pattern.search(text))
    if passive_count > 1:
        violations.append(StyleViolation(
            rule="active_voice",
            message=f"Description uses passive voice ({passive_count} instances). Prefer active voice.",
            severity="warning",
        ))

    # Temporal presence
    has_temporal = any(p.search(text) for p in _TEMPORAL_PATTERNS)
    if not has_temporal:
        violations.append(StyleViolation(
            rule="temporal_qualifier",
            message="Description lacks a temporal qualifier (date, year, reign, or era).",
            severity="warning",
        ))

    # BCE exposure
    if BCE_EXPOSURE_PATTERN.search(text):
        violations.append(StyleViolation(
            rule="bce_format",
            message="Description exposes internal negative-year notation (e.g. '-2000'). Use '2000 BCE' instead.",
            severity="error",
        ))

    passed = not any(v.severity == "error" for v in violations)
    return StyleValidationResult("relation_description", passed, violations)


def validate_all(
    summaries: dict[str, str],
    relation_descriptions: dict[str, str],
) -> dict[str, Any]:
    """Run style validation across all generated content.

    Parameters
    ----------
    summaries: Mapping of entity label → summary text.
    relation_descriptions: Mapping of "source|rel|target" key → description text.

    Returns
    -------
    Dict with overall pass/fail, per-item results, and aggregated violations.
    """
    entity_results = {
        label: validate_entity_summary(text, label)
        for label, text in summaries.items()
    }

    relation_results = {
        key: validate_relation_description(text)
        for key, text in relation_descriptions.items()
    }

    all_violations = []
    for result in list(entity_results.values()) + list(relation_results.values()):
        all_violations.extend(result.violations)

    error_count = sum(1 for v in all_violations if v.severity == "error")
    warning_count = sum(1 for v in all_violations if v.severity == "warning")

    return {
        "passed": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "entity_results": {
            label: {
                "passed": r.passed,
                "violations": [
                    {"rule": v.rule, "message": v.message, "severity": v.severity}
                    for v in r.violations
                ],
            }
            for label, r in entity_results.items()
        },
        "relation_results": {
            key: {
                "passed": r.passed,
                "violations": [
                    {"rule": v.rule, "message": v.message, "severity": v.severity}
                    for v in r.violations
                ],
            }
            for key, r in relation_results.items()
        },
    }
