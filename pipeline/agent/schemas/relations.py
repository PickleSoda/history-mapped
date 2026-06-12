from __future__ import annotations

from pydantic import BaseModel, Field


class CandidateRelation(BaseModel):
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


class CommittedChange(BaseModel):
    change_type: str  # "entity" | "relation"
    record: dict
    committed_at: str
    batch_id: str
