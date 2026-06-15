<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('CREATE UNIQUE INDEX IF NOT EXISTS gp_entity_period_unique_idx ON geometry_periods (entity_id, geometry_period_id)');

        DB::statement('ALTER TABLE entity_geo_refs ADD COLUMN IF NOT EXISTS geometry_period_id uuid NULL');

        DB::statement('ALTER TABLE entity_geo_refs DROP CONSTRAINT IF EXISTS egr_geometry_period_fk');
        DB::statement('ALTER TABLE entity_geo_refs ADD CONSTRAINT egr_geometry_period_fk
            FOREIGN KEY (geometry_period_id)
            REFERENCES geometry_periods (geometry_period_id)
            ON DELETE CASCADE');

        DB::statement('ALTER TABLE entity_geo_refs DROP CONSTRAINT IF EXISTS egr_geometry_period_owner_fk');
        DB::statement('ALTER TABLE entity_geo_refs ADD CONSTRAINT egr_geometry_period_owner_fk
            FOREIGN KEY (entity_id, geometry_period_id)
            REFERENCES geometry_periods (entity_id, geometry_period_id)
            ON DELETE CASCADE');

        DB::statement('DROP INDEX IF EXISTS egr_entity_external_unique_idx');
        DB::statement('CREATE UNIQUE INDEX egr_entity_external_unique_root_idx
            ON entity_geo_refs (entity_id, provider, external_type, external_id)
            WHERE geometry_period_id IS NULL');
        DB::statement('CREATE UNIQUE INDEX egr_entity_external_period_unique_idx
            ON entity_geo_refs (entity_id, provider, external_type, external_id, geometry_period_id)
            WHERE geometry_period_id IS NOT NULL');
        DB::statement('CREATE INDEX IF NOT EXISTS egr_geometry_period_idx ON entity_geo_refs (geometry_period_id)');
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS egr_geometry_period_idx');
        DB::statement('DROP INDEX IF EXISTS egr_entity_external_period_unique_idx');
        DB::statement('DROP INDEX IF EXISTS egr_entity_external_unique_root_idx');
        DB::statement('CREATE UNIQUE INDEX egr_entity_external_unique_idx ON entity_geo_refs (entity_id, provider, external_type, external_id)');

        DB::statement('ALTER TABLE entity_geo_refs DROP CONSTRAINT IF EXISTS egr_geometry_period_owner_fk');
        DB::statement('ALTER TABLE entity_geo_refs DROP CONSTRAINT IF EXISTS egr_geometry_period_fk');
        DB::statement('ALTER TABLE entity_geo_refs DROP COLUMN IF EXISTS geometry_period_id');

        DB::statement('DROP INDEX IF EXISTS gp_entity_period_unique_idx');
    }
};
