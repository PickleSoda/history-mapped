<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Staging table for pipeline relationship hints.
 *
 * When the Python pipeline scrapes Wikidata, it extracts relationship
 * properties (e.g., P36 = capital, P710 = participant) as hints containing
 * target Wikidata QIDs. These can't be resolved to entity_id references
 * at scrape time because the target entities may not be imported yet.
 *
 * This table holds the raw hints. After a batch import completes,
 * ResolveRelationshipsJob reads this table, looks up target entities
 * by wikidata_id, and creates actual relationship records.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('pipeline_relationship_hints', function (Blueprint $table) {
            $table->id();
            $table->uuid('source_entity_id');
            $table->string('relationship_type');
            $table->string('target_wikidata_id');
            $table->string('target_label')->nullable();
            $table->string('confidence')->default('medium');
            $table->string('wikidata_property')->nullable();
            $table->string('batch_id');
            $table->boolean('resolved')->default(false);
            $table->string('resolution_note')->nullable();
            $table->timestamp('created_at')->useCurrent();

            $table->index('batch_id');
            $table->index(['resolved', 'batch_id']);
            $table->index('target_wikidata_id');

            $table->foreign('source_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('pipeline_relationship_hints');
    }
};
