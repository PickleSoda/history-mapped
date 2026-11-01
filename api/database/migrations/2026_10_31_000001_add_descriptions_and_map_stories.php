<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Long-form text and battle maps.
 *
 * `entities.description` and `chronicles.description` hold several plain
 * paragraphs (the one-sentence `summary` stays the lead). `map_stories` holds
 * step-by-step battle maps attached to an entity: the schema-1 document from
 * resources/map-stories/*.json, with its Q-ids resolved to entity ids
 * (MapStoryDocument, `map-stories:sync`). See
 * docs/superpowers/specs/2026-10-31-battle-maps-and-descriptions-design.md.
 *
 * up() tolerates a second run. On prod (2026-10-31) its DDL committed but
 * the ledger insert after it failed (a content load had reset
 * migrations_id_seq; see db:repair-sequences), so the next migrate runs it
 * again over the existing columns and table.
 */
return new class extends Migration
{
    public function up(): void
    {
        foreach (['entities', 'chronicles'] as $name) {
            if (! Schema::hasColumn($name, 'description')) {
                Schema::table($name, function (Blueprint $table) {
                    $table->text('description')->nullable();
                });
            }
        }

        if (Schema::hasTable('map_stories')) {
            return;
        }

        Schema::create('map_stories', function (Blueprint $table) {
            $table->uuid('story_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('slug')->unique();
            $table->string('kind', 24);
            $table->text('title');
            $table->integer('year')->nullable();
            $table->smallInteger('step_count')->default(0);
            $table->jsonb('document');
            $table->text('source_path')->nullable();
            $table->text('content_hash')->nullable();
            $table->timestamps();

            $table->index('entity_id');
            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('map_stories');

        Schema::table('chronicles', function (Blueprint $table) {
            $table->dropColumn('description');
        });

        Schema::table('entities', function (Blueprint $table) {
            $table->dropColumn('description');
        });
    }
};
