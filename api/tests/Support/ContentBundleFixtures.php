<?php

declare(strict_types=1);

namespace Tests\Support;

/**
 * Fully populated bundle lines (every key non-null, one item per nested list) for schema,
 * serializer and validator tests. Keys are in bundle order.
 */
final class ContentBundleFixtures
{
    public const ENTITY_ID = '3f2b8c1e-5a47-4d0e-9b6a-1c2d3e4f5a6b';

    public const RELATIONSHIP_ID = '7a1d9e20-8c3b-4f5a-a1b2-2d3e4f5a6b7c';

    public const PERIOD_ID = '9c4e2f31-1d5a-4b6c-8e7f-3e4f5a6b7c8d';

    public const GEO_REF_ID = 'b2e5f4a6-2e6b-4c7d-9f80-4f5a6b7c8d9e';

    public const CHRONICLE_ID = 'd5f6a7b8-3f7c-4d8e-a091-5a6b7c8d9eaf';

    public const ENTRY_ID = 'e6a7b8c9-4a8d-4e9f-b1a2-6b7c8d9eafb0';

    public const OTHER_ENTITY_ID = 'f7b8c9d0-5b9e-4fa0-82b3-7c8d9eafb0c1';

    /** @return array<string, array<string, mixed>> */
    public static function all(): array
    {
        return [
            'entities' => self::entity(),
            'relationships' => self::relationship(),
            'geometry_periods' => self::geometryPeriod(),
            'geo_refs' => self::geoRef(),
            'chronicles' => self::chronicle(),
            'chronicle_entries' => self::chronicleEntry(),
        ];
    }

    /** @return array<string, mixed> */
    public static function polygon(): array
    {
        return ['type' => 'Polygon', 'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 41.0]]]];
    }

    /** @return array<string, mixed> */
    public static function entity(): array
    {
        return [
            'id' => self::ENTITY_ID,
            'name' => 'Roman Republic',
            'entity_type' => 'political_entity',
            'wikidata_id' => 'Q17167',
            'summary' => 'The era of classical Roman civilization led by an elected senate.',
            'significance' => 'Laid the foundations of Western law and government.',
            'impact_score' => 95,
            'display_priority' => 10,
            'icon_class' => 'crown',
            'confidence' => 'high',
            'verification_status' => 'human_verified',
            'date_method' => 'source_database',
            'date_confidence' => 'high',
            'duration_type' => 'period',
            'location_method' => 'wikidata',
            'location_confidence' => 'medium',
            'primary_geo_ref_id' => self::GEO_REF_ID,
            'attributes' => ['capital' => 'Rome', '_internal' => 'x'],
            'source_citations' => ['wikidata_id' => 'Q17167', 'confidence' => 1],
            'aliases' => [['name' => 'Res publica Romana', 'language' => 'la', 'source' => 'wikidata', 'is_primary' => false]],
            'tags' => [['slug' => 'ancient-rome', 'source' => 'curated']],
            'temporal_ranges' => [[
                'range_type' => 'primary', 'start_year' => -509, 'end_year' => -27,
                'start_date' => '-0509', 'end_date' => '-0027', 'duration_type' => 'period',
                'date_method' => 'source_database', 'date_confidence' => 'high', 'is_primary' => true, 'notes' => 'Traditional dates.',
            ]],
            'locations' => [[
                'location_name' => 'Rome', 'location_method' => 'wikidata', 'location_confidence' => 'high',
                'is_primary' => true, 'notes' => 'Capital city.', 'geom' => ['type' => 'Point', 'coordinates' => [12.4964, 41.9028]],
                'territory_geom' => self::polygon(),
            ]],
        ];
    }

    /** @return array<string, mixed> */
    public static function relationship(): array
    {
        return [
            'id' => self::RELATIONSHIP_ID,
            'source_entity_id' => self::ENTITY_ID,
            'target_entity_id' => self::OTHER_ENTITY_ID,
            'relationship_type' => 'governed_by',
            'temporal_start' => '-0509',
            'temporal_end' => '-0027',
            'start_year' => -509,
            'end_year' => -27,
            'description' => 'Governed by the Senate.',
            'confidence' => 'medium',
            'derive_geometry_period' => false,
            'source_citations' => ['source' => 'wikidata'],
        ];
    }

    /** @return array<string, mixed> */
    public static function geometryPeriod(): array
    {
        return [
            'id' => self::PERIOD_ID,
            'entity_id' => self::ENTITY_ID,
            'period_type' => 'territory',
            'start_year' => -509,
            'end_year' => -27,
            'description' => 'Extent of the Republic.',
            'confidence' => 'medium',
            'provenance_mode' => 'derived',
            'relationship_id' => self::RELATIONSHIP_ID,
            'source_event_id' => self::OTHER_ENTITY_ID,
            'geom' => ['type' => 'Point', 'coordinates' => [12.4964, 41.9028]],
            'territory_geom' => self::polygon(),
        ];
    }

    /** @return array<string, mixed> */
    public static function geoRef(): array
    {
        return [
            'id' => self::GEO_REF_ID,
            'entity_id' => self::ENTITY_ID,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '2698123',
            'match_role' => 'primary',
            'retrieval_method' => 'overpass',
            'temporal_start' => '-0509',
            'temporal_end' => '-0027',
            'temporal_start_year' => -509,
            'temporal_end_year' => -27,
            'geometry_period_id' => self::PERIOD_ID,
            'match_score' => 0.8731,
            'is_active' => true,
            'external_tags' => ['name' => 'Roman Republic'],
            'source_meta' => ['query' => 'rel[name=Roman Republic]'],
        ];
    }

    /** @return array<string, mixed> */
    public static function chronicle(): array
    {
        return [
            'id' => self::CHRONICLE_ID,
            'slug' => 'rise-of-the-roman-republic',
            'title' => 'Rise of the Roman Republic',
            'source_type' => 'article',
            'source_reference' => 'https://en.wikipedia.org/wiki/Roman_Republic',
            'status' => 'published',
            'start_year' => -509,
            'end_year' => -264,
            'impact_score' => 80,
            'approximate_location' => ['lat' => 41.9, 'lon' => 12.5],
            'metadata' => ['campaign' => 'e03'],
            'tags' => [['slug' => 'ancient-rome', 'source' => 'manual']],
        ];
    }

    /** @return array<string, mixed> */
    public static function chronicleEntry(): array
    {
        return [
            'id' => self::ENTRY_ID,
            'chronicle_id' => self::CHRONICLE_ID,
            'sequence_order' => 3,
            'start_year' => -494,
            'end_year' => -493,
            'impact_score' => 60,
            'primary_relationship_id' => self::RELATIONSHIP_ID,
            'narrative_text' => 'The plebeians withdrew from Rome in the first secession.',
            'notes' => 'Dates approximate.',
            'approximate_location' => ['lat' => 41.9, 'lon' => 12.5],
            'source_evidence' => 'event:0',
            'generated_by' => 'historical-agent-pipeline',
            'entities' => [['entity_id' => self::ENTITY_ID, 'role' => 'participant', 'sequence_in_entry' => 1]],
        ];
    }
}
