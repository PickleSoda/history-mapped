<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('chronicles', function (Blueprint $table) {
            $table->integer('start_year')->nullable()->after('status');
            $table->integer('end_year')->nullable()->after('start_year');
            $table->integer('impact_score')->nullable()->after('end_year');
            // Using a JSONB column for approximate location to store lat/lng or a simple point representation
            // Alternatively, a dedicated point column if PostGIS is strictly used, but JSONB is safer for general Laravel setups unless PostGIS is confirmed.
            // Given the requirement for "approximate location, not exact, for bounding box queries based on zoom level", a JSONB with lat/lng is flexible.
            $table->jsonb('approximate_location')->nullable()->after('impact_score');
        });
    }

    public function down(): void
    {
        Schema::table('chronicles', function (Blueprint $table) {
            $table->dropColumn(['start_year', 'end_year', 'impact_score', 'approximate_location']);
        });
    }
};