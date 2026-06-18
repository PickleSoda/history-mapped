from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Any

# LLMs emit year fields as JSON numbers (start_date: -331) as often as strings;
# coerce them so a bare integer doesn't raise a ValidationError and sink the node.
_COERCE = ConfigDict(coerce_numbers_to_str=True)

# The canonical 30-type taxonomy (must mirror validate.ALLOWED_ENTITY_TYPES /
# commit_writer.ENTITY_TYPE_TO_GROUP). Kept here so candidates normalise to it at
# construction.
_CANONICAL_ENTITY_TYPES = {
    # POLITY
    "political_entity", "dynasty", "person", "military_unit",
    "diplomatic_relationship", "social_class",
    # PLACE
    "city", "infrastructure_monument", "extraction_infra", "educational_institution",
    # EVENT
    "event_war", "event_battle", "event_treaty", "event_rebellion",
    "event_natural_disaster", "event_tech_adoption", "event_legal_reform",
    "migration", "epidemic_disease",
    # ECONOMY
    "trade_route", "natural_resource", "currency_monetary_system",
    # CULTURE
    "cultural_work", "intellectual_movement", "archaeological_culture",
    "language", "religious_text", "legal_code", "religious_movement", "technology",
}

# Generic / synonym entity types the LLM emits despite the prompt (≈20% of
# candidates), all of which validate.ALLOWED_ENTITY_TYPES would otherwise drop —
# silently blocking backbone entities (Roman Empire="state", Christianity=
# "religion", Italy="place") and cascading into unresolved relations. Map them to
# the canonical type. Countries / regions / territories have no dedicated type, so
# they become political_entity (which geocodes and takes part_of / spread_to
# relations) rather than city.
_TYPE_SYNONYMS = {
    "polity": "political_entity",
    "state": "political_entity",
    "country": "political_entity",
    "nation": "political_entity",
    "empire": "political_entity",
    "kingdom": "political_entity",
    "republic": "political_entity",
    "civilization": "political_entity",
    "civilisation": "political_entity",
    "place": "political_entity",
    "region": "political_entity",
    "territory": "political_entity",
    "province": "political_entity",
    "religion": "religious_movement",
    "philosophical_movement": "intellectual_movement",
    "philosophy": "intellectual_movement",
    "school_of_thought": "intellectual_movement",
    "ideology": "intellectual_movement",
    "disease": "epidemic_disease",
    "plague": "epidemic_disease",
    "pandemic": "epidemic_disease",
    "monument": "infrastructure_monument",
    "building": "infrastructure_monument",
    "university": "educational_institution",
    "school": "educational_institution",
    "currency": "currency_monetary_system",
    "coin": "currency_monetary_system",
    "law": "legal_code",
}

# Bare event-ish types: resolve to a specific EVENT type by the label's keyword
# ("Battle of Philippi" → event_battle, "Punic Wars" → event_war).
_GENERIC_EVENT_TYPES = {"event", "war", "battle", "siege", "conflict", "campaign",
                        "rebellion", "revolt", "uprising", "treaty", "disaster"}


def normalize_entity_type(raw: str, label: str = "") -> str:
    """Coerce an LLM-emitted entity_type into the canonical taxonomy.

    Returns the canonical type, or the cleaned original when no mapping applies
    (validate then blocks genuinely-unknown types such as 'historical_period').
    """
    t = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if t in _CANONICAL_ENTITY_TYPES:
        return t
    if t in _TYPE_SYNONYMS:
        return _TYPE_SYNONYMS[t]
    if t in _GENERIC_EVENT_TYPES:
        lab = (label or "").lower()
        if "battle" in lab or "siege" in lab:
            return "event_battle"
        if "rebellion" in lab or "revolt" in lab or "uprising" in lab:
            return "event_rebellion"
        if "treaty" in lab or "edict" in lab or "peace of" in lab:
            return "event_treaty"
        if t in ("battle", "siege"):
            return "event_battle"
        if t in ("rebellion", "revolt", "uprising"):
            return "event_rebellion"
        if t == "treaty":
            return "event_treaty"
        if t == "disaster":
            return "event_natural_disaster"
        return "event_war"  # war / conflict / campaign / bare "event"
    return t


class ParsedEvent(BaseModel):
    model_config = _COERCE

    label: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    mentioned_entities: list[str] = Field(default_factory=list)
    date_uncertain: bool = False


class CandidateEntity(BaseModel):
    model_config = _COERCE

    label: str
    entity_type: str
    start_date: str | None = None
    end_date: str | None = None
    source_event: str | None = None
    aliases: list[str] = Field(default_factory=list)
    wikidata_id: str | None = None
    confidence: float = 0.0

    @model_validator(mode="after")
    def _canonicalize_entity_type(self) -> "CandidateEntity":
        # Normalise generic/synonym types (label-aware for bare events) so the
        # extractor's and critic's drift into "polity"/"place"/"religion"/"event"
        # doesn't get the entity silently blocked at validation.
        self.entity_type = normalize_entity_type(self.entity_type, self.label)
        return self


class EnrichedCandidate(BaseModel):
    candidate: CandidateEntity
    wikidata_match: dict[str, Any] | None = None
    wikipedia_url: str | None = None
    ohm_match: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    # `_geo_resolution` manifest (OHM Nominatim) for the Laravel geo-ref importer.
    geo_resolution: dict[str, Any] | None = None
    summary: str | None = None
    significance: str | None = None
    system_confidence: float = 0.0
    final_confidence: float = 0.0
    validation_errors: list[str] = Field(default_factory=list)
    existing_entity: bool = False  # Set by db_lookup when entity already exists
