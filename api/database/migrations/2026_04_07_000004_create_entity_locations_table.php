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
        Schema::create('entity_locations', function (Blueprint $table) {
            $table->uuid('location_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('location_name')->nullable();
            $table->geometry('geom')->nullable();
            $table->geometry('territory_geom')->nullable();
            $table->text('location_method')->nullable();
            $table->text('location_confidence')->nullable();
            $table->boolean('is_primary')->default(false);
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement("ALTER TABLE entity_locations ADD CONSTRAINT el_has_locator
            CHECK (location_name IS NOT NULL OR geom IS NOT NULL OR territory_geom IS NOT NULL)");

        DB::statement('CREATE INDEX el_entity_idx ON entity_locations (entity_id)');
        DB::statement('CREATE INDEX el_geom_gist_idx ON entity_locations USING GIST (geom)');
        DB::statement('CREATE INDEX el_territory_geom_gist_idx ON entity_locations USING GIST (territory_geom)');
    }

    public function down(): void
    {
        Schema::dropIfExists('entity_locations');
    }
};
