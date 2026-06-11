from unittest.mock import MagicMock, patch

import json

from pipeline.agent.graph.nodes.extract_candidates import extract_candidates
from pipeline.agent.graph.nodes.generate_content import generate_content
from pipeline.agent.graph.nodes.parse_sequence import parse_sequence
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate, ParsedEvent
from pipeline.agent.schemas.relations import CandidateRelation


def make_base_state() -> AgentRunState:
    return {
        "run_id": "test_1",
        "raw_input": "In 1121, David IV defeated Ilghazi at Didgori.",
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }


@patch("pipeline.agent.llm.ChatOpenAI")
def test_parse_sequence_returns_events(mock_chat):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content=json.dumps(
            {
                "events": [
                    {
                        "label": "Battle of Didgori",
                        "description": "David IV defeats Ilghazi.",
                        "start_date": "1121-08-12",
                        "end_date": "1121-08-12",
                        "mentioned_entities": ["David IV", "Ilghazi"],
                        "date_uncertain": False,
                    }
                ]
            }
        )
    )
    mock_chat.return_value = mock_llm
    state = make_base_state()
    new_state = parse_sequence(state)
    assert len(new_state["parsed_events"]) == 1
    assert new_state["parsed_events"][0].label == "Battle of Didgori"
    assert len(new_state["audit_log"]) == 1


@patch("pipeline.agent.llm.ChatOpenAI")
def test_extract_candidates(mock_chat):
    mock_llm = MagicMock()
    with open("pipeline/agent/tests/fixtures/llm_responses/extract_candidates.json") as f:
        mock_llm.invoke.return_value = MagicMock(content=f.read())
    mock_chat.return_value = mock_llm
    state = make_base_state()
    state["parsed_events"] = [
        ParsedEvent(
            label="Battle of Didgori",
            description="...",
            start_date="1121-08-12",
            mentioned_entities=["David IV", "Ilghazi"],
        )
    ]
    new_state = extract_candidates(state)
    assert len(new_state["candidate_entities"]) == 4
    assert len(new_state["candidate_relations"]) == 2


@patch("pipeline.agent.llm.ChatOpenAI")
def test_generate_content(mock_chat):
    mock_llm = MagicMock()
    with open("pipeline/agent/tests/fixtures/llm_responses/generate_content.json") as f:
        mock_llm.invoke.return_value = MagicMock(content=f.read())
    mock_chat.return_value = mock_llm
    state = make_base_state()
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="David IV of Georgia", entity_type="person")
        )
    ]
    state["candidate_relations"] = [
        CandidateRelation(
            source_label="David IV of Georgia",
            target_label="Battle of Didgori",
            relationship_type="participated_in",
        )
    ]
    new_state = generate_content(state)
    assert new_state["enriched_entities"][0].summary is not None
    assert "Ruled the Kingdom" in new_state["enriched_entities"][0].summary
