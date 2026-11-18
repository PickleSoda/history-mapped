<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Prefix index for 1-2 character searches (EntityBuilder::search). The
 * trigram index cannot serve a pattern shorter than three characters, so
 * `name ILIKE '%ro%'` read every row of entities (1 GB at 641k rows). Short
 * terms now match `lower(name) LIKE 'ro%'`, which this index answers.
 * Built CONCURRENTLY so a deploy does not block writes to entities.
 */
return new class extends Migration
{
    public $withinTransaction = false;

    public function up(): void
    {
        DB::statement('CREATE INDEX CONCURRENTLY IF NOT EXISTS entities_name_prefix_idx ON entities (lower(name) text_pattern_ops)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX CONCURRENTLY IF EXISTS entities_name_prefix_idx');
    }
};
