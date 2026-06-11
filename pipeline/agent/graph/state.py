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
    committed: list[CommittedChange]
    audit_log: list[AuditEvent]
    errors: list[PipelineError]
    chronicle: Chronicle | None
    title: str | None
    create_chronicle: bool
