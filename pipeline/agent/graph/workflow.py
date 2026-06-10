from __future__ import annotations

from langgraph.graph import StateGraph, END

from pipeline.agent.graph.state import AgentRunState
from pipeline.agent.graph.nodes.parse_sequence import parse_sequence
from pipeline.agent.graph.nodes.extract_candidates import extract_candidates
from pipeline.agent.graph.nodes.db_lookup import db_lookup
from pipeline.agent.graph.nodes.resolve_wikidata import resolve_wikidata
from pipeline.agent.graph.nodes.resolve_ohm import resolve_ohm
from pipeline.agent.graph.nodes.generate_content import generate_content
from pipeline.agent.graph.nodes.validate import validate
from pipeline.agent.graph.nodes.build_diff import build_diff
from pipeline.agent.graph.nodes.approval_gate import approval_gate
from pipeline.agent.graph.nodes.commit_writer import commit_writer
from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.nodes.chronicle_writer import chronicle_writer
from pipeline.agent.graph.nodes.audit_logger import audit_logger


def build_workflow() -> StateGraph:
    """Build and return the compiled agent workflow graph."""
    workflow = StateGraph(AgentRunState)

    # Register all nodes
    workflow.add_node("parse_sequence", parse_sequence)
    workflow.add_node("extract_candidates", extract_candidates)
    workflow.add_node("db_lookup", db_lookup)
    workflow.add_node("resolve_wikidata", resolve_wikidata)
    workflow.add_node("resolve_ohm", resolve_ohm)
    workflow.add_node("generate_content", generate_content)
    workflow.add_node("validate", validate)
    workflow.add_node("build_diff", build_diff)
    workflow.add_node("approval_gate", approval_gate)
    workflow.add_node("commit_writer", commit_writer)
    workflow.add_node("chronicle_builder", chronicle_builder)
    workflow.add_node("chronicle_writer", chronicle_writer)
    workflow.add_node("audit_logger", audit_logger)

    # Define edges
    workflow.set_entry_point("parse_sequence")
    workflow.add_edge("parse_sequence", "extract_candidates")
    workflow.add_edge("extract_candidates", "db_lookup")
    workflow.add_edge("db_lookup", "resolve_wikidata")
    workflow.add_edge("resolve_wikidata", "resolve_ohm")
    workflow.add_edge("resolve_ohm", "generate_content")
    workflow.add_edge("generate_content", "validate")
    workflow.add_edge("validate", "build_diff")
    workflow.add_edge("build_diff", "approval_gate")
    workflow.add_edge("approval_gate", "commit_writer")
    workflow.add_edge("commit_writer", "chronicle_builder")
    workflow.add_edge("chronicle_builder", "chronicle_writer")
    workflow.add_edge("chronicle_writer", "audit_logger")
    workflow.add_edge("audit_logger", END)

    return workflow.compile()


def run_agent(raw_input: str, run_id: str) -> AgentRunState:
    """Run the full agent pipeline on a raw text input.

    Returns the final state dict with all artifacts and audit log.
    """
    workflow = build_workflow()
    initial_state: AgentRunState = {
        "run_id": run_id,
        "raw_input": raw_input,
        "parsed_events": [],
        "candidate_entities": [],
        "candidate_relations": [],
        "enriched_entities": [],
        "validation_results": [],
        "proposed_diff": None,
        "committed": [],
        "chronicle": None,
        "audit_log": [],
        "errors": [],
    }
    result = workflow.invoke(initial_state)
    return result
