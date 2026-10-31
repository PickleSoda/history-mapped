<?php

declare(strict_types=1);

namespace App\Support\MapStory;

/**
 * The map-story document vocabulary (schema 1).
 *
 * Mirrors pipeline/map_stories/schema.py (the authoring source of truth) and
 * web/src/lib/schemas/map-story.ts; change all three together. The authoring
 * guide (docs/implementation-docs/map-story-authoring.md) explains each value.
 */
final class MapStoryVocabulary
{
    public const SCHEMA_VERSION = 1;

    public const STORY_KINDS = ['battle', 'naval_battle', 'siege', 'campaign'];

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
        'commander', 'camp', 'baggage',
    ];

    public const SHAPES = ['block', 'line', 'column', 'wedge', 'crescent', 'square', 'circle'];

    public const UNIT_STATES = ['ready', 'engaged', 'wavering', 'routed', 'destroyed', 'hidden'];

    public const MOVE_TYPES = ['advance', 'attack', 'charge', 'flank', 'feint', 'retreat', 'rout', 'pursuit', 'march', 'fire'];

    public const NOTE_KINDS = ['label', 'clash', 'death', 'capture', 'event'];

    /** Terrain kind → the geometry key it needs (`at` point, `line`, `area` ring). */
    public const TERRAIN_KINDS = [
        'town' => 'at', 'village' => 'at', 'farm' => 'at', 'building' => 'at', 'bridge' => 'at', 'pass' => 'at', 'label' => 'at',
        'river' => 'line', 'stream' => 'line', 'road' => 'line', 'ridge' => 'line', 'wall' => 'line', 'coast' => 'line',
        'hill' => 'area', 'woods' => 'area', 'marsh' => 'area', 'lake' => 'area', 'sea' => 'area', 'island' => 'area',
        'fortification' => 'area', 'camp' => 'area', 'field' => 'area',
    ];

    public const SOURCE_KINDS = ['primary', 'secondary', 'web', 'video'];
}
