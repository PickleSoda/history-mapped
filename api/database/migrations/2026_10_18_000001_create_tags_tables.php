<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Tag vocabulary shared by chronicles and entities.
 *
 * `tags` is keyed by slug so the existing `entity_tags.tag` text column keeps
 * its meaning (it now holds a tag slug, enforced by FK). Each tag belongs to a
 * facet (era / region / theme / type / topic) and may have a parent; pivots
 * store the closure, so filtering by "asia" matches rows tagged "china".
 *
 * Pivot `source`: manual (admin or pipeline input — never overwritten),
 * curated (database/data/tags/chronicles.json), derived (computed by
 * `tags:sync`, replaced on every run).
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::create('tags', function (Blueprint $table) {
            $table->text('slug')->primary();
            $table->text('name');
            $table->string('facet', 16);
            $table->text('parent_slug')->nullable();
            $table->text('description')->nullable();
            // Era tags only: the year span used to derive the tag from dates.
            $table->integer('start_year')->nullable();
            $table->integer('end_year')->nullable();
            $table->integer('sort_order')->default(0);
            $table->timestamps();

            $table->index(['facet', 'sort_order']);
        });

        // Separate statement: the self-reference needs the primary key to exist.
        Schema::table('tags', function (Blueprint $table) {
            $table->foreign('parent_slug')
                ->references('slug')
                ->on('tags')
                ->cascadeOnUpdate()
                ->nullOnDelete();
        });

        Schema::create('chronicle_tags', function (Blueprint $table) {
            $table->uuid('chronicle_id');
            $table->text('tag');
            $table->string('source', 16)->default('manual');
            $table->timestamps();

            $table->primary(['chronicle_id', 'tag']);

            $table->foreign('chronicle_id')
                ->references('chronicle_id')
                ->on('chronicles')
                ->cascadeOnDelete();

            $table->foreign('tag')
                ->references('slug')
                ->on('tags')
                ->cascadeOnUpdate()
                ->cascadeOnDelete();

            $table->index('tag');
        });

        Schema::table('entity_tags', function (Blueprint $table) {
            $table->string('source', 16)->default('manual');
        });

        // Free-text tags written before the vocabulary existed become topic tags,
        // so the FK below holds for any rows already present.
        DB::statement(<<<'SQL'
            INSERT INTO tags (slug, name, facet, created_at, updated_at)
            SELECT DISTINCT tag, tag, 'topic', now(), now() FROM entity_tags
            ON CONFLICT (slug) DO NOTHING
        SQL);

        Schema::table('entity_tags', function (Blueprint $table) {
            $table->foreign('tag')
                ->references('slug')
                ->on('tags')
                ->cascadeOnUpdate()
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('entity_tags', function (Blueprint $table) {
            $table->dropForeign(['tag']);
            $table->dropColumn('source');
        });

        Schema::dropIfExists('chronicle_tags');
        Schema::dropIfExists('tags');
    }
};
