import json
from pathlib import Path
from unittest.mock import patch

from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.nodes.chronicle_writer import chronicle_writer
from pipeline.agent.graph.nodes import chronicle_writer as cw_mod
from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.schemas.chronicle import Chronicle, ChronicleEntry


def test_chronicle_writer_writes_jsonl(tmp_path, monkeypatch):
    # Patch AgentConfig in the node module so new instances use temp path
    monkeypatch.setattr(cw_mod, "AgentConfig", lambda: AgentConfig(output_dir=str(tmp_path)))

    # Mock successful artisan import
    with patch("pipeline.agent.graph.nodes.chronicle_writer.run_artisan_command") as mock_run:
        mock_run.return_value = {"returncode": 0, "stdout": "Imported", "stderr": ""}

        state: AgentRunState = {
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
            "chronicle": Chronicle(
                title="Test Chronicle",
                slug="test-chronicle",
                entries=[ChronicleEntry(sequence_order=0, narrative_text="Test entry.")],
            ),
        }
        new_state = chronicle_writer(state)

        chronicle_path = tmp_path / "test_1" / "chronicle.json"
        assert chronicle_path.exists()
        data = json.loads(chronicle_path.read_text())
        assert data["title"] == "Test Chronicle"
        assert len(data["entries"]) == 1

        # Check committed log
        assert any(c.change_type == "chronicle" for c in new_state["committed"])
        assert any(a.action == "chronicle_written" for a in new_state["audit_log"])


def test_chronicle_writer_no_chronicle():
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
    new_state = chronicle_writer(state)
    assert new_state == state
