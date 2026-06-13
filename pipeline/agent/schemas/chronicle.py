from __future__ import annotations

from pydantic import BaseModel, Field


class ChronicleEntryEntity(BaseModel):
    entity_id: str
    role: str = "participant"  # participant, mentioned, location, outcome
    sequence_in_entry: int | None = None


class ChronicleEntry(BaseModel):
    sequence_order: int
    primary_relationship_id: str | None = None
    narrative_text: str
    notes: str | None = None
    source_evidence: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    impact_score: int | None = None
    approximate_location: dict | None = None
    secondary_entities: list[ChronicleEntryEntity] = Field(default_factory=list)


class Chronicle(BaseModel):
    title: str
    slug: str
    source_type: str = "video_transcript"
    source_reference: str | None = None
    status: str = "draft"
    start_year: int | None = None
    end_year: int | None = None
    impact_score: int | None = None
    approximate_location: dict | None = None
    metadata: dict = Field(default_factory=dict)
    entries: list[ChronicleEntry] = Field(default_factory=list)
