from __future__ import annotations

from pydantic import BaseModel, Field

from pipeline.agent.schemas.entities import EnrichedCandidate
from pipeline.agent.schemas.relations import CandidateRelation


class ProposedDiff(BaseModel):
    run_id: str
    summary: dict[str, int] = Field(default_factory=dict)
    create_entities: list[EnrichedCandidate] = Field(default_factory=list)
    create_relations: list[CandidateRelation] = Field(default_factory=list)
    review_items: list[dict] = Field(default_factory=list)
    blocked_items: list[dict] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    auto_committed_entities: list[str] = Field(default_factory=list)
    auto_committed_relations: list[str] = Field(default_factory=list)
    flagged_for_review: list[dict] = Field(default_factory=list)
