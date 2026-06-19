import json
from unittest.mock import MagicMock, patch

from pipeline.agent.graph.nodes.completeness_critic import (
    completeness_critic,
    route_after_critic,
    _ensure_relation_endpoints,
    MAX_CRITIC_ITERATIONS,
)
from pipeline.agent.schemas.entities import CandidateEntity
from pipeline.agent.schemas.relations import CandidateRelation


def _rel(src, rtype, tgt):
    return CandidateRelation(source_label=src, target_label=tgt, relationship_type=rtype)


def test_backstop_materializes_typed_endpoint():
    # "Leonardo authored Mona Lisa" with no Mona Lisa entity → create it as a
    # cultural_work so the relation survives and Leonardo isn't orphaned.
    entities = [CandidateEntity(label="Leonardo da Vinci", entity_type="person")]
    relations = [_rel("Leonardo da Vinci", "authored", "Mona Lisa")]
    added, dropped = _ensure_relation_endpoints(entities, relations)
    assert added == 1 and dropped == 0
    mona = next(e for e in entities if e.label == "Mona Lisa")
    assert mona.entity_type == "cultural_work"
    assert len(relations) == 1


def test_backstop_drops_untypeable_dangling_relation():
    # An ambiguous relationship (influenced_by) to a non-entity can't be safely
    # typed, so the relation is dropped rather than inventing a mistyped entity.
    entities = [CandidateEntity(label="Petrarch", entity_type="person")]
    relations = [_rel("Petrarch", "influenced_by", "Some Vague Concept")]
    added, dropped = _ensure_relation_endpoints(entities, relations)
    assert added == 0 and dropped == 1
    assert relations == []


def test_backstop_leaves_intact_relations_untouched():
    entities = [
        CandidateEntity(label="Rome", entity_type="political_entity"),
        CandidateEntity(label="Carthage", entity_type="political_entity"),
    ]
    relations = [_rel("Rome", "at_war_with", "Carthage")]
    added, dropped = _ensure_relation_endpoints(entities, relations)
    assert added == 0 and dropped == 0
    assert len(relations) == 1


def _state(iterations: int = 0) -> dict:
    return {
        "raw_input": "Rome fought Carthage in the Punic Wars; Scipio defeated Hannibal at Zama.",
        "candidate_entities": [CandidateEntity(label="Rome", entity_type="political_entity")],
        "candidate_relations": [],
        "audit_log": [],
        "errors": [],
        "critic_iterations": iterations,
    }


@patch("pipeline.agent.graph.nodes.completeness_critic.create_llm_with_fallbacks")
def test_critic_adds_new_and_dedupes_existing(mock_llm_factory):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "candidate_entities": [
            {"label": "Carthage", "entity_type": "political_entity"},
            {"label": "Rome", "entity_type": "political_entity"},  # duplicate → ignored
        ],
        "candidate_relations": [
            {"source_label": "Rome", "target_label": "Carthage", "relationship_type": "at_war_with"},
            {"source_label": "", "target_label": "Carthage", "relationship_type": "at_war_with"},  # invalid → skipped
        ],
    }))
    mock_llm_factory.return_value = mock_llm

    new_state = completeness_critic(_state())

    labels = {e.label for e in new_state["candidate_entities"]}
    assert labels == {"Rome", "Carthage"}  # Rome not duplicated
    assert len(new_state["candidate_relations"]) == 1
    assert new_state["critic_iterations"] == 1
    assert new_state["critic_done"] is False  # found new items, under cap → keep looping
    assert route_after_critic(new_state) == "loop"


@patch("pipeline.agent.graph.nodes.completeness_critic.create_llm_with_fallbacks")
def test_critic_stops_when_nothing_new(mock_llm_factory):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "candidate_entities": [], "candidate_relations": [],
    }))
    mock_llm_factory.return_value = mock_llm

    new_state = completeness_critic(_state())
    assert new_state["critic_done"] is True
    assert route_after_critic(new_state) == "done"


@patch("pipeline.agent.graph.nodes.completeness_critic.create_llm_with_fallbacks")
def test_critic_respects_iteration_cap(mock_llm_factory):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=json.dumps({
        "candidate_entities": [{"label": "Hannibal", "entity_type": "person"}],
        "candidate_relations": [],
    }))
    mock_llm_factory.return_value = mock_llm

    # Already at the last allowed pass: even though it adds a new entity, it must stop.
    new_state = completeness_critic(_state(iterations=MAX_CRITIC_ITERATIONS - 1))
    assert new_state["critic_iterations"] == MAX_CRITIC_ITERATIONS
    assert new_state["critic_done"] is True
    assert route_after_critic(new_state) == "done"


@patch("pipeline.agent.graph.nodes.completeness_critic.create_llm_with_fallbacks")
def test_critic_survives_bad_json(mock_llm_factory):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="not json at all")
    mock_llm_factory.return_value = mock_llm

    new_state = completeness_critic(_state())
    assert any(e.node == "completeness_critic" for e in new_state["errors"])
    assert new_state["critic_done"] is True  # 0 added → done
