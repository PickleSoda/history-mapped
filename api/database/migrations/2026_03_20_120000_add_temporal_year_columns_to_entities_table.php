<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Add integer year columns for correct temporal sorting and indexing.
 *
 * The existing `temporal_start` / `temporal_end` text columns break
 * both index usage and sort order for BCE dates because string
 * comparison is lexicographic (`'-0500' > '1000'`).
 *
 * This migration adds `temporal_start_year` and `temporal_end_year`
 * integer columns, backfills them from the text columns, and replaces
 * the old composite text index with a proper integer B-tree index.
 *
 * The text columns are kept for raw display / free-form input.
 */
return new class extends Migration
{
    public function up(): void
    {
        // 1. Add integer year columns
        DB::statement('ALTER TABLE entities ADD COLUMN temporal_start_year integer');
        DB::statement('ALTER TABLE entities ADD COLUMN temporal_end_year integer');

        // 2. Backfill from existing text columns.
        //    Temporal text values may be plain years ('-0027', '0476') or
        //    partial/full ISO dates ('-0480-08', '1453-04-06'). Extract the
        //    leading signed integer (year) portion with a regex.
        DB::statement("
            UPDATE entities
            SET temporal_start_year = CAST(SUBSTRING(temporal_start FROM '^-?\\d+') AS integer)
            WHERE temporal_start IS NOT NULL
              AND temporal_start ~ '^-?\\d+'
        ");

        DB::statement("
            UPDATE entities
            SET temporal_end_year = CAST(SUBSTRING(temporal_end FROM '^-?\\d+') AS integer)
            WHERE temporal_end IS NOT NULL
              AND temporal_end ~ '^-?\\d+'
        ");

        // 3. Replace the old text composite index with integer indexes
        DB::statement('DROP INDEX IF EXISTS entities_temporal_range_idx');
        DB::statement('CREATE INDEX entities_temporal_start_year_idx ON entities (temporal_start_year)');
        DB::statement('CREATE INDEX entities_temporal_end_year_idx ON entities (temporal_end_year)');
        DB::statement('CREATE INDEX entities_temporal_year_range_idx ON entities (temporal_start_year, temporal_end_year)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS entities_temporal_year_range_idx');
        DB::statement('DROP INDEX IF EXISTS entities_temporal_end_year_idx');
        DB::statement('DROP INDEX IF EXISTS entities_temporal_start_year_idx');

        // Restore the original text composite index
        DB::statement('CREATE INDEX entities_temporal_range_idx ON entities (temporal_start, temporal_end)');

        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_end_year');
        DB::statement('ALTER TABLE entities DROP COLUMN IF EXISTS temporal_start_year');
    }
};
