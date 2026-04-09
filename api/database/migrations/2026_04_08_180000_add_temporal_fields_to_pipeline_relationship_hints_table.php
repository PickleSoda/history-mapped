<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('pipeline_relationship_hints', function (Blueprint $table) {
            if (! Schema::hasColumn('pipeline_relationship_hints', 'temporal_start')) {
                $table->text('temporal_start')->nullable()->after('target_label');
            }

            if (! Schema::hasColumn('pipeline_relationship_hints', 'temporal_end')) {
                $table->text('temporal_end')->nullable()->after('temporal_start');
            }
        });
    }

    public function down(): void
    {
        Schema::table('pipeline_relationship_hints', function (Blueprint $table) {
            if (Schema::hasColumn('pipeline_relationship_hints', 'temporal_start')) {
                $table->dropColumn('temporal_start');
            }

            if (Schema::hasColumn('pipeline_relationship_hints', 'temporal_end')) {
                $table->dropColumn('temporal_end');
            }
        });
    }
};
