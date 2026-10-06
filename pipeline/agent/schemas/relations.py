from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CandidateRelation(BaseModel):
    # Coerce numeric year fields (start_date: -331) emitted by the LLM to strings.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    source_label: str
    target_label: str
    relationship_type: str
    start_date: str | None = None
    end_date: str | None = None
    source_event: str | None = None
    description: str | None = None
    confidence: float = 0.0
    final_confidence: float = 0.0
    source_wikidata_id: str | None = None
    target_wikidata_id: str | None = None
    # Set only by approval_gate (it resets any other value): a reviewed campaign
    # relation committed below its predicate's auto-commit threshold is imported
    # with this relationships.confidence level. Excluded from dumps, so handoff
    # files (candidates.json) never carry it.
    commit_confidence: str | None = Field(default=None, exclude=True)


class CommittedChange(BaseModel):
    change_type: str  # "entity" | "relation"
    record: dict
    committed_at: str
    batch_id: str
