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
        Schema::create('entity_timeline_entries', function (Blueprint $table) {
            $table->uuid('timeline_entry_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('entry_kind');
            $table->integer('start_year');
            $table->integer('end_year')->nullable();
            $table->text('title');
            $table->text('description')->nullable();
            $table->uuid('location_entity_id')->nullable();
            $table->geometry('geom')->nullable();
            $table->geometry('territory_geom')->nullable();
            $table->text('source_table');
            $table->uuid('source_id');

            // Relationship metadata (nullable — only set for relationship entries)
            $table->text('relationship_type')->nullable();
            $table->uuid('related_entity_id')->nullable();
            $table->text('related_entity_name')->nullable();

            $table->timestamp('derived_at')->useCurrent();
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();

            $table->foreign('location_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();

            $table->foreign('related_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();
        });

        DB::statement('ALTER TABLE entity_timeline_entries ADD CONSTRAINT ete_valid_year_range
            CHECK (end_year IS NULL OR start_year <= end_year)');

        DB::statement('CREATE INDEX ete_entity_year_idx ON entity_timeline_entries (entity_id, start_year, end_year)');
        DB::statement('CREATE INDEX ete_source_idx ON entity_timeline_entries (source_table, source_id)');
        DB::statement('CREATE INDEX ete_entry_kind_idx ON entity_timeline_entries (entry_kind)');
        DB::statement('CREATE INDEX ete_geom_gist_idx ON entity_timeline_entries USING GIST (geom)');
        DB::statement('CREATE INDEX ete_territory_geom_gist_idx ON entity_timeline_entries USING GIST (territory_geom)');
        DB::statement('CREATE INDEX ete_entity_relationship_type_idx ON entity_timeline_entries (entity_id, relationship_type)');
        DB::statement('CREATE INDEX ete_related_entity_id_idx ON entity_timeline_entries (related_entity_id)');
        DB::statement("CREATE INDEX ete_active_range_gist_idx
            ON entity_timeline_entries USING GIST (int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year + 1 END, '[)'))");
    }

    public function down(): void
    {
        Schema::dropIfExists('entity_timeline_entries');
    }
};
