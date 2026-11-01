<?php

declare(strict_types=1);

namespace App\Support\MapStory;

/**
 * The map-story document vocabulary (schema 3; schemas 1 and 2 are subsets).
 *
 * Mirrors pipeline/map_stories/schema.py (the authoring source of truth) and
 * web/src/lib/schemas/map-story.ts; change all three together. The contracts
 * are docs/superpowers/specs/2026-10-31-map-story-schema-v2-design.md and the
 * schema-3 section of docs/superpowers/plans/2026-10-31-generic-map-stories.md;
 * the authoring guide (docs/implementation-docs/map-story-authoring.md)
 * explains each value.
 */
final class MapStoryVocabulary
{
    public const SCHEMA_VERSION = 3;

    public const SCHEMA_VERSIONS = [1, 2, 3];

    public const STORY_KINDS = [
        'battle', 'naval_battle', 'siege', 'campaign',
        'war', 'trade_route', 'epidemic', 'migration', 'exploration', 'expansion', 'diffusion', 'event',
    ];

    /** Kinds fought out by formations: they need two sides. */
    public const BATTLE_KINDS = ['battle', 'naval_battle', 'siege'];

    /** Military kinds: they need units (a campaign or a war may have one side). */
    public const MILITARY_KINDS = ['battle', 'naval_battle', 'siege', 'campaign', 'war'];

    public const UNIT_KINDS = [
        // foot
        'infantry', 'heavy_infantry', 'light_infantry', 'pikemen', 'archers', 'slingers', 'crossbowmen', 'musketeers',
        // mounted
        'cavalry', 'heavy_cavalry', 'light_cavalry', 'horse_archers', 'chariots', 'elephants', 'camels',
        // support
        'artillery', 'siege_engine',
        // naval
        'warship', 'transport',
        // point markers
        'commander', 'camp', 'baggage', 'standard', 'ship',
        // point markers at campaign or world scale
        'army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group',
    ];

    /** Kinds drawn as a single marker (no formation block). */
    public const POINT_UNIT_KINDS = [
        'commander', 'camp', 'baggage', 'standard', 'ship',
        'army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group',
    ];

    public const SHAPES = ['block', 'line', 'column', 'wedge', 'crescent', 'square', 'circle'];

    public const UNIT_STATES = [
        'ready', 'engaged', 'wavering', 'routed', 'destroyed', 'hidden',
        'killed', 'wounded', 'captured', 'sunk', 'aground', 'burning',
    ];

    public const MOVE_TYPES = [
        'advance', 'attack', 'charge', 'flank', 'feint', 'retreat', 'rout', 'pursuit', 'march', 'fire',
        'ram', 'back_water', 'blockade', 'landing',
        'sail', 'trade', 'migrate', 'explore', 'spread',
    ];

    public const MOVE_ORIENTS = ['path'];

    public const NOTE_KINDS = ['label', 'clash', 'death', 'capture', 'event'];

    /**
     * Feature (schema 1–2: terrain) kind → the geometry key it needs: `at`
     * point, `line`, or `area` (one ring; in schema 3 also a list of rings).
     */
    public const FEATURE_KINDS = [
        'town' => 'at', 'village' => 'at', 'farm' => 'at', 'building' => 'at', 'bridge' => 'at', 'pass' => 'at', 'label' => 'at',
        'city' => 'at', 'port' => 'at', 'market' => 'at', 'mine' => 'at', 'outbreak' => 'at', 'site' => 'at',
        'river' => 'line', 'stream' => 'line', 'road' => 'line', 'ridge' => 'line', 'wall' => 'line', 'coast' => 'line',
        'route' => 'line',
        'hill' => 'area', 'woods' => 'area', 'marsh' => 'area', 'lake' => 'area', 'sea' => 'area', 'island' => 'area',
        'fortification' => 'area', 'camp' => 'area', 'field' => 'area', 'mask' => 'area',
        'region' => 'area',
    ];

    public const FEATURE_STATES = [
        'held', 'contested', 'captured', 'burning', 'destroyed', 'flooded',
        'infected', 'peak', 'recovered', 'founded', 'abandoned', 'disrupted', 'new',
    ];

    /** Required on a `route` feature. */
    public const ROUTE_KINDS = ['trade', 'voyage', 'migration', 'pilgrimage', 'campaign', 'road'];

    /** Required on a `region` feature. */
    public const REGION_KINDS = ['spread', 'extent', 'influence', 'affected', 'front'];

    public const LEGEND_STYLES = ['fill', 'line', 'dot'];

    /** The longest day of each month (a date check, so 29 February always passes). */
    public const MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

    /** Feature-state keys that set the geometry: giving one replaces the others. */
    public const GEOMETRY_KEYS = ['at', 'line', 'area', 'area_from_entity'];

    public const LIGHTS = ['night', 'dawn', 'day', 'dusk'];

    public const WIND_STRENGTHS = ['light', 'strong'];

    public const SOURCE_KINDS = ['primary', 'secondary', 'web', 'video'];

    // Schema 2: a schema-1 document may not use these values or fields.

    public const V2_UNIT_KINDS = ['standard', 'ship'];

    public const V2_UNIT_STATES = ['killed', 'wounded', 'captured', 'sunk', 'aground', 'burning'];

    public const V2_MOVE_TYPES = ['ram', 'back_water', 'blockade', 'landing'];

    public const V2_FEATURE_KINDS = ['mask'];

    /** Fields added in schema 2, by the object they belong to. */
    public const V2_FIELDS = [
        'document' => ['alt_sites'],
        'side' => ['contingents'],
        'unit' => ['ranks', 'strength_n', 'contingent'],
        'feature' => ['conjectural'],
        'step' => ['beats', 'terrain_state', 'light', 'wind', 'sun'],
        'placement' => ['frame', 'from', 'into', 'lines', 'lanes', 'subunits', 'strength_n', 'by', 'conjectural'],
        'move' => ['continues', 'orient', 'target', 'arc', 'conjectural'],
        'note' => ['conjectural'],
    ];

    // Schema 3: a schema-1 or schema-2 document may not use these values or fields.

    public const V3_STORY_KINDS = ['war', 'trade_route', 'epidemic', 'migration', 'exploration', 'expansion', 'diffusion', 'event'];

    public const V3_UNIT_KINDS = ['army', 'fleet', 'caravan', 'merchant_ship', 'expedition', 'group'];

    public const V3_MOVE_TYPES = ['sail', 'trade', 'migrate', 'explore', 'spread'];

    public const V3_FEATURE_KINDS = ['city', 'port', 'market', 'mine', 'outbreak', 'site', 'route', 'region'];

    public const V3_FEATURE_STATES = ['infected', 'peak', 'recovered', 'founded', 'abandoned', 'disrupted', 'new'];

    /**
     * Fields added in schema 3, by the object they belong to. `features` is the
     * new name of `terrain` (document) and of `terrain_state` (step).
     */
    public const V3_FIELDS = [
        'document' => ['chronicle', 'period', 'ambient', 'legend', 'features'],
        'feature' => ['entity', 'side', 'goods', 'route_kind', 'region_kind', 'bidirectional', 'active', 'value_n', 'intensity'],
        'step' => ['date', 'entry', 'entities', 'features'],
        'feature_state' => ['active', 'value_n', 'value_label', 'intensity', 'at', 'line', 'area', 'area_from_entity'],
    ];

    /** The feature kinds an ambient story shows on the plain atlas. */
    public const AMBIENT_FEATURE_KINDS = ['route', 'region', 'outbreak', 'port', 'market', 'city'];

    /** Integer ranges for the formation-detail placement fields. */
    public const FORMATION_RANGES = ['lines' => [1, 5], 'lanes' => [0, 12], 'subunits' => [1, 24]];

    public const MAX_BEATS = 4;
}
