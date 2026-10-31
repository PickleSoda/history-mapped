"""The map-story document vocabulary (schema 3; schemas 1 and 2 are subsets).

Mirrors web/src/lib/schemas/map-story.ts and api/app/Support/MapStory/
MapStoryVocabulary.php; change all three together. The contracts are
docs/superpowers/specs/2026-10-31-map-story-schema-v2-design.md and the
schema-3 contract in docs/superpowers/plans/2026-10-31-generic-map-stories.md;
the authoring guide (docs/implementation-docs/map-story-authoring.md) explains
each field.
"""

SCHEMA_VERSION = 3
SCHEMA_VERSIONS = (1, 2, 3)

STORY_KINDS = (
    "battle",
    "naval_battle",
    "siege",
    "campaign",
    # schema 3
    "war",
    "trade_route",
    "epidemic",
    "migration",
    "exploration",
    "expansion",
    "diffusion",
    "event",
)

#: Story kinds fought out by formations: two sides, units, formation lint.
BATTLE_KINDS = ("battle", "naval_battle", "siege")
#: Military kinds: they need units (a campaign or war may have one side).
MILITARY_KINDS = (*BATTLE_KINDS, "campaign", "war")

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
    "standard",
    "ship",
    # schema 3: map-scale markers
    "army",
    "fleet",
    "caravan",
    "merchant_ship",
    "expedition",
    "group",
)

#: Kinds drawn as a single marker (no formation block).
POINT_UNIT_KINDS = ("commander", "camp", "baggage", "standard", "ship", "army", "fleet", "caravan", "merchant_ship", "expedition", "group")

#: Kinds that float: the land/water check wants them on water.
SHIP_UNIT_KINDS = ("warship", "ship", "transport", "fleet", "merchant_ship")

SHAPES = ("block", "line", "column", "wedge", "crescent", "square", "circle")

UNIT_STATES = (
    "ready",
    "engaged",
    "wavering",
    "routed",
    "destroyed",
    "hidden",
    "killed",
    "wounded",
    "captured",
    "sunk",
    "aground",
    "burning",
)

#: States that only fit some kinds (the validator warns otherwise).
STATE_KINDS = {
    "killed": POINT_UNIT_KINDS,
    "wounded": POINT_UNIT_KINDS,
    "sunk": SHIP_UNIT_KINDS,
    "aground": SHIP_UNIT_KINDS,
}

MOVE_TYPES = (
    "advance",
    "attack",
    "charge",
    "flank",
    "feint",
    "retreat",
    "rout",
    "pursuit",
    "march",
    "fire",
    "ram",
    "back_water",
    "blockade",
    "landing",
    # schema 3
    "sail",
    "trade",
    "migrate",
    "explore",
    "spread",
)

MOVE_ORIENTS = ("path",)

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
    "mask": "area",
}

#: Feature kinds (schema 3 generalises terrain into features) → geometry key.
FEATURE_KINDS = {
    **TERRAIN_KINDS,
    "city": "at",
    "port": "at",
    "market": "at",
    "mine": "at",
    "outbreak": "at",
    "site": "at",
    "route": "line",
    "region": "area",
}

ROUTE_KINDS = ("trade", "voyage", "migration", "pilgrimage", "campaign", "road")
REGION_KINDS = ("spread", "extent", "influence", "affected", "front")

TERRAIN_STATES = ("held", "contested", "captured", "burning", "destroyed", "flooded")
FEATURE_STATES = (*TERRAIN_STATES, "infected", "peak", "recovered", "founded", "abandoned", "disrupted", "new")

LEGEND_STYLES = ("fill", "line", "dot")

LIGHTS = ("night", "dawn", "day", "dusk")

WIND_STRENGTHS = ("light", "strong")

SOURCE_KINDS = ("primary", "secondary", "web", "video")

# ── schema 2 ──────────────────────────────────────────────────────────────
# A schema-1 document may not use these values or fields; the validators tell
# the author to bump `schema` to 2.

V2_UNIT_KINDS = ("standard", "ship")
V2_UNIT_STATES = ("killed", "wounded", "captured", "sunk", "aground", "burning")
V2_MOVE_TYPES = ("ram", "back_water", "blockade", "landing")
V2_TERRAIN_KINDS = ("mask",)

#: Fields added in schema 2, by the object they belong to.
V2_FIELDS = {
    "document": ("alt_sites",),
    "side": ("contingents",),
    "unit": ("ranks", "strength_n", "contingent"),
    "terrain": ("conjectural",),
    "step": ("beats", "terrain_state", "light", "wind", "sun"),
    "placement": ("frame", "from", "into", "lines", "lanes", "subunits", "strength_n", "by", "conjectural"),
    "move": ("continues", "orient", "target", "arc", "conjectural"),
    "note": ("conjectural",),
}

#: Placement fields that only make sense on a formation block.
FORMATION_FIELDS = ("lines", "lanes", "subunits")

#: Integer ranges for the formation-detail fields.
FORMATION_RANGES = {"lines": (1, 5), "lanes": (0, 12), "subunits": (1, 24)}

MAX_BEATS = 4

# ── schema 3 ──────────────────────────────────────────────────────────────
# A schema-1 or -2 document may not use these; the validators say "bump schema".

V3_STORY_KINDS = STORY_KINDS[4:]
V3_UNIT_KINDS = ("army", "fleet", "caravan", "merchant_ship", "expedition", "group")
V3_MOVE_TYPES = ("sail", "trade", "migrate", "explore", "spread")
V3_FEATURE_KINDS = ("city", "port", "market", "mine", "outbreak", "site", "route", "region")
V3_FEATURE_STATES = FEATURE_STATES[len(TERRAIN_STATES):]

#: Fields added in schema 3, by the object they belong to. `features` is the
#: new name of `terrain` (document) and of `terrain_state` (step).
V3_FIELDS = {
    "document": ("chronicle", "period", "ambient", "legend", "features"),
    "step": ("date", "entry", "entities", "features"),
    "feature": ("entity", "side", "goods", "route_kind", "region_kind", "bidirectional", "active", "value_n", "intensity"),
    "feature_state": ("active", "value_n", "value_label", "intensity", "at", "line", "area", "area_from_entity"),
}

#: Validator scale per story kind: how far (km) anything may sit from the
#: story's centre, and how far (m) a unit may jump between frames without an arrow.
SPREAD_KM = {
    "battle": 20, "naval_battle": 30, "siege": 15,
    "campaign": 3000, "war": 3000, "expansion": 3000,
    "diffusion": 5000, "event": 5000,
    "epidemic": 20_000, "trade_route": 20_000, "migration": 20_000, "exploration": 20_000,
}
TELEPORT_M = {
    "battle": 900, "naval_battle": 1500, "siege": 600,
    "campaign": 150_000, "war": 150_000, "expansion": 150_000,
    "diffusion": 300_000, "event": 300_000,
    "epidemic": 2_000_000, "trade_route": 2_000_000, "migration": 2_000_000, "exploration": 2_000_000,
}

#: Terrain kinds that count as water for the land/water check.
WATER_AREA_KINDS = ("sea", "lake")
WATER_LINE_KINDS = ("river", "coast")
#: How close (m) to a river or coast line a ship may sit.
SHORE_M = 400
