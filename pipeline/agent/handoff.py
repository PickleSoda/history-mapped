"""Handoff-file loading for opencode-authored extractions.

An opencode session performs the graph's LLM stages offline (parse_sequence,
extract_candidates, completeness_critic, generate_content summaries) and writes
a candidates.json handoff file. load_handoff validates it against the pipeline
schemas; hydrate_state builds an AgentRunState ready for the deterministic tail
(db_lookup onward) via build_workflow(entry_point="tail").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pipeline.agent.graph.state import AgentRunState, empty_state
from pipeline.agent.schemas.entities import CandidateEntity, ParsedEvent
from pipeline.agent.schemas.relations import CandidateRelation


class HandoffDocument(BaseModel):
    run_id: str
    source_transcript: str | None = None
    title: str | None = None
    summaries_precomputed: bool = False
    parsed_events: list[ParsedEvent] = Field(default_factory=list)
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)
    candidate_relations: list[CandidateRelation] = Field(default_factory=list)
    summaries: dict[str, dict[str, str]] = Field(default_factory=dict)
    self_audit: dict[str, Any] = Field(default_factory=dict)


def load_handoff(path: str | Path) -> HandoffDocument:
    return HandoffDocument.model_validate_json(Path(path).read_text(encoding="utf-8"))


def hydrate_state(
    doc: HandoffDocument,
    raw_input: str,
    create_chronicle: bool = True,
    refresh: bool = False,
) -> AgentRunState:
    """Build a complete AgentRunState from a validated handoff document."""
    state = empty_state(doc.run_id, raw_input, title=doc.title,
                        create_chronicle=create_chronicle, refresh=refresh)
    state["parsed_events"] = doc.parsed_events
    state["candidate_entities"] = doc.candidate_entities
    state["candidate_relations"] = doc.candidate_relations
    state["critic_iterations"] = int(doc.self_audit.get("critic_iterations", 0))
    state["critic_done"] = True
    state["summaries"] = doc.summaries
    state["summaries_precomputed"] = doc.summaries_precomputed
    return state
