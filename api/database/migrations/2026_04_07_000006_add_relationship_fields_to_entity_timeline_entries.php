<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('entity_timeline_entries', function (Blueprint $table) {
            $table->text('relationship_type')->nullable()->after('source_id');
            $table->uuid('related_entity_id')->nullable()->after('relationship_type');
            $table->text('related_entity_name')->nullable()->after('related_entity_id');

            $table->foreign('related_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();

            $table->index(['entity_id', 'relationship_type'], 'ete_entity_relationship_type_idx');
            $table->index('related_entity_id', 'ete_related_entity_id_idx');
        });
    }

    public function down(): void
    {
        Schema::table('entity_timeline_entries', function (Blueprint $table) {
            $table->dropIndex('ete_related_entity_id_idx');
            $table->dropIndex('ete_entity_relationship_type_idx');
            $table->dropForeign(['related_entity_id']);

            $table->dropColumn(['relationship_type', 'related_entity_id', 'related_entity_name']);
        });
    }
};