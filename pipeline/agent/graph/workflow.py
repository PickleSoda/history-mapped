from __future__ import annotations

import json
from pathlib import Path
from langgraph.graph import StateGraph, END

from pipeline.agent.log_config import get_logger
from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState

logger = get_logger(__name__)
from pipeline.agent.graph.nodes.preprocess_transcript import preprocess_transcript
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
from pipeline.agent.graph.nodes.resolve_entity_ids import resolve_entity_ids
from pipeline.agent.graph.nodes.chronicle_builder import chronicle_builder
from pipeline.agent.graph.nodes.chronicle_writer import chronicle_writer
from pipeline.agent.graph.nodes.audit_logger import audit_logger


def build_workflow() -> StateGraph:
    """Build and return the compiled agent workflow graph."""
    workflow = StateGraph(AgentRunState)

    # Register all nodes
    workflow.add_node("preprocess_transcript", preprocess_transcript)
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
    workflow.add_node("resolve_entity_ids", resolve_entity_ids)
    workflow.add_node("chronicle_builder", chronicle_builder)
    workflow.add_node("chronicle_writer", chronicle_writer)
    workflow.add_node("audit_logger", audit_logger)

    # Define edges
    workflow.set_entry_point("preprocess_transcript")
    workflow.add_edge("preprocess_transcript", "parse_sequence")
    workflow.add_edge("parse_sequence", "extract_candidates")
    workflow.add_edge("extract_candidates", "db_lookup")
    workflow.add_edge("db_lookup", "resolve_wikidata")
    workflow.add_edge("resolve_wikidata", "resolve_ohm")
    workflow.add_edge("resolve_ohm", "generate_content")
    workflow.add_edge("generate_content", "validate")
    workflow.add_edge("validate", "build_diff")
    workflow.add_edge("build_diff", "approval_gate")
    workflow.add_edge("approval_gate", "commit_writer")
    workflow.add_edge("commit_writer", "resolve_entity_ids")
    workflow.add_edge("resolve_entity_ids", "chronicle_builder")
    workflow.add_edge("chronicle_builder", "chronicle_writer")
    workflow.add_edge("chronicle_writer", "audit_logger")
    workflow.add_edge("audit_logger", END)

    return workflow.compile()


def run_agent(raw_input: str, run_id: str, title: str | None = None, create_chronicle: bool = True) -> AgentRunState:
    """Run the full agent pipeline on a raw text input.

    Parameters
    ----------
    raw_input: The historical text to process.
    run_id: Unique identifier for this run.
    title: Optional chronicle title (defaults to derived from input).
    create_chronicle: Whether to build a chronicle from the events.

    Returns
    -------
    The final state dict with all artifacts and audit log.
    """
    cfg = AgentConfig()
    workflow = build_workflow()

    # Check for idempotency - if manifest exists with no errors, short-circuit
    output_root = Path(cfg.output_dir) / run_id
    manifest_path = output_root / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        if manifest.get("errors_count", 0) == 0:
            logger.info("Run %s already completed successfully, skipping", run_id)
            # Return a minimal valid state so callers can check result keys
            return {
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
                "title": title,
                "create_chronicle": create_chronicle,
                "entity_id_map": {},
                "relation_id_map": {},
            }

    initial_state: AgentRunState = {
        "run_id": run_id,
        "raw_input": raw_input,
        "date_hints": [],
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
        "title": title,
        "create_chronicle": create_chronicle,
        "entity_id_map": {},
        "relation_id_map": {},
    }
    result = workflow.invoke(initial_state)
    logger.info("Workflow complete: run_id=%s errors=%d committed=%d chronicle=%s",
                run_id, len(result.get("errors", [])), len(result.get("committed", [])),
                result.get("chronicle") is not None)
    return result
