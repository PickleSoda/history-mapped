from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import ValidationResult, AuditEvent


def test_parsed_event():
    event = ParsedEvent(
        label="Battle of Didgori",
        description="David IV defeats Ilghazi.",
        start_date="1121-08-12",
        mentioned_entities=["David IV", "Ilghazi"],
    )
    assert event.label == "Battle of Didgori"
    assert event.date_uncertain == False


def test_enriched_candidate():
    candidate = CandidateEntity(label="David IV", entity_type="person")
    enriched = EnrichedCandidate(candidate=candidate, final_confidence=0.95)
    assert enriched.candidate.label == "David IV"
    assert enriched.final_confidence == 0.95


def test_proposed_diff():
    diff = ProposedDiff(run_id="test_1", summary={"entities_to_create": 1})
    assert diff.run_id == "test_1"
    assert diff.summary["entities_to_create"] == 1


def test_validation_result():
    result = ValidationResult(candidate_id="E1", passed=True)
    assert result.passed
    assert result.errors == []
