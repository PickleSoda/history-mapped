<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Map-optimization indexes (spec §4.1):
 * - partial UNIQUE (entity_id) WHERE is_primary on the one-primary tables,
 *   guarded by a duplicate audit so the constraint can't fail mid-deploy;
 * - a functional GiST on COALESCE(territory_geom, geom) for the single-geometry
 *   bbox filter;
 * - a display_priority index matching the map's NULLS-LAST ordering.
 */
return new class extends Migration
{
    public function up(): void
    {
        foreach (['entity_aliases', 'entity_locations', 'entity_temporal_ranges'] as $table) {
            $this->assertNoDuplicatePrimaries($table);
        }

        DB::statement('CREATE UNIQUE INDEX IF NOT EXISTS entity_aliases_primary_unique ON entity_aliases (entity_id) WHERE is_primary');
        DB::statement('CREATE UNIQUE INDEX IF NOT EXISTS entity_locations_primary_unique ON entity_locations (entity_id) WHERE is_primary');
        DB::statement('CREATE UNIQUE INDEX IF NOT EXISTS entity_temporal_ranges_primary_unique ON entity_temporal_ranges (entity_id) WHERE is_primary');
        DB::statement('CREATE INDEX IF NOT EXISTS gp_map_geom_gist ON geometry_periods USING GIST (COALESCE(territory_geom, geom))');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_display_priority_idx ON entities (display_priority DESC NULLS LAST)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS entity_aliases_primary_unique');
        DB::statement('DROP INDEX IF EXISTS entity_locations_primary_unique');
        DB::statement('DROP INDEX IF EXISTS entity_temporal_ranges_primary_unique');
        DB::statement('DROP INDEX IF EXISTS gp_map_geom_gist');
        DB::statement('DROP INDEX IF EXISTS entities_display_priority_idx');
    }

    /**
     * Abort the migration if a table already violates the one-primary invariant,
     * so CREATE UNIQUE INDEX cannot fail partway through a deploy.
     */
    private function assertNoDuplicatePrimaries(string $table): void
    {
        $hasDuplicates = DB::table($table)
            ->where('is_primary', true)
            ->select('entity_id')
            ->groupBy('entity_id')
            ->havingRaw('COUNT(*) > 1')
            ->exists();

        if ($hasDuplicates) {
            throw new RuntimeException(
                "Cannot add unique primary index: {$table} has duplicate is_primary rows for some entity_id. Resolve the duplicates first.",
            );
        }
    }
};
