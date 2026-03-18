<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * Creates all PostgreSQL enum types required by the entity system.
     */
    public function up(): void
    {
        // Drop any existing types first (needed for migrate:fresh which drops
        // tables but not PG types, leaving stale types behind).
        $this->down();

        // ──────────────────────────────────────────────
        // Core system enums
        // ──────────────────────────────────────────────

        // Top-level grouping for all entities
        DB::statement("
            CREATE TYPE entity_group AS ENUM (
                'POLITY',
                'PLACE',
                'EVENT',
                'ECONOMY',
                'CULTURE'
            )
        ");

        // Specific entity type within a group (30 values)
        DB::statement("
            CREATE TYPE entity_type AS ENUM (
                'political_entity',
                'dynasty',
                'person',
                'military_unit',
                'diplomatic_relationship',
                'social_class',
                'city',
                'infrastructure_monument',
                'extraction_infra',
                'educational_institution',
                'event_war',
                'event_battle',
                'event_treaty',
                'event_rebellion',
                'event_natural_disaster',
                'event_tech_adoption',
                'event_legal_reform',
                'migration',
                'epidemic_disease',
                'trade_route',
                'natural_resource',
                'currency_monetary_system',
                'cultural_work',
                'intellectual_movement',
                'archaeological_culture',
                'language',
                'religious_text',
                'legal_code',
                'religious_movement',
                'technology'
            )
        ");

        // Pipeline verification workflow status
        DB::statement("
            CREATE TYPE verification_status AS ENUM (
                'pipeline_draft',
                'auto_validated',
                'needs_review',
                'in_review',
                'human_verified',
                'expert_verified',
                'flagged',
                'rejected',
                'merged'
            )
        ");

        // Confidence level assigned to a data point
        DB::statement("
            CREATE TYPE confidence_level AS ENUM (
                'high',
                'medium',
                'low',
                'unresolved'
            )
        ");

        // Source reliability tier
        DB::statement("
            CREATE TYPE reliability_tier AS ENUM (
                'authoritative',
                'scholarly',
                'reference',
                'user_contributed'
            )
        ");

        // ──────────────────────────────────────────────
        // Temporal enums
        // ──────────────────────────────────────────────

        // Method used to resolve a date value
        DB::statement("
            CREATE TYPE date_resolution_method AS ENUM (
                'nlp_direct',
                'nlp_approximate',
                'llm_reign_resolution',
                'era_table_lookup',
                'llm_contextual_inference',
                'human_assigned',
                'source_database'
            )
        ");

        // Duration classification of a temporal span
        DB::statement("
            CREATE TYPE duration_type AS ENUM (
                'point',
                'period',
                'ongoing',
                'uncertain'
            )
        ");

        // ──────────────────────────────────────────────
        // Spatial enums
        // ──────────────────────────────────────────────

        // Method used to resolve a location
        DB::statement("
            CREATE TYPE location_resolution_method AS ENUM (
                'ohm_nominatim',
                'wikidata',
                'geonames',
                'pleiades',
                'llm_disambiguation',
                'human_assigned',
                'source_database'
            )
        ");

        // PostGIS geometry type classification
        DB::statement("
            CREATE TYPE geometry_type AS ENUM (
                'point',
                'polygon',
                'linestring',
                'multipoint',
                'multipolygon'
            )
        ");

        // ──────────────────────────────────────────────
        // Display enums
        // ──────────────────────────────────────────────

        // Icon class for UI rendering of entities (30 values)
        DB::statement("
            CREATE TYPE icon_class AS ENUM (
                'crown',
                'person',
                'dynasty_tree',
                'sword',
                'city',
                'monument',
                'trade_ship',
                'gem',
                'pickaxe',
                'coin',
                'people',
                'migration_arrow',
                'plague',
                'handshake',
                'scroll',
                'palette',
                'ruins',
                'language_glyph',
                'sacred_book',
                'scales',
                'crossed_swords',
                'shield',
                'treaty_seal',
                'fist',
                'earthquake',
                'gear',
                'quill',
                'temple',
                'lightbulb',
                'university'
            )
        ");

        // ──────────────────────────────────────────────
        // Relationship enums
        // ──────────────────────────────────────────────

        // All possible relationship types between entities (76 values)
        DB::statement("
            CREATE TYPE relationship_type AS ENUM (
                'rules',
                'governed_by',
                'vassal_of',
                'suzerain_of',
                'allied_with',
                'at_war_with',
                'succeeded_by',
                'preceded_by',
                'part_of',
                'contains',
                'capital_of',
                'split_from',
                'merged_into',
                'born_in',
                'died_in',
                'resided_in',
                'commanded',
                'founded',
                'authored',
                'commissioned',
                'married_to',
                'parent_of',
                'child_of',
                'sibling_of',
                'mentor_of',
                'student_of',
                'assassinated_by',
                'member_of_dynasty',
                'patron_of',
                'participated_in',
                'fought_at',
                'defeated_at',
                'victorious_at',
                'stationed_at',
                'recruited_from',
                'commanded_by',
                'trades_with',
                'connects',
                'produces',
                'extracts',
                'supplies',
                'controlled_by',
                'passes_through',
                'minted_by',
                'used_currency',
                'adheres_to',
                'official_religion_of',
                'persecuted_by',
                'influenced_by',
                'inspired',
                'schism_from',
                'translated_into',
                'located_at',
                'built_by',
                'destroyed_by',
                'restored_by',
                'caused',
                'resulted_from',
                'contributed_to',
                'enabled',
                'prevented',
                'weakened',
                'strengthened',
                'invented',
                'adopted',
                'taught_at',
                'spread_to',
                'required_by',
                'replaced_by',
                'signed_by',
                'violated_by',
                'guaranteed_by',
                'mediated_by',
                'enforced_by'
            )
        ");
    }

    /**
     * Reverse the migrations.
     *
     * Drops all enum types in reverse creation order.
     */
    public function down(): void
    {
        DB::statement('DROP TYPE IF EXISTS relationship_type CASCADE');
        DB::statement('DROP TYPE IF EXISTS icon_class CASCADE');
        DB::statement('DROP TYPE IF EXISTS geometry_type CASCADE');
        DB::statement('DROP TYPE IF EXISTS location_resolution_method CASCADE');
        DB::statement('DROP TYPE IF EXISTS duration_type CASCADE');
        DB::statement('DROP TYPE IF EXISTS date_resolution_method CASCADE');
        DB::statement('DROP TYPE IF EXISTS reliability_tier CASCADE');
        DB::statement('DROP TYPE IF EXISTS confidence_level CASCADE');
        DB::statement('DROP TYPE IF EXISTS verification_status CASCADE');
        DB::statement('DROP TYPE IF EXISTS entity_type CASCADE');
        DB::statement('DROP TYPE IF EXISTS entity_group CASCADE');
    }
};
