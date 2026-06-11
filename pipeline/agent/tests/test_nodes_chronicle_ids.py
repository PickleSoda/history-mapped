from unittest.mock import patch

from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.relations import CommittedChange
from datetime import datetime, timezone


def test_resolve_entity_ids_returns_empty_maps_on_no_commits():
    """When nothing is committed, maps should be empty."""
    state: AgentRunState = {
        "run_id": "test",
        "raw_input": "",
        "date_hints": [],
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
    result = resolve_entity_ids(state)
    assert result["entity_id_map"] == {}
    assert result["relation_id_map"] == {}


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_relationship_by_labels")
def test_resolve_entity_ids_maps_committed_entities(mock_search_rel, mock_search_ent):
    """Committed entities should be looked up and mapped by name."""
    mock_search_ent.return_value = [{
        "entity_id": "ent_david_001",
        "name": "David IV of Georgia",
        "entity_type": "person",
        "wikidata_id": "Q405",
    }]
    mock_search_rel.return_value = []

    state: AgentRunState = {
        "run_id": "test",
        "raw_input": "",
        "date_hints": [],
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [
            CommittedChange(
                change_type="entity",
                record={"name": "David IV of Georgia", "count": 1, "path": "/tmp/test.jsonl", "result": {"returncode": 0}},
                committed_at=datetime.now(timezone.utc).isoformat(),
                batch_id="test",
            ),
        ],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }
    result = resolve_entity_ids(state)
    assert result["entity_id_map"] == {"David IV of Georgia": "ent_david_001"}
    assert result["relation_id_map"] == {}


@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_entity_ids.search_relationship_by_labels")
def test_resolve_entity_ids_maps_relations(mock_search_rel, mock_search_ent):
    """Committed relations should be looked up and mapped by source|type|target key."""
    mock_search_ent.return_value = []
    mock_search_rel.return_value = [{
        "relationship_id": "rel_001",
        "source_id": "src_001",
        "target_id": "tgt_001",
        "relationship_type": "fought_at",
    }]

    state: AgentRunState = {
        "run_id": "test",
        "raw_input": "",
        "date_hints": [],
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [
            CommittedChange(
                change_type="relation",
                record={
                    "source_label": "Alexander",
                    "target_label": "Darius III",
                    "relationship_type": "fought_at",
                    "relationship_id": "Alexander|fought_at|Darius III",
                    "count": 1,
                    "path": "/tmp/test.jsonl",
                    "result": {"returncode": 0},
                },
                committed_at=datetime.now(timezone.utc).isoformat(),
                batch_id="test",
            ),
        ],
        "audit_log": [],
        "errors": [],
        "entity_id_map": {},
        "relation_id_map": {},
    }
    result = resolve_entity_ids(state)
    assert result["relation_id_map"] == {"Alexander|fought_at|Darius III": "rel_001"}
    assert result["entity_id_map"] == {}