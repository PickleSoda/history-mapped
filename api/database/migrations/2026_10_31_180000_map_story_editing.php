<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Map stories edited in the admin and by the AI agent.
 *
 * The DB row is the live copy; resources/map-stories/*.json are seeds and
 * exports. `file_hash` (was `content_hash`) is the hash of the file content
 * last synced from or exported to disk, `synced_at` when that happened, and
 * `edited_at`/`edited_by` the last admin, AI or restore save. A row whose
 * `edited_at` is after `synced_at` holds edits the file lacks:
 * `map-stories:sync` keeps them and `map-stories:export` writes them out.
 *
 * `document` becomes `json` (not `jsonb`) so the stored text keeps the
 * authored key order, which `map-stories:export` needs to write a file
 * byte-identical to the builder's. jsonb reordered the existing rows' keys,
 * so their `file_hash` is cleared: the next `map-stories:sync` reloads them
 * from their files.
 *
 * `map_story_revisions` keeps the newest 50 versions of each story's
 * authored document (SaveMapStoryAction); a restore saves one of them again.
 * See docs/superpowers/plans/2026-10-31-map-story-admin-and-ai-editing.md.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('map_stories', function (Blueprint $table) {
            $table->renameColumn('content_hash', 'file_hash');
        });

        Schema::table('map_stories', function (Blueprint $table) {
            // Microseconds: a save right after a sync (or an export right after a save) must still order.
            $table->timestamp('synced_at', 6)->nullable();
            $table->timestamp('edited_at', 6)->nullable();
            $table->foreignId('edited_by')->nullable()->constrained('users')->nullOnDelete();
        });

        DB::statement('ALTER TABLE map_stories ALTER COLUMN document TYPE json USING document::json');
        DB::statement('UPDATE map_stories SET file_hash = NULL, synced_at = updated_at');

        Schema::create('map_story_revisions', function (Blueprint $table) {
            $table->id();
            $table->uuid('map_story_id');
            // The authored document (no resolved ids), key order kept.
            $table->json('document');
            $table->string('source', 16);
            $table->foreignId('user_id')->nullable()->constrained('users')->nullOnDelete();
            $table->text('note')->nullable();
            $table->timestamp('created_at')->useCurrent();

            $table->index(['map_story_id', 'id']);
            $table->foreign('map_story_id')
                ->references('story_id')
                ->on('map_stories')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('map_story_revisions');

        DB::statement('ALTER TABLE map_stories ALTER COLUMN document TYPE jsonb USING document::jsonb');

        Schema::table('map_stories', function (Blueprint $table) {
            $table->dropConstrainedForeignId('edited_by');
            $table->dropColumn(['edited_at', 'synced_at']);
        });

        Schema::table('map_stories', function (Blueprint $table) {
            $table->renameColumn('file_hash', 'content_hash');
        });
    }
};
