from __future__ import annotations

from typing import TypedDict, Any

from pipeline.agent.schemas.chronicle import Chronicle
from pipeline.agent.schemas.entities import ParsedEvent, CandidateEntity, EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation, CommittedChange
from pipeline.agent.schemas.proposals import ProposedDiff
from pipeline.agent.schemas.validation import ValidationResult, PipelineError, AuditEvent


class AgentRunState(TypedDict):
    run_id: str
    raw_input: str
    date_hints: list[dict[str, str]]
    parsed_events: list[ParsedEvent]
    candidate_entities: list[CandidateEntity]
    candidate_relations: list[CandidateRelation]
    enriched_entities: list[EnrichedCandidate]
    validation_results: list[ValidationResult]
    proposed_diff: ProposedDiff | None
    # NOTE: These three are accumulators. The graph is strictly linear and every
    # node mutates the carried-forward state in place and returns the FULL state,
    # so the default "replace" channel semantics already accumulate correctly.
    # Do NOT add an operator.add reducer here — combined with full-state returns
    # it concatenates the already-accumulated list onto itself at every node,
    # doubling it per node (exponential blow-up). See test_state_reducers.py.
    committed: list[CommittedChange]
    audit_log: list[AuditEvent]
    errors: list[PipelineError]
    chronicle: Chronicle | None
    title: str | None
    create_chronicle: bool
    refresh: bool
    entity_id_map: dict[str, str]
    relation_id_map: dict[str, str]
    # Completeness-critic recall loop (F6): how many critic passes have run, and
    # whether the loop is finished (no new items found, or the cap was hit).
    critic_iterations: int
    critic_done: bool
    # Handoff mode (--from-candidates): pre-generated summaries keyed by entity
    # label, plus the flag telling generate_content to skip its LLM calls.
    summaries: dict[str, dict[str, str]]
    summaries_precomputed: bool


def empty_state(run_id: str, raw_input: str, title: str | None = None,
                create_chronicle: bool = True, refresh: bool = False) -> AgentRunState:
    """Fresh AgentRunState with every channel initialised.

    Single source of truth for every entry point (run_agent,
    run_agent_from_candidates, handoff hydration): graph nodes read channels
    straight off this dict at runtime, so a key missing here surfaces as a
    KeyError mid-run instead of at construction — and per-entry-point copies
    can't drift apart as the TypedDict grows.
    """
    return {
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
        "refresh": refresh,
        "entity_id_map": {},
        "relation_id_map": {},
        "critic_iterations": 0,
        "critic_done": False,
        "summaries": {},
        "summaries_precomputed": False,
    }
