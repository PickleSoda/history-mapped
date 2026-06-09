from unittest.mock import patch
from pathlib import Path
import json
from pipeline.agent.graph.nodes.commit_writer import commit_writer
from pipeline.agent.graph.nodes.audit_logger import audit_logger
from pipeline.agent.graph.nodes.messy_research import messy_research
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import ValidationResult


def make_base_state() -> AgentRunState:
    return {
        "run_id": "test_run_1",
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
    }


@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
def test_commit_writer_writes_jsonl(mock_run):
    mock_run.return_value = {"returncode": 0, "stdout": "Imported 1", "stderr": ""}
    state = make_base_state()
    state["enriched_entities"] = [EnrichedCandidate(
        candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
        final_confidence=0.98,
        summary="A battle.",
        wikidata_match={"qid": "Q999"},
    )]
    state["proposed_diff"] = ProposedDiff(
        run_id="test_run_1",
        create_entities=[EnrichedCandidate(
            candidate=CandidateEntity(label="Battle X", entity_type="event_battle"),
            final_confidence=0.98,
            summary="A battle.",
            wikidata_match={"qid": "Q999"},
        )],
        create_relations=[],
    )
    new_state = commit_writer(state)
    assert len(new_state["committed"]) > 0
    # Check that files were written
    output_dir = Path("output/agent_runs/test_run_1")
    assert (output_dir / "entities_to_create.jsonl").exists()


def test_audit_logger_writes_manifest():
    state = make_base_state()
    state["audit_log"].append(ValidationResult(candidate_id="x", passed=True))  # wrong type but ok for test
    new_state = audit_logger(state)
    output_dir = Path("output/agent_runs/test_run_1")
    assert (output_dir / "manifest.json").exists()
    with open(output_dir / "manifest.json") as f:
        manifest = json.load(f)
    assert manifest["run_id"] == "test_run_1"


def test_messy_research_passthrough():
    state = make_base_state()
    new_state = messy_research(state)
    assert new_state["run_id"] == state["run_id"]
