<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Simplify the entities table by dropping dead columns and migrating
 * display/provenance metadata into the JSONB `attributes` column.
 *
 * See docs/plans/06-entity-model-simplification.md for the full plan.
 */
return new class extends Migration
{
    /**
     * Columns that are being moved into attributes JSONB.
     * The migration backfills existing non-null values before dropping.
     */
    private const MOVED_COLUMNS = [
        'entity_color',
        'era_label',
        'temporal_display_range',
        'date_raw',
        'confidence_notes',
        'validation_flags',
        'media_refs',
    ];

    /**
     * Columns that are simply dropped (never populated / dead).
     */
    private const DEAD_COLUMNS = [
        'relationship_summary',
        'nearby_entity_count',
        'cluster_id',
        'confidence_breakdown',
        'source_diversity_score',
        'embedding_version',
    ];

    public function up(): void
    {
        // ────────────────────────────────────────────────────────
        // 1. Backfill: merge existing column values into attributes
        // ────────────────────────────────────────────────────────
        //
        // For each row, build a JSONB object from the columns being moved
        // and merge it into the existing attributes. jsonb_strip_nulls()
        // ensures we only store keys that actually have values.
        //
        // validation_flags is text[] — convert to a JSON array.
        // media_refs is already jsonb — embed directly.
        DB::statement("
            UPDATE entities
            SET attributes = attributes || jsonb_strip_nulls(jsonb_build_object(
                'entity_color',            entity_color,
                'era_label',               era_label,
                'temporal_display_range',   temporal_display_range,
                'date_raw',                date_raw,
                'confidence_notes',        confidence_notes,
                'validation_flags',        to_jsonb(validation_flags),
                'media_refs',              media_refs
            ))
            WHERE entity_color IS NOT NULL
               OR era_label IS NOT NULL
               OR temporal_display_range IS NOT NULL
               OR date_raw IS NOT NULL
               OR confidence_notes IS NOT NULL
               OR validation_flags IS NOT NULL
               OR media_refs IS NOT NULL
        ");

        // ────────────────────────────────────────────────────────
        // 2. Drop all removed columns
        // ────────────────────────────────────────────────────────
        $allColumns = array_merge(self::MOVED_COLUMNS, self::DEAD_COLUMNS);

        foreach ($allColumns as $col) {
            DB::statement("ALTER TABLE entities DROP COLUMN IF EXISTS {$col}");
        }
    }

    public function down(): void
    {
        // ────────────────────────────────────────────────────────
        // 1. Re-add moved columns
        // ────────────────────────────────────────────────────────
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS entity_color text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS era_label text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS temporal_display_range text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS date_raw text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS confidence_notes text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS validation_flags text[]');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS media_refs jsonb');

        // ────────────────────────────────────────────────────────
        // 2. Re-add dead columns
        // ────────────────────────────────────────────────────────
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS relationship_summary jsonb');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS nearby_entity_count integer');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS cluster_id integer');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS confidence_breakdown jsonb');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS source_diversity_score integer');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS embedding_version text');

        // ────────────────────────────────────────────────────────
        // 3. Copy values back out of attributes into columns
        // ────────────────────────────────────────────────────────
        DB::statement("
            UPDATE entities
            SET entity_color            = attributes->>'entity_color',
                era_label               = attributes->>'era_label',
                temporal_display_range   = attributes->>'temporal_display_range',
                date_raw                = attributes->>'date_raw',
                confidence_notes        = attributes->>'confidence_notes',
                validation_flags        = ARRAY(SELECT jsonb_array_elements_text(attributes->'validation_flags')),
                media_refs              = attributes->'media_refs'
            WHERE attributes ? 'entity_color'
               OR attributes ? 'era_label'
               OR attributes ? 'temporal_display_range'
               OR attributes ? 'date_raw'
               OR attributes ? 'confidence_notes'
               OR attributes ? 'validation_flags'
               OR attributes ? 'media_refs'
        ");

        // ────────────────────────────────────────────────────────
        // 4. Remove the migrated keys from attributes
        // ────────────────────────────────────────────────────────
        DB::statement("
            UPDATE entities
            SET attributes = attributes - ARRAY[
                'entity_color', 'era_label', 'temporal_display_range',
                'date_raw', 'confidence_notes', 'validation_flags', 'media_refs'
            ]
        ");
    }
};
