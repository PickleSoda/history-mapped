from unittest.mock import patch, MagicMock
import json

from pipeline.agent.graph.workflow import build_workflow, run_agent
from pipeline.agent.graph.state import AgentRunState


def test_build_workflow_compiles():
    workflow = build_workflow()
    assert workflow is not None
    graph = workflow.get_graph()
    nodes = {n for n in graph.nodes}
    assert "chronicle_builder" in nodes
    assert "chronicle_writer" in nodes


@patch("pipeline.agent.llm.ChatOpenAI")
@patch("pipeline.agent.graph.nodes.db_lookup.search_entity_by_name")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.search_wikidata_by_name")
@patch("pipeline.agent.graph.nodes.resolve_wikidata.enrich_wikidata_entities")
@patch("pipeline.agent.graph.nodes.resolve_ohm.search_ohm_by_wikidata_id")
@patch("pipeline.agent.graph.nodes.resolve_ohm.search_ohm_by_name")
@patch("pipeline.agent.graph.nodes.commit_writer.run_artisan_command")
def test_run_agent_end_to_end(mock_run, mock_ohm_name, mock_ohm, mock_enrich, mock_wd, mock_db, mock_chat):
    """End-to-end test with all external dependencies mocked."""
    mock_llm = MagicMock()

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        # Call 1: preprocess_transcript (returns cleaned text)
        if call_count[0] == 1:
            return MagicMock(content=json.dumps({
                "cleaned_text": "In 1121, David IV defeated Ilghazi at Didgori."
            }))
        # Call 2: parse_sequence
        elif call_count[0] == 2:
            return MagicMock(content=json.dumps({
                "events": [{"label": "Battle of Didgori", "description": "David IV defeats Ilghazi.", "start_date": "1121-08-12", "end_date": "1121-08-12", "mentioned_entities": ["David IV", "Ilghazi"], "date_uncertain": False}]
            }))
        # Call 3: extract_candidates
        elif call_count[0] == 3:
            return MagicMock(content=json.dumps({
                "candidate_entities": [{"label": "David IV of Georgia", "entity_type": "person", "aliases": ["David IV"]}, {"label": "Battle of Didgori", "entity_type": "event_battle", "start_date": "1121-08-12", "end_date": "1121-08-12"}],
                "candidate_relations": [{"source_label": "David IV of Georgia", "target_label": "Battle of Didgori", "relationship_type": "participated_in", "start_date": "1121-08-12", "end_date": "1121-08-12"}]
            }))
        # Call 4: generate_content
        else:
            return MagicMock(content=json.dumps({
                "summaries": {"David IV of Georgia": "Ruled Georgia from 1089 to 1125."},
                "relation_descriptions": {"David IV of Georgia|participated_in|Battle of Didgori": "Commanded at Didgori."}
            }))

    mock_llm.invoke.side_effect = side_effect
    mock_chat.return_value = mock_llm

    mock_db.return_value = []
    mock_wd.return_value = [{"qid": "Q405", "label": "David IV of Georgia", "description": "King of Georgia"}]
    mock_enrich.return_value = {"Q405": {"label": "David IV of Georgia", "description": "King of Georgia"}}
    mock_ohm.return_value = []
    mock_ohm_name.return_value = []
    mock_run.return_value = {"returncode": 0, "stdout": "OK", "stderr": ""}

    result = run_agent("In 1121, David IV defeated Ilghazi at Didgori.", run_id="e2e_test_1")
    assert result["run_id"] == "e2e_test_1"
    assert len(result["parsed_events"]) == 1
    assert len(result["audit_log"]) > 0
    assert "entity_id_map" in result
    assert "relation_id_map" in result
    assert isinstance(result["entity_id_map"], dict)
    assert isinstance(result["relation_id_map"], dict)
