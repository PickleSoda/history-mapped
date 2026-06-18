"""Pin: generic / synonym entity types must normalise to the canonical taxonomy.

The LLM emits ~20% of candidates with off-taxonomy types ("polity", "place",
"religion", bare "event") despite the prompt. validate.ALLOWED_ENTITY_TYPES would
drop those, silently blocking backbone entities (Roman Empire="state",
Christianity="religion", Italy="place") and cascading into unresolved relations.
CandidateEntity normalises at construction so they survive.
"""
from __future__ import annotations

import pytest

from pipeline.agent.schemas.entities import CandidateEntity, normalize_entity_type


@pytest.mark.parametrize(
    "raw,label,expected",
    [
        # Polity synonyms / regions / countries → political_entity
        ("polity", "Roman Empire", "political_entity"),
        ("state", "Byzantine Empire", "political_entity"),
        ("country", "Italy", "political_entity"),
        ("empire", "Byzantine Empire", "political_entity"),
        ("place", "Europe", "political_entity"),
        ("region", "Al-Andalus", "political_entity"),
        # Culture synonyms
        ("religion", "Christianity", "religious_movement"),
        ("philosophical_movement", "Stoicism", "intellectual_movement"),
        # Bare event → specific event type by label keyword
        ("event", "Battle of Philippi", "event_battle"),
        ("event", "Punic Wars", "event_war"),
        ("event", "Caesar's Civil War", "event_war"),
        # Case / separator insensitivity
        ("Political Entity", "Macedon", "political_entity"),
        ("EVENT_BATTLE", "Battle of Issus", "event_battle"),
        # Canonical types pass through unchanged
        ("person", "Julius Caesar", "person"),
        ("city", "Rome", "city"),
        ("epidemic_disease", "Black Death", "epidemic_disease"),
    ],
)
def test_normalize_entity_type(raw, label, expected):
    assert normalize_entity_type(raw, label) == expected


def test_unknown_type_is_left_for_validate_to_block():
    # 'historical_period' is a reference-table concept, not an entity type; it
    # must NOT be silently coerced into a real type.
    assert normalize_entity_type("historical_period", "Islamic Golden Age") == "historical_period"


def test_candidate_entity_normalizes_on_construction():
    assert CandidateEntity(label="Roman Republic", entity_type="polity").entity_type == "political_entity"
    assert CandidateEntity(label="Punic Wars", entity_type="event").entity_type == "event_war"
    assert CandidateEntity(label="Christianity", entity_type="religion").entity_type == "religious_movement"
