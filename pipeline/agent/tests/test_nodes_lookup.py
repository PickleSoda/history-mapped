from unittest.mock import patch

from pipeline.agent.graph.nodes.db_lookup import db_lookup
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata
from pipeline.agent.graph.nodes.resolve_ohm import resolve_ohm
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.entities import CandidateEntity, EnrichedCandidate


def make_base_state() -> AgentRunState:
    return {
        "run_id": "test_1",
        "raw_input": "...",
        "parsed_events": [],
        "candidate_entities": [CandidateEntity(label="David IV of Georgia", entity_type="person")],
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


@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
def test_db_lookup_flags_existing(mock_search):
    mock_search.return_value = [
        {
            "entity_id": "E123",
            "name": "David IV of Georgia",
            "entity_type": "person",
            "wikidata_id": "Q405",
        }
    ]
    state = make_base_state()
    new_state = db_lookup(state)
    assert len(new_state["enriched_entities"]) == 1
    assert new_state["enriched_entities"][0].wikidata_match is not None


@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
def test_resolve_wikidata(mock_search, mock_enrich):
    mock_search.return_value = [
        {"qid": "Q405", "label": "David IV of Georgia", "description": "King of Georgia"}
    ]
    mock_enrich.return_value = {
        "Q405": {"label": "David IV of Georgia", "description": "King of Georgia"}
    }
    state = make_base_state()
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="David IV of Georgia", entity_type="person")
        )
    ]
    new_state = resolve_wikidata(state)
    assert new_state["enriched_entities"][0].wikidata_match is not None
    assert new_state["enriched_entities"][0].wikidata_match.get("qid") == "Q405"


@patch("pipeline.agent.graph.nodes.resolve_ohm.Path")
@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_ohm_geometry")
@patch("pipeline.agent.graph.nodes.resolve_ohm.search_ohm_by_wikidata_id")
def test_resolve_ohm(mock_search, mock_geo, mock_path):
    mock_path.return_value.exists.return_value = True
    mock_search.return_value = [{"object_type": "node", "object_id": 123, "name": "Didgori"}]
    mock_geo.return_value = {"type": "Point", "coordinates": [44.5, 41.8]}
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Didgori", entity_type="infrastructure_monument"),
            wikidata_match={"qid": "Q12345"},
        )
    ]
    new_state = resolve_ohm(state)
    assert new_state["enriched_entities"][0].ohm_match is not None
