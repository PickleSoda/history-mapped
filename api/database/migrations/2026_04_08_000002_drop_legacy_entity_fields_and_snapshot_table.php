<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS geom');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS territory_geom');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS location_name');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_start');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_end');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_start_year');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_end_year');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS alternative_names');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS tags');

        Schema::dropIfExists('geometry_snapshots');
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS geom geometry');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS territory_geom geometry');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS location_name text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS temporal_start text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS temporal_end text');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS temporal_start_year integer');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS temporal_end_year integer');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS alternative_names text[]');
        DB::statement('ALTER TABLE entities ADD COLUMN IF NOT EXISTS tags text[]');
    }
};
