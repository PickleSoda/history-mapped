<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('chronicle_entries', function (Blueprint $table) {
            $table->integer('start_year')->nullable()->after('sequence_order');
            $table->integer('end_year')->nullable()->after('start_year');
            $table->integer('impact_score')->nullable()->after('end_year');
            $table->jsonb('approximate_location')->nullable()->after('impact_score');
        });
    }

    public function down(): void
    {
        Schema::table('chronicle_entries', function (Blueprint $table) {
            $table->dropColumn(['start_year', 'end_year', 'impact_score', 'approximate_location']);
        });
    }
};