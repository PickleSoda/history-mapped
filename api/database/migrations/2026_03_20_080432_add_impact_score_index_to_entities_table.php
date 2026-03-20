<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Add indexes to support map query pattern:
 * bbox + timeframe + impact_score threshold filtering.
 *
 * The map endpoint filters by:
 *   - geom && ST_MakeEnvelope(...)    → hits existing GIST index
 *   - temporal_start / temporal_end   → hits existing composite B-tree
 *   - impact_score >= threshold       → needs dedicated B-tree
 *
 * A composite (impact_score, entity_type) index also serves
 * the zoom-level threshold + type filter combination efficiently.
 */
return new class extends Migration
{
    public function up(): void
    {
        // B-tree on impact_score for threshold filtering (WHERE impact_score >= ?)
        DB::statement('CREATE INDEX IF NOT EXISTS entities_impact_score_idx ON entities (impact_score DESC NULLS LAST)');

        // Composite index for zoom-level threshold + type filter
        DB::statement('CREATE INDEX IF NOT EXISTS entities_impact_type_idx ON entities (impact_score DESC NULLS LAST, entity_type)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS entities_impact_type_idx');
        DB::statement('DROP INDEX IF EXISTS entities_impact_score_idx');
    }
};
