<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('ALTER TABLE relationships ADD COLUMN start_year integer');
        DB::statement('ALTER TABLE relationships ADD COLUMN end_year integer');

                DB::statement(
                        "UPDATE relationships
                        SET start_year = CAST(SUBSTRING(temporal_start FROM '^-?\\d+') AS integer)
                        WHERE temporal_start IS NOT NULL
                            AND temporal_start ~ '^-?\\d+'"
                );

                DB::statement(
                        "UPDATE relationships
                        SET end_year = CAST(SUBSTRING(temporal_end FROM '^-?\\d+') AS integer)
                        WHERE temporal_end IS NOT NULL
                            AND temporal_end ~ '^-?\\d+'"
                );

        DB::statement('CREATE INDEX relationships_start_year_idx ON relationships (start_year)');
        DB::statement('CREATE INDEX relationships_end_year_idx ON relationships (end_year)');
        DB::statement('CREATE INDEX relationships_year_range_idx ON relationships (start_year, end_year)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS relationships_year_range_idx');
        DB::statement('DROP INDEX IF EXISTS relationships_end_year_idx');
        DB::statement('DROP INDEX IF EXISTS relationships_start_year_idx');

        DB::statement('ALTER TABLE relationships DROP COLUMN IF EXISTS end_year');
        DB::statement('ALTER TABLE relationships DROP COLUMN IF EXISTS start_year');
    }
};