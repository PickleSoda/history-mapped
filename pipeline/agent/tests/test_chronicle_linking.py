"""Tests for narrative-based entity linking in chronicle entries."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline.agent.graph.nodes.chronicle_builder import _collect_secondary_entities
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate


def _enriched(label, entity_type="person", aliases=None):
    return EnrichedCandidate(
        candidate=CandidateEntity(label=label, entity_type=entity_type, aliases=aliases or []),
    )


def test_links_entity_named_in_narrative_even_if_not_in_mentioned():
    # parse_sequence missed mentioned_entities, but the names are in the text.
    event = SimpleNamespace(
        mentioned_entities=[],
        description="In the 6th century BCE, Cyrus II of the Achaemenid Dynasty conquered Media.",
    )
    entities = [
        _enriched("Cyrus II"),
        _enriched("Achaemenid Dynasty", "dynasty"),
        _enriched("Babylon", "city"),  # not in this narrative
    ]
    linked = {e.entity_id for e in _collect_secondary_entities(event, entities, {})}
    assert "Cyrus II" in linked
    assert "Achaemenid Dynasty" in linked
    assert "Babylon" not in linked


def test_links_via_alias_in_narrative():
    # Entity adopted OHM's Latin name; the transcript uses the English alias.
    event = SimpleNamespace(mentioned_entities=[], description="The Roman Empire expanded under Trajan.")
    entities = [_enriched("Imperium Romanum", "political_entity", aliases=["Roman Empire"])]
    linked = {e.entity_id for e in _collect_secondary_entities(event, entities, {})}
    assert "Imperium Romanum" in linked  # entity_id uses the label, matched via alias


def test_word_boundary_avoids_false_substring_match():
    event = SimpleNamespace(mentioned_entities=[], description="The Romance languages evolved later.")
    entities = [_enriched("Rome", "city")]
    linked = {e.entity_id for e in _collect_secondary_entities(event, entities, {})}
    assert "Rome" not in linked  # "Rome" must not match inside "Romance"
