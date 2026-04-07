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
        Schema::create('entity_temporal_ranges', function (Blueprint $table) {
            $table->uuid('temporal_range_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('range_type')->default('primary'); // primary | secondary | disputed
            $table->integer('start_year')->nullable();
            $table->integer('end_year')->nullable();
            $table->text('start_date')->nullable(); // ISO-8601 string
            $table->text('end_date')->nullable();
            $table->text('duration_type')->nullable();
            $table->text('date_method')->nullable();
            $table->text('date_confidence')->nullable();
            $table->boolean('is_primary')->default(false);
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement("ALTER TABLE entity_temporal_ranges ADD CONSTRAINT etr_valid_year_range
            CHECK (start_year IS NULL OR end_year IS NULL OR start_year <= end_year)");

        DB::statement('CREATE INDEX etr_entity_idx ON entity_temporal_ranges (entity_id)');
        DB::statement('CREATE INDEX etr_year_range_idx ON entity_temporal_ranges (start_year, end_year)');
    }

    public function down(): void
    {
        Schema::dropIfExists('entity_temporal_ranges');
    }
};
