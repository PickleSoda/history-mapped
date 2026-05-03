"""Relationship mapper — resolves Wikidata properties to history-mapped's 76 relationship types.

This module handles the second pass: after entities are imported into PostgreSQL,
it resolves _relationship_hints (containing Wikidata QIDs) into actual entity_id
references and creates relationship records.

This is used by the Laravel ImportRelationshipsCommand, but is documented here
for reference. The actual resolution happens on the Laravel side since it needs
DB access to look up entity_id by wikidata_id.
"""

from __future__ import annotations

# ── Complete Wikidata property → history-mapped relationship_type mapping ─────────
#
# Bidirectional relationships: Wikidata often stores only one direction.
# The inverse can be derived. The "inverse" column shows what to create
# for the target entity looking back at the source.

WIKIDATA_PROPERTY_MAP: list[dict] = [
    # ── Political ────────────────────────────────────────────────────────────
    {"prop": "P36",   "rel": "capital_of",     "inverse": None,            "category": "political"},
    {"prop": "P1376", "rel": "capital_of",     "inverse": None,            "category": "political"},
    {"prop": "P17",   "rel": "part_of",        "inverse": "contains",      "category": "political"},
    {"prop": "P131",  "rel": "part_of",        "inverse": "contains",      "category": "political"},
    {"prop": "P150",  "rel": "contains",       "inverse": "part_of",       "category": "political"},
    {"prop": "P155",  "rel": "preceded_by",    "inverse": "succeeded_by",  "category": "political"},
    {"prop": "P156",  "rel": "succeeded_by",   "inverse": "preceded_by",   "category": "political"},
    {"prop": "P361",  "rel": "part_of",        "inverse": "contains",      "category": "political"},
    {"prop": "P527",  "rel": "contains",       "inverse": "part_of",       "category": "political"},
    {"prop": "P122",  "rel": "governed_by",    "inverse": None,            "category": "political"},  # gov form, not entity
    {"prop": "P6",    "rel": "governed_by",    "inverse": "rules",         "category": "political"},
    {"prop": "P35",   "rel": "governed_by",    "inverse": "rules",         "category": "political"},

    # ── Person ───────────────────────────────────────────────────────────────
    {"prop": "P19",   "rel": "born_in",        "inverse": None,            "category": "person"},
    {"prop": "P20",   "rel": "died_in",        "inverse": None,            "category": "person"},
    {"prop": "P22",   "rel": "child_of",       "inverse": "parent_of",     "category": "person"},
    {"prop": "P25",   "rel": "child_of",       "inverse": "parent_of",     "category": "person"},
    {"prop": "P26",   "rel": "married_to",     "inverse": "married_to",    "category": "person"},  # symmetric
    {"prop": "P40",   "rel": "parent_of",      "inverse": "child_of",      "category": "person"},
    {"prop": "P39",   "rel": "rules",          "inverse": "governed_by",   "category": "person"},  # position held
    {"prop": "P106",  "rel": "member_of_dynasty", "inverse": None,         "category": "person"},  # rough — occupation

    # ── Military ─────────────────────────────────────────────────────────────
    {"prop": "P607",  "rel": "participated_in", "inverse": None,           "category": "military"},
    {"prop": "P710",  "rel": "participated_in", "inverse": None,           "category": "military"},
    {"prop": "P1344", "rel": "participated_in", "inverse": None,           "category": "military"},

    # ── Economic ─────────────────────────────────────────────────────────────
    {"prop": "P38",   "rel": "used_currency",  "inverse": "minted_by",     "category": "economic"},
    {"prop": "P37",   "rel": "official_religion_of", "inverse": None,      "category": "economic"},  # actually language, contextual

    # ── Cultural ─────────────────────────────────────────────────────────────
    {"prop": "P50",   "rel": "authored",       "inverse": None,            "category": "cultural"},
    {"prop": "P84",   "rel": "built_by",       "inverse": None,            "category": "cultural"},
    {"prop": "P112",  "rel": "founded",        "inverse": None,            "category": "cultural"},
    {"prop": "P170",  "rel": "authored",       "inverse": None,            "category": "cultural"},  # creator
    {"prop": "P86",   "rel": "authored",       "inverse": None,            "category": "cultural"},  # composer
    {"prop": "P282",  "rel": "translated_into","inverse": None,            "category": "cultural"},  # writing system

    # ── Causal ───────────────────────────────────────────────────────────────
    {"prop": "P828",  "rel": "resulted_from",  "inverse": "caused",        "category": "causal"},
    {"prop": "P1542", "rel": "caused",         "inverse": "resulted_from", "category": "causal"},
    {"prop": "P1478", "rel": "caused",         "inverse": "resulted_from", "category": "causal"},  # has immediate cause

    # ── Knowledge ────────────────────────────────────────────────────────────
    {"prop": "P61",   "rel": "invented",       "inverse": None,            "category": "knowledge"},  # discoverer/inventor
    {"prop": "P737",  "rel": "influenced_by",  "inverse": "inspired",      "category": "knowledge"},

    # ── Diplomatic ───────────────────────────────────────────────────────────
    # (Treaty signatories — P710 is shared with military "participant")
    # Resolved by entity_type context: if source is treaty → signed_by, else → participated_in
]

# Index by property for fast lookup
PROPERTY_INDEX: dict[str, list[dict]] = {}
for entry in WIKIDATA_PROPERTY_MAP:
    PROPERTY_INDEX.setdefault(entry["prop"], []).append(entry)


def get_relationship_type(
    wikidata_property: str,
    source_entity_type: str | None = None,
    target_entity_type: str | None = None,
) -> str | None:
    """Resolve a Wikidata property to a history-mapped relationship type.

    Uses entity type context to disambiguate properties like P710 which
    mean different things for battles vs. treaties.
    """
    entries = PROPERTY_INDEX.get(wikidata_property, [])
    if not entries:
        return None

    if len(entries) == 1:
        return entries[0]["rel"]

    # Disambiguate with context
    if source_entity_type == "event_treaty" and wikidata_property == "P710":
        return "signed_by"

    # Default to first match
    return entries[0]["rel"]


def get_inverse(relationship_type: str) -> str | None:
    """Get the inverse relationship type, if one exists."""
    for entry in WIKIDATA_PROPERTY_MAP:
        if entry["rel"] == relationship_type:
            return entry.get("inverse")
    return None


# Symmetric relationship types — store only one direction, query both
SYMMETRIC_TYPES = {
    "married_to",
    "allied_with",
    "sibling_of",
    "trades_with",
    "at_war_with",
}
