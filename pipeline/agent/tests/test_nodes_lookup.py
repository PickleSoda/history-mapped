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


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_skips_non_polity(mock_resolve):
    # Scope is polities only — a city/monument must not be OHM-resolved (avoids
    # modern-namesake mismatches like Rome OH for ancient Rome).
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Didgori", entity_type="infrastructure_monument"),
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.geo_resolution is None
    assert enriched.ohm_match is None
    mock_resolve.assert_not_called()


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_polity_adopts_ohm_identity(mock_resolve):
    mock_resolve.return_value = {
        "name": "Imperium Romanum Orientale",
        "external_id": "2882342",
        "external_type": "relation",
        "wikidata_id": "Q12544",
        "match_score": 1.0,
        "manifest": {"status": "matched", "geo_ref": {"external_id": "2882342"}},
    }
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Byzantine Empire", entity_type="political_entity"),
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.candidate.label == "Imperium Romanum Orientale"  # polity: OHM name adopted
    assert "Byzantine Empire" in enriched.candidate.aliases
    assert enriched.wikidata_match.get("qid") == "Q12544"
    assert enriched.geo_resolution is not None
