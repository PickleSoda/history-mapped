<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Index the three columns that reference entities without a leading index.
 * Without them every entity delete or merge scans these tables in full
 * (pipeline_relationship_hints passes a million rows once the bulk Wikidata
 * waves land), and GET /entities/{id}/chronicles scans
 * chronicle_entry_entities, whose primary key leads with entry_id.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('pipeline_relationship_hints', function (Blueprint $table): void {
            $table->index('source_entity_id');
        });
        Schema::table('chronicle_entry_entities', function (Blueprint $table): void {
            $table->index('entity_id');
        });
        Schema::table('entity_timeline_entries', function (Blueprint $table): void {
            $table->index('location_entity_id');
        });
    }

    public function down(): void
    {
        Schema::table('pipeline_relationship_hints', function (Blueprint $table): void {
            $table->dropIndex(['source_entity_id']);
        });
        Schema::table('chronicle_entry_entities', function (Blueprint $table): void {
            $table->dropIndex(['entity_id']);
        });
        Schema::table('entity_timeline_entries', function (Blueprint $table): void {
            $table->dropIndex(['location_entity_id']);
        });
    }
};
