from __future__ import annotations
from pipeline.agent.graph.state import AgentRunState


def messy_research(state: AgentRunState) -> AgentRunState:
    """Stub for post-MVP DeepAgent node.

    This node will perform deep research on ambiguous entities using
    multi-step reasoning, web search, and cross-referencing.
    For MVP, it simply passes through the state unchanged.
    """
    return state
