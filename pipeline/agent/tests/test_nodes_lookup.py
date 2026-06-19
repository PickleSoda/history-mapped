from unittest.mock import patch

from pipeline.agent.graph.nodes.db_lookup import db_lookup
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata, _sign_corrected
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


def test_sign_corrected_flips_ce_to_bce():
    # LLM emitted "750 CE" but Wikidata says -0750: same magnitude, opposite sign.
    assert _sign_corrected("750 CE", "-0750-01-01T00:00:00Z") == "-0750-01-01T00:00:00Z"
    assert _sign_corrected("331 BCE", "+0331-01-01T00:00:00Z") == "+0331-01-01T00:00:00Z"


def test_sign_corrected_leaves_genuine_differences_and_blanks():
    # Different magnitude (birth vs reign) → no correction.
    assert _sign_corrected("100 BCE", "-0044-01-01T00:00:00Z") is None
    # Agreeing dates → no correction.
    assert _sign_corrected("-331", "-0331-01-01T00:00:00Z") is None
    # Missing either side → no correction.
    assert _sign_corrected(None, "-0331") is None
    assert _sign_corrected("331 BCE", None) is None


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_resolves_place_types(mock_resolve):
    # Places (cities/monuments) ARE OHM-resolved now — the qid anchor + era guard
    # against modern-namesake mismatches (Rome OH). Geometry only; name preserved.
    mock_resolve.return_value = {
        "name": "Tbilisi",
        "external_id": "12345",
        "external_type": "relation",
        "wikidata_id": "Q994",
        "match_score": 0.9,
        "manifest": {"status": "matched", "geo_ref": {"provider": "ohm"}},
    }
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Tbilisi", entity_type="city"),
            wikidata_match={"qid": "Q994"},
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.geo_resolution is not None
    assert enriched.ohm_match == {"object_type": "relation", "object_id": "12345"}
    assert enriched.candidate.label == "Tbilisi"  # place name preserved (not a polity)
    mock_resolve.assert_called_once()


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_event_always_gets_a_point(mock_resolve):
    # Events (wars/battles) must land a point: OHM-less here, so the Wikidata
    # coordinate fallback applies — and the event keeps its own name.
    mock_resolve.return_value = None
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Franco-Prussian War", entity_type="event_war"),
            wikidata_match={"qid": "Q156311", "coordinates": "Point(2 48)"},
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.geo_resolution is not None
    assert enriched.geo_resolution["geometry"]["coordinates"] == [2.0, 48.0]
    assert enriched.candidate.label == "Franco-Prussian War"  # event name preserved


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_polity_keeps_name_records_ohm_alias(mock_resolve):
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
    # Readable display name kept; OHM's canonical form recorded as an alias.
    assert enriched.candidate.label == "Byzantine Empire"
    assert "Imperium Romanum Orientale" in enriched.candidate.aliases
    assert enriched.wikidata_match.get("qid") == "Q12544"  # OHM's id/qid still adopted
    assert enriched.geo_resolution is not None


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_falls_back_to_wikidata_point(mock_resolve):
    # OHM has no feature (Persian Empire, Nabataean Kingdom) -> approximate point.
    mock_resolve.return_value = None
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Nabataean Kingdom", entity_type="political_entity"),
            wikidata_match={"qid": "Q11029653", "coordinates": "Point(35.44 30.33)"},
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.geo_resolution is not None
    assert enriched.geo_resolution["provenance"]["resolver"] == "wikidata_coords"
    assert enriched.geo_resolution["geometry"]["coordinates"] == [35.44, 30.33]
    assert enriched.candidate.label == "Nabataean Kingdom"  # fallback never renames


@patch("pipeline.agent.graph.nodes.resolve_ohm.resolve_polity")
def test_resolve_ohm_keeps_readable_name_over_non_latin_ohm_name(mock_resolve):
    # OHM's Achaemenid feature is named in cuneiform; keep the readable name.
    mock_resolve.return_value = {
        "name": "\U000103a7\U000103c2\U000103c2",  # cuneiform glyphs
        "external_id": "2099900308", "external_type": "node",
        "wikidata_id": None, "match_score": 0.6,
        "manifest": {"status": "matched", "geo_ref": {"external_id": "2099900308"}},
    }
    state = make_base_state()
    state["candidate_entities"] = []
    state["enriched_entities"] = [
        EnrichedCandidate(
            candidate=CandidateEntity(label="Achaemenid Dynasty", entity_type="dynasty"),
        )
    ]
    new_state = resolve_ohm(state)
    enriched = new_state["enriched_entities"][0]
    assert enriched.candidate.label == "Achaemenid Dynasty"  # non-Latin name not adopted
    assert enriched.geo_resolution is not None  # geometry/id still attached
