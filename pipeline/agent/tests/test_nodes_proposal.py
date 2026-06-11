from pipeline.agent.graph.nodes.validate import validate
from pipeline.agent.graph.nodes.build_diff import build_diff
from pipeline.agent.graph.nodes.approval_gate import approval_gate
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.validation import ValidationResult
from pipeline.agent.schemas.proposals import ProposedDiff


def make_base_state() -> AgentRunState:
    return {
        "run_id": "test_1",
        "raw_input": "...",
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


def test_validate_blocks_invalid_type():
    state = make_base_state()
    state["enriched_entities"] = [EnrichedCandidate(
        candidate=CandidateEntity(label="X", entity_type="invalid_type"),
        wikidata_match={"qid": "Q1"},
    )]
    new_state = validate(state)
    assert not new_state["validation_results"][0].passed
    assert "Invalid entity type" in new_state["validation_results"][0].errors[0]


def test_validate_passes_valid_entity():
    state = make_base_state()
    state["enriched_entities"] = [EnrichedCandidate(
        candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
        wikidata_match={"qid": "Q1"},
        system_confidence=0.5,
    )]
    new_state = validate(state)
    assert new_state["validation_results"][0].passed


def test_build_diff_sorts_into_buckets():
    state = make_base_state()
    state["enriched_entities"] = [EnrichedCandidate(
        candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
        final_confidence=0.98,
    )]
    state["validation_results"] = [ValidationResult(candidate_id="Battle X", passed=True)]
    new_state = build_diff(state)
    assert new_state["proposed_diff"] is not None
    assert len(new_state["proposed_diff"].create_entities) == 1


def test_approval_gate_auto_commits_low_risk():
    state = make_base_state()
    state["enriched_entities"] = [EnrichedCandidate(
        candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
        final_confidence=0.98,
    )]
    state["validation_results"] = [ValidationResult(candidate_id="Battle X", passed=True)]
    state["proposed_diff"] = ProposedDiff(
        run_id="test_1",
        create_entities=[EnrichedCandidate(
            candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
            final_confidence=0.98,
        )],
        create_relations=[],
    )
    new_state = approval_gate(state)
    # event_battle is low risk with threshold 0.90, confidence 0.98 passes
    assert len(new_state["proposed_diff"].create_entities) == 1
    assert len(new_state["proposed_diff"].review_items) == 0
