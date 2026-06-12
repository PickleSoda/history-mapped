<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("ALTER TABLE chronicle_entries
            ALTER COLUMN source_evidence TYPE jsonb
            USING CASE WHEN source_evidence IS NULL THEN NULL
                       ELSE jsonb_build_array(source_evidence) END");
    }

    public function down(): void
    {
        DB::statement("ALTER TABLE chronicle_entries
            ALTER COLUMN source_evidence TYPE text
            USING CASE WHEN source_evidence IS NULL THEN NULL
                       ELSE (source_evidence->>0) END");
    }
};