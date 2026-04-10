<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("ALTER TYPE verification_status ADD VALUE IF NOT EXISTS 'ohm_draft'");

        DB::statement('ALTER TABLE geometry_periods DROP CONSTRAINT IF EXISTS gp_provenance_mode');
        DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_provenance_mode CHECK (provenance_mode IN ('derived', 'manual', 'ohm_import'))");
    }

    public function down(): void
    {
        // PostgreSQL enum values cannot be removed safely in down migrations.
        // Keep verification_status as-is and restore the older check constraint.
        DB::statement('ALTER TABLE geometry_periods DROP CONSTRAINT IF EXISTS gp_provenance_mode');
        DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_provenance_mode CHECK (provenance_mode IN ('derived', 'manual'))");
    }
};
