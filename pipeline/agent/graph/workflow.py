from __future__ import annotations

import json
import os
from pathlib import Path
from langgraph.graph import StateGraph, END

from pipeline.agent.log_config import get_logger
from pipeline.agent.config import AgentConfig
from pipeline.agent.graph.state import AgentRunState, empty_state

logger = get_logger(__name__)
from pipeline.agent.graph.nodes.preprocess_transcript import preprocess_transcript
from pipeline.agent.graph.nodes.parse_sequence import parse_sequence
from pipeline.agent.graph.nodes.extract_candidates import extract_candidates
from pipeline.agent.graph.nodes.completeness_critic import completeness_critic, route_after_critic
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
from pipeline.agent.graph.node_wrapper import with_error_capture
from langgraph.checkpoint.memory import MemorySaver


def build_workflow(entry_point: str = "full") -> StateGraph:
    """Build and return the compiled agent workflow graph.

    entry_point="full" (default): complete graph starting at preprocess_transcript.
    entry_point="tail": starts at db_lookup — handoff runs where the LLM stages
    already executed offline (--from-candidates). Upstream nodes stay registered
    but are never reached from the tail entry point.
    """
    if entry_point not in ("full", "tail"):
        raise ValueError(f"Unknown entry_point: {entry_point!r} (expected 'full' or 'tail')")
    workflow = StateGraph(AgentRunState)

    # Register all nodes with error capture wrapper
    workflow.add_node("preprocess_transcript", with_error_capture(preprocess_transcript))
    workflow.add_node("parse_sequence", with_error_capture(parse_sequence))
    workflow.add_node("extract_candidates", with_error_capture(extract_candidates))
    workflow.add_node("completeness_critic", with_error_capture(completeness_critic))
    workflow.add_node("db_lookup", with_error_capture(db_lookup))
    workflow.add_node("resolve_wikidata", with_error_capture(resolve_wikidata))
    workflow.add_node("resolve_ohm", with_error_capture(resolve_ohm))
    workflow.add_node("generate_content", with_error_capture(generate_content))
    workflow.add_node("validate", with_error_capture(validate))
    workflow.add_node("build_diff", with_error_capture(build_diff))
    workflow.add_node("approval_gate", with_error_capture(approval_gate))
    workflow.add_node("commit_writer", with_error_capture(commit_writer))
    workflow.add_node("resolve_entity_ids", with_error_capture(resolve_entity_ids))
    workflow.add_node("chronicle_builder", with_error_capture(chronicle_builder))
    workflow.add_node("chronicle_writer", with_error_capture(chronicle_writer))
    workflow.add_node("audit_logger", with_error_capture(audit_logger))

    # Define edges
    workflow.set_entry_point(
        "preprocess_transcript" if entry_point == "full" else "db_lookup"
    )
    workflow.add_edge("preprocess_transcript", "parse_sequence")
    workflow.add_edge("parse_sequence", "extract_candidates")
    workflow.add_edge("extract_candidates", "completeness_critic")
    # Bounded recall loop: re-read the transcript for missed entities/relations,
    # looping until a pass finds nothing new (or the cap is hit), then enrich.
    workflow.add_conditional_edges(
        "completeness_critic",
        route_after_critic,
        {"loop": "completeness_critic", "done": "db_lookup"},
    )
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

    # Compile with checkpointer for resumability
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


def run_agent(raw_input: str, run_id: str, title: str | None = None, create_chronicle: bool = True,
              refresh: bool = False) -> AgentRunState:
    """Run the full agent pipeline on a raw text input.

    Parameters
    ----------
    raw_input: The historical text to process.
    run_id: Unique identifier for this run.
    title: Optional chronicle title (defaults to derived from input).
    create_chronicle: Whether to build a chronicle from the events.
    refresh: Re-resolve every entity (type/QID/geo/date) and force-update existing
        rows in place, preserving entity_id and relationships. Also bypasses the
        already-completed short-circuit below so a prior clean run is redone.

    Returns
    -------
    The final state dict with all artifacts and audit log.
    """
    cfg = AgentConfig()
    workflow = build_workflow()

    # Check for idempotency - if manifest exists with no errors, short-circuit.
    # Refresh mode intentionally re-runs even a previously-clean transcript.
    output_root = Path(cfg.output_dir) / run_id
    manifest_path = output_root / "manifest.json"
    if not refresh and manifest_path.exists():
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
                "critic_iterations": 0,
                "critic_done": True,
            }

    initial_state = empty_state(run_id, raw_input, title=title,
                                create_chronicle=create_chronicle, refresh=refresh)
    result = workflow.invoke(initial_state, config={"configurable": {"thread_id": run_id}})
    logger.info("Workflow complete: run_id=%s errors=%d committed=%d chronicle=%s",
                run_id, len(result.get("errors", [])), len(result.get("committed", [])),
                result.get("chronicle") is not None)
    return result


def run_agent_from_candidates(handoff_path, run_id=None, create_chronicle=True,
                              refresh=False) -> AgentRunState:
    """Run the deterministic tail from an opencode-authored handoff file.

    Idempotency mirrors run_agent(): a clean existing manifest short-circuits.
    """
    # Imported here, not at module top: handoff -> graph.state triggers this
    # package's __init__, which imports workflow — a module-top import would be
    # circular (workflow suspended mid-import when graph/__init__ asks for it).
    from pipeline.agent.handoff import hydrate_state, load_handoff

    cfg = AgentConfig()
    doc = load_handoff(handoff_path)
    run_id = run_id or doc.run_id

    output_root = Path(cfg.output_dir) / run_id
    manifest_path = output_root / "manifest.json"
    if not refresh and manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        if manifest.get("errors_count", 0) == 0:
            logger.info("Run %s already completed successfully, skipping", run_id)
            return {"run_id": run_id, "raw_input": "", "parsed_events": doc.parsed_events,
                    "candidate_entities": doc.candidate_entities,
                    "candidate_relations": doc.candidate_relations,
                    "enriched_entities": [], "validation_results": [],
                    "proposed_diff": None, "committed": [], "chronicle": None,
                    "audit_log": [], "errors": [], "title": doc.title,
                    "create_chronicle": create_chronicle, "entity_id_map": {},
                    "relation_id_map": {}, "critic_iterations": 0, "critic_done": True}

    raw_input = ""
    if doc.source_transcript and os.path.exists(doc.source_transcript):
        raw_input = Path(doc.source_transcript).read_text(encoding="utf-8")

    initial_state = hydrate_state(doc, raw_input=raw_input,
                                  create_chronicle=create_chronicle, refresh=refresh)
    initial_state["run_id"] = run_id

    workflow = build_workflow(entry_point="tail")
    result = workflow.invoke(initial_state, config={"configurable": {"thread_id": run_id}})
    logger.info("Handoff workflow complete: run_id=%s errors=%d committed=%d",
                run_id, len(result.get("errors", [])), len(result.get("committed", [])))
    return result
