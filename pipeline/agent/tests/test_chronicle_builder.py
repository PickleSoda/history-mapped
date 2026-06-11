from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


def test_chronicle_builder_creates_chronicle():
    state: AgentRunState = {
        "run_id": "test_1",
        "raw_input": "In 1121, David IV defeated Ilghazi at Didgori.",
        "parsed_events": [
            ParsedEvent(
                label="Battle of Didgori",
                description="David IV defeated Ilghazi at Didgori in 1121.",
                start_date="1121-08-12",
                mentioned_entities=["David IV", "Ilghazi"],
            )
        ],
        "candidate_entities": [
            CandidateEntity(label="David IV", entity_type="person"),
            CandidateEntity(label="Ilghazi", entity_type="person"),
        ],
        "candidate_relations": [
            CandidateRelation(
                source_label="David IV",
                target_label="Battle of Didgori",
                relationship_type="participated_in",
            )
        ],
        "enriched_entities": [
            EnrichedCandidate(
                candidate=CandidateEntity(label="David IV", entity_type="person")
            )
        ],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [
            {
                "relationship_id": "rel-001",
                "source_label": "David IV",
                "target_label": "Battle of Didgori",
                "relationship_type": "participated_in",
            }
        ],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }
    new_state = chronicle_builder(state)
    assert new_state["chronicle"] is not None
    assert new_state["chronicle"].title == "Battle of Didgori"
    assert len(new_state["chronicle"].entries) == 1


def test_chronicle_builder_no_events():
    state: AgentRunState = {
        "run_id": "test_2",
        "raw_input": "",
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
    new_state = chronicle_builder(state)
    assert new_state["chronicle"] is None
    assert any(a.action == "no_events" for a in new_state["audit_log"])
