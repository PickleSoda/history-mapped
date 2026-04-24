<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('geometry_periods', function (Blueprint $table) {
            $table->uuid('geometry_period_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('period_type');
            $table->integer('start_year');
            $table->integer('end_year')->nullable();
            $table->geometry('geom')->nullable();
            $table->geometry('territory_geom')->nullable();
            $table->text('description')->nullable();
            $table->text('provenance_mode');
            $table->uuid('relationship_id')->nullable();
            $table->uuid('source_event_id')->nullable();
            $table->text('created_by')->nullable();
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();

            $table->foreign('relationship_id')
                ->references('relationship_id')
                ->on('relationships')
                ->cascadeOnDelete();

            $table->foreign('source_event_id')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();
        });

        DB::statement('ALTER TABLE geometry_periods ADD COLUMN confidence confidence_level');

        DB::statement('ALTER TABLE geometry_periods ADD CONSTRAINT gp_valid_year_range
            CHECK (end_year IS NULL OR start_year <= end_year)');

        DB::statement('ALTER TABLE geometry_periods ADD CONSTRAINT gp_has_geometry
            CHECK (geom IS NOT NULL OR territory_geom IS NOT NULL)');

        DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_provenance_mode
            CHECK (provenance_mode IN ('derived', 'manual'))");

        DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_derived_requires_source
            CHECK (
                provenance_mode <> 'derived'
                OR relationship_id IS NOT NULL
                OR source_event_id IS NOT NULL
            )");

        DB::statement("ALTER TABLE geometry_periods ADD CONSTRAINT gp_presence_requires_relationship
            CHECK (period_type <> 'presence' OR relationship_id IS NOT NULL)");

        DB::statement('CREATE INDEX gp_entity_idx ON geometry_periods (entity_id)');
        DB::statement('CREATE INDEX gp_year_range_idx ON geometry_periods (start_year, end_year)');
        DB::statement('CREATE INDEX gp_period_type_idx ON geometry_periods (period_type)');
        DB::statement('CREATE INDEX gp_relationship_id_idx ON geometry_periods (relationship_id)');
        DB::statement('CREATE INDEX gp_source_event_id_idx ON geometry_periods (source_event_id)');
        DB::statement('CREATE INDEX gp_geom_gist_idx ON geometry_periods USING GIST (geom)');
        DB::statement('CREATE INDEX gp_territory_geom_gist_idx ON geometry_periods USING GIST (territory_geom)');
        DB::statement("CREATE INDEX gp_active_range_gist_idx
            ON geometry_periods USING GIST (int4range(start_year, COALESCE(end_year, 2147483647), '[]'))");
        DB::statement("CREATE UNIQUE INDEX gp_unique_derived_presence_relationship_idx
            ON geometry_periods (relationship_id)
            WHERE relationship_id IS NOT NULL
              AND provenance_mode = 'derived'
              AND period_type = 'presence'");
    }

    public function down(): void
    {
        Schema::dropIfExists('geometry_periods');
    }
};
