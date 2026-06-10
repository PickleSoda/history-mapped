"""Workflow orchestrator for the historical entity agentic pipeline.

This module will contain the LangGraph workflow definition and the `run_agent`
entry point. It is currently a stub so that the CLI entry point can be wired up.
"""
from __future__ import annotations


def run_agent(raw_text: str, *, run_id: str) -> dict:
    """Run the agentic pipeline on raw historical text.

    Args:
        raw_text: The raw historical text input.
        run_id: Deterministic run identifier for artifact directory naming.

    Returns:
        A dictionary with pipeline results matching the CLI's expected keys.
    """
    raise NotImplementedError("Agent workflow is not yet implemented.")
