"""Regression tests for state-channel accumulation.

The agent graph is strictly linear and every node mutates the state in place
and returns the *full* state dict. If the accumulator channels (audit_log,
committed, errors) use an ``operator.add`` reducer, LangGraph concatenates the
returned (already-accumulated) list onto the existing channel value, doubling
it at every node — an exponential blow-up that produced 65k audit entries and
an 11 MB manifest on real runs.

These tests pin the invariant: N nodes that each append one item must yield
exactly N items, not 2**N - 1.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.graph.node_wrapper import with_error_capture
from pipeline.agent.schemas.validation import AuditEvent, PipelineError
from pipeline.agent.schemas.relations import CommittedChange


def _blank_state() -> AgentRunState:
    return {
        "run_id": "reducer_test",
        "raw_input": "x",
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
        "chronicle": None,
        "title": None,
        "create_chronicle": False,
        "entity_id_map": {},
        "relation_id_map": {},
    }


def _make_appender(name: str):
    def fn(state: AgentRunState) -> AgentRunState:
        state["audit_log"].append(
            AuditEvent(timestamp="t", node=name, action="a", output_summary=name)
        )
        state["committed"].append(
            CommittedChange(
                change_type="entity",
                record={"name": name},
                committed_at="t",
                batch_id="b",
            )
        )
        return state

    return fn


def _three_node_graph(node_factory):
    g = StateGraph(AgentRunState)
    g.add_node("a", node_factory("a"))
    g.add_node("b", node_factory("b"))
    g.add_node("c", node_factory("c"))
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", END)
    return g.compile()


def test_accumulators_do_not_duplicate_across_linear_nodes():
    app = _three_node_graph(_make_appender)
    result = app.invoke(_blank_state())
    # Exactly one per node — NOT 7 (1 + 2 + 4) from operator.add doubling.
    assert len(result["audit_log"]) == 3, result["audit_log"]
    assert len(result["committed"]) == 3, result["committed"]


def test_error_wrapper_preserves_prior_errors_and_full_state():
    """A wrapped node that throws must append its error while keeping the
    other channels intact (replace semantics: it returns the full state)."""

    def good(state: AgentRunState) -> AgentRunState:
        state["errors"].append(
            PipelineError(node="good", error_type="Seed", message="prior")
        )
        state["audit_log"].append(
            AuditEvent(timestamp="t", node="good", action="a", output_summary="g")
        )
        return state

    def boom(state: AgentRunState) -> AgentRunState:
        raise ValueError("kaboom")

    g = StateGraph(AgentRunState)
    g.add_node("good", with_error_capture(good))
    g.add_node("boom", with_error_capture(boom))
    g.set_entry_point("good")
    g.add_edge("good", "boom")
    g.add_edge("boom", END)
    app = g.compile()

    result = app.invoke(_blank_state())
    # Prior error preserved + new error appended (no duplication, no wipe).
    assert len(result["errors"]) == 2, result["errors"]
    assert result["errors"][0].message == "prior"
    assert "kaboom" in result["errors"][1].message
    # The good node's audit entry survived the boom node's failure.
    assert len(result["audit_log"]) == 1, result["audit_log"]
