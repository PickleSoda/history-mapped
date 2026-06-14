<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Enable trigram-based fuzzy search on entity names: the pg_trgm extension plus
 * a GIN trigram index backing the `%` similarity operator and ILIKE substring
 * matches used by EntityBuilder::search().
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::statement('CREATE EXTENSION IF NOT EXISTS pg_trgm');
        DB::statement('CREATE INDEX IF NOT EXISTS entities_name_trgm_idx ON entities USING gin (name gin_trgm_ops)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS entities_name_trgm_idx');
        // Leave the pg_trgm extension installed — other features may rely on it.
    }
};
