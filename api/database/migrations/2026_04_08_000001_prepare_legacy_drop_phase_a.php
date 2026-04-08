<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('DROP INDEX IF EXISTS entities_geom_gist_idx');
        DB::statement('DROP INDEX IF EXISTS entities_territory_geom_gist_idx');
        DB::statement('DROP INDEX IF EXISTS entities_temporal_range_idx');
        DB::statement('DROP INDEX IF EXISTS entities_temporal_start_index');
        DB::statement('DROP INDEX IF EXISTS entities_temporal_end_index');
        DB::statement('DROP INDEX IF EXISTS entities_tags_gin_idx');
    }

    public function down(): void
    {
        DB::statement('CREATE INDEX IF NOT EXISTS entities_geom_gist_idx ON entities USING gist (geom)');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_territory_geom_gist_idx ON entities USING gist (territory_geom)');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_temporal_range_idx ON entities (temporal_start, temporal_end)');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_temporal_start_index ON entities (temporal_start)');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_temporal_end_index ON entities (temporal_end)');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_tags_gin_idx ON entities USING gin (tags)');
    }
};
