<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("COMMENT ON COLUMN entities.temporal_start IS 'DEPRECATED: use entity_temporal_ranges + timeline projection'");
        DB::statement("COMMENT ON COLUMN entities.temporal_end IS 'DEPRECATED: use entity_temporal_ranges + timeline projection'");
        DB::statement("COMMENT ON COLUMN entities.temporal_start_year IS 'DEPRECATED: use entity_temporal_ranges.start_year'");
        DB::statement("COMMENT ON COLUMN entities.temporal_end_year IS 'DEPRECATED: use entity_temporal_ranges.end_year'");
        DB::statement("COMMENT ON COLUMN entities.location_name IS 'DEPRECATED: use entity_locations or geometry_periods context'");
        DB::statement("COMMENT ON COLUMN entities.location_method IS 'DEPRECATED: use entity_locations.location_method'");
        DB::statement("COMMENT ON COLUMN entities.location_confidence IS 'DEPRECATED: use entity_locations.location_confidence'");
    }

    public function down(): void
    {
        DB::statement('COMMENT ON COLUMN entities.temporal_start IS NULL');
        DB::statement('COMMENT ON COLUMN entities.temporal_end IS NULL');
        DB::statement('COMMENT ON COLUMN entities.temporal_start_year IS NULL');
        DB::statement('COMMENT ON COLUMN entities.temporal_end_year IS NULL');
        DB::statement('COMMENT ON COLUMN entities.location_name IS NULL');
        DB::statement('COMMENT ON COLUMN entities.location_method IS NULL');
        DB::statement('COMMENT ON COLUMN entities.location_confidence IS NULL');
    }
};
