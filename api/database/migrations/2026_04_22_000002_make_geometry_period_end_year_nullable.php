<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Allow open-ended periods (current entities with no end date)
        DB::statement('ALTER TABLE geometry_periods ALTER COLUMN end_year DROP NOT NULL');
        DB::statement('ALTER TABLE geometry_periods DROP CONSTRAINT IF EXISTS gp_valid_year_range');
        DB::statement('ALTER TABLE geometry_periods ADD CONSTRAINT gp_valid_year_range
            CHECK (end_year IS NULL OR start_year <= end_year)');

        // Same for the denormalised timeline projection
        DB::statement('ALTER TABLE entity_timeline_entries ALTER COLUMN end_year DROP NOT NULL');
        DB::statement('ALTER TABLE entity_timeline_entries DROP CONSTRAINT IF EXISTS ete_valid_year_range');
        DB::statement('ALTER TABLE entity_timeline_entries ADD CONSTRAINT ete_valid_year_range
            CHECK (end_year IS NULL OR start_year <= end_year)');
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE entity_timeline_entries DROP CONSTRAINT IF EXISTS ete_valid_year_range');
        DB::statement('ALTER TABLE entity_timeline_entries ADD CONSTRAINT ete_valid_year_range
            CHECK (start_year <= end_year)');
        DB::statement('ALTER TABLE entity_timeline_entries ALTER COLUMN end_year SET NOT NULL');

        DB::statement('ALTER TABLE geometry_periods DROP CONSTRAINT IF EXISTS gp_valid_year_range');
        DB::statement('ALTER TABLE geometry_periods ADD CONSTRAINT gp_valid_year_range
            CHECK (start_year <= end_year)');
        DB::statement('ALTER TABLE geometry_periods ALTER COLUMN end_year SET NOT NULL');
    }
};
