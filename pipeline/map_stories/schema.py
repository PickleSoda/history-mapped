"""The map-story document vocabulary (schema 1).

Mirrors web/src/lib/schemas/map-story.ts and api/app/Support/MapStory/
MapStoryDocument.php; change all three together. The authoring guide
(docs/implementation-docs/map-story-authoring.md) explains each field.
"""

SCHEMA_VERSION = 1

STORY_KINDS = ("battle", "naval_battle", "siege", "campaign")

UNIT_KINDS = (
    # foot
    "infantry",
    "heavy_infantry",
    "light_infantry",
    "pikemen",
    "archers",
    "slingers",
    "crossbowmen",
    "musketeers",
    # mounted
    "cavalry",
    "heavy_cavalry",
    "light_cavalry",
    "horse_archers",
    "chariots",
    "elephants",
    "camels",
    # support
    "artillery",
    "siege_engine",
    # naval
    "warship",
    "transport",
    # point markers
    "commander",
    "camp",
    "baggage",
)

#: Kinds drawn as a single marker (no formation block).
POINT_UNIT_KINDS = ("commander", "camp", "baggage")

SHAPES = ("block", "line", "column", "wedge", "crescent", "square", "circle")

UNIT_STATES = ("ready", "engaged", "wavering", "routed", "destroyed", "hidden")

MOVE_TYPES = ("advance", "attack", "charge", "flank", "feint", "retreat", "rout", "pursuit", "march", "fire")

NOTE_KINDS = ("label", "clash", "death", "capture", "event")

TERRAIN_KINDS = {
    # point features
    "town": "at",
    "village": "at",
    "farm": "at",
    "building": "at",
    "bridge": "at",
    "pass": "at",
    "label": "at",
    # line features
    "river": "line",
    "stream": "line",
    "road": "line",
    "ridge": "line",
    "wall": "line",
    "coast": "line",
    # area features
    "hill": "area",
    "woods": "area",
    "marsh": "area",
    "lake": "area",
    "sea": "area",
    "island": "area",
    "fortification": "area",
    "camp": "area",
    "field": "area",
}

SOURCE_KINDS = ("primary", "secondary", "web", "video")
