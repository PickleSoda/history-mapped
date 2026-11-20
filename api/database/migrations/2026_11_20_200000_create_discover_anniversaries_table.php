<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * What happened on each day of the year, for GET /discover/on-this-day.
 *
 * Finding the entities with a real day in their dates means a regex over
 * 594k `entity_temporal_ranges` rows and a read of 477k people's attributes
 * in the 1 GB `entities` heap, far too much per request. This table holds the
 * answer: one row per entity and kind (born, died, happened…), with the
 * impact and whether it is on the map copied in so a day is read and ordered
 * from one index. `php artisan discover:build-anniversaries` rebuilds it.
 *
 * `date` is the date as text ("1815-11-20", "-0753-04-21"); `year` is its
 * year, BCE negative.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('discover_anniversaries', function (Blueprint $table): void {
            $table->uuid('entity_id');
            $table->string('kind', 12);
            $table->smallInteger('month');
            $table->smallInteger('day');
            $table->integer('year');
            $table->text('date');
            $table->smallInteger('impact')->default(0);
            $table->boolean('placed')->default(false);

            $table->primary(['entity_id', 'kind']);
            $table->foreign('entity_id')->references('entity_id')->on('entities')->cascadeOnDelete();
        });

        // The order a day is read in: placed first, then by impact.
        DB::statement('CREATE INDEX discover_anniversaries_day_idx ON discover_anniversaries (month, day, placed DESC, impact DESC)');
    }

    public function down(): void
    {
        Schema::dropIfExists('discover_anniversaries');
    }
};
