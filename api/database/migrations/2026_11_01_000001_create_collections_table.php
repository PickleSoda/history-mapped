<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Curated collections for the public site's browse pages: editorial,
 * file-authored sets (resources/collections/<slug>.json) loaded by
 * `collections:sync`. `items` is the ordered list of
 * `{kind: entity|chronicle|story|tag, ref, note?}`; refs are Wikidata ids
 * (entities) or slugs, resolved when served, so merges and re-imports that
 * change uuids do not break a set. See docs/schemas/collections.md.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('collections', function (Blueprint $table) {
            $table->uuid('collection_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->text('slug')->unique();
            $table->text('title');
            $table->text('subtitle')->nullable();
            // Markdown.
            $table->text('description')->nullable();
            $table->uuid('cover_entity_id')->nullable();
            $table->jsonb('items')->default(DB::raw("'[]'::jsonb"));
            $table->string('status', 16)->default('published');
            $table->integer('sort_order')->default(0);
            $table->timestamps();

            $table->index(['status', 'sort_order']);
            $table->foreign('cover_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();
        });

        DB::statement("ALTER TABLE collections ADD CONSTRAINT collections_status_check CHECK (status IN ('draft', 'published'))");
    }

    public function down(): void
    {
        Schema::dropIfExists('collections');
    }
};
