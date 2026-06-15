"""Tests for the deterministic event-anchored relation direction fix."""
from __future__ import annotations

from types import SimpleNamespace

from pipeline.agent.graph.nodes.commit_writer import (
    _entity_type_index,
    _is_event_type,
    _normalize_relation_directions,
)


def _ent(label, etype, aliases=None):
    return SimpleNamespace(
        candidate=SimpleNamespace(label=label, entity_type=etype, aliases=aliases or [])
    )


def _rel(src, tgt, rtype):
    return SimpleNamespace(source_label=src, target_label=tgt, relationship_type=rtype)


def test_is_event_type():
    assert _is_event_type("event_battle")
    assert _is_event_type("event_war")
    assert _is_event_type("migration")
    assert _is_event_type("epidemic_disease")
    assert not _is_event_type("person")
    assert not _is_event_type("political_entity")
    assert not _is_event_type(None)


def test_flips_inverted_event_to_combatant():
    idx = _entity_type_index(
        [_ent("Battle of Waterloo", "event_battle"), _ent("Napoleon Bonaparte", "person")]
    )
    rels = [_rel("Battle of Waterloo", "Napoleon Bonaparte", "defeated_at")]
    assert _normalize_relation_directions(rels, idx) == 1
    assert rels[0].source_label == "Napoleon Bonaparte"
    assert rels[0].target_label == "Battle of Waterloo"


def test_leaves_correct_direction_untouched():
    idx = _entity_type_index(
        [_ent("Battle of Waterloo", "event_battle"), _ent("Duke of Wellington", "person")]
    )
    rels = [_rel("Duke of Wellington", "Battle of Waterloo", "victorious_at")]
    assert _normalize_relation_directions(rels, idx) == 0
    assert rels[0].source_label == "Duke of Wellington"


def test_ignores_non_event_anchored_types():
    idx = _entity_type_index(
        [_ent("Battle of X", "event_battle"), _ent("Person Y", "person")]
    )
    rels = [_rel("Battle of X", "Person Y", "caused")]
    assert _normalize_relation_directions(rels, idx) == 0


def test_uses_alias_for_type_lookup():
    # A polity renamed to its OHM canonical form, with the transcript name kept as
    # an alias that the relation still references.
    idx = _entity_type_index(
        [
            _ent("Battle of Issus", "event_battle"),
            _ent("Imperium Macedonicum", "political_entity", aliases=["Macedon"]),
        ]
    )
    rels = [_rel("Battle of Issus", "Macedon", "participated_in")]
    assert _normalize_relation_directions(rels, idx) == 1
    assert rels[0].source_label == "Macedon"
    assert rels[0].target_label == "Battle of Issus"


def test_no_swap_when_both_event_or_target_unknown():
    idx = _entity_type_index(
        [_ent("War A", "event_war"), _ent("Battle B", "event_battle")]
    )
    # both events -> can't determine, leave alone
    assert _normalize_relation_directions([_rel("War A", "Battle B", "participated_in")], idx) == 0
    # unknown target type -> leave alone
    assert _normalize_relation_directions([_rel("War A", "Mystery", "defeated_at")], idx) == 0
