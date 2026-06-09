from typing import get_type_hints

from pipeline.agent.graph.state import AgentRunState


def test_state_is_typed_dict():
    hints = get_type_hints(AgentRunState)
    assert "run_id" in hints
    assert "raw_input" in hints
    assert "parsed_events" in hints
