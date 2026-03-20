<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * Creates the `geometry_snapshots` table for storing time-varying PostGIS
     * geometries per entity. Each snapshot has a year range (year_start–year_end)
     * and at least one geometry column (geom or territory_geom).
     *
     * Enum-typed columns (confidence) are added via DB::statement() because the
     * `confidence_level` PG enum was created in a previous migration.
     */
    public function up(): void
    {
        Schema::create('geometry_snapshots', function (Blueprint $table) {
            $table->uuid('snapshot_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');

            // Temporal validity (integer years — negative = BCE)
            $table->integer('year_start');
            $table->integer('year_end');

            // Geometry (at least one must be non-null — enforced by CHECK constraint)
            $table->geometry('geom')->nullable();
            $table->geometry('territory_geom')->nullable();

            // Metadata
            $table->text('label')->nullable();
            $table->jsonb('source_citations')->nullable();
            $table->text('notes')->nullable();
            $table->integer('display_priority')->default(0);

            // Audit
            $table->text('created_by')->nullable();
            $table->timestamps();

            // Foreign key — cascade delete when parent entity is removed
            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->onDelete('cascade');
        });

        // confidence column uses the existing PostgreSQL enum type
        DB::statement('ALTER TABLE geometry_snapshots ADD COLUMN confidence confidence_level');

        // ── Constraints ──────────────────────────────────────────────────────

        DB::statement('ALTER TABLE geometry_snapshots ADD CONSTRAINT gs_has_geometry
            CHECK (geom IS NOT NULL OR territory_geom IS NOT NULL)');

        DB::statement('ALTER TABLE geometry_snapshots ADD CONSTRAINT gs_valid_year_range
            CHECK (year_start <= year_end)');

        // ── Indexes ──────────────────────────────────────────────────────────

        DB::statement('CREATE INDEX gs_entity_id_idx ON geometry_snapshots (entity_id)');
        DB::statement('CREATE INDEX gs_year_range_idx ON geometry_snapshots (year_start, year_end)');
        DB::statement('CREATE INDEX gs_entity_year_idx ON geometry_snapshots (entity_id, year_start, year_end)');
        DB::statement('CREATE INDEX gs_geom_gist_idx ON geometry_snapshots USING GIST (geom)');
        DB::statement('CREATE INDEX gs_territory_gist_idx ON geometry_snapshots USING GIST (territory_geom)');
        DB::statement('CREATE INDEX gs_territory_year_gist_idx ON geometry_snapshots USING GIST (territory_geom)
            WHERE territory_geom IS NOT NULL');
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('geometry_snapshots');
    }
};
