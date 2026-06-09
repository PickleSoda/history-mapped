from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class ParsedEvent(BaseModel):
    label: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    mentioned_entities: list[str] = Field(default_factory=list)
    date_uncertain: bool = False


class CandidateEntity(BaseModel):
    label: str
    entity_type: str
    start_date: str | None = None
    end_date: str | None = None
    source_event: str | None = None
    aliases: list[str] = Field(default_factory=list)
    wikidata_id: str | None = None
    confidence: float = 0.0


class EnrichedCandidate(BaseModel):
    candidate: CandidateEntity
    wikidata_match: dict[str, Any] | None = None
    wikipedia_url: str | None = None
    ohm_match: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    summary: str | None = None
    system_confidence: float = 0.0
    final_confidence: float = 0.0
    validation_errors: list[str] = Field(default_factory=list)
