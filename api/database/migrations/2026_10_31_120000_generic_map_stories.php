<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Map stories, schema 3: a story belongs to an entity, a chronicle (its map
 * layer), or both, and opt-in stories show faintly on the plain atlas
 * (ambient mode). `period_*`, `bbox` and `ambient_steps` are precomputed by
 * `map-stories:sync` (SyncMapStoryFileAction) for GET /map-stories/ambient.
 * See docs/superpowers/plans/2026-10-31-generic-map-stories.md.
 *
 * A story needs one attachment. Deleting a chronicle nulls its stories'
 * `chronicle_id`; a story that had only the chronicle is deleted with it
 * (a trigger), since it would otherwise break the check.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('map_stories', function (Blueprint $table) {
            $table->uuid('chronicle_id')->nullable();
            $table->integer('period_start')->nullable();
            $table->integer('period_end')->nullable();
            $table->boolean('ambient')->default(false);
            // An SRID-4326 envelope, like ref_geographic_regions.bounding_box.
            $table->geometry('bbox')->nullable();
            // [{index, start, title, features: FeatureCollection}], ambient stories only.
            $table->jsonb('ambient_steps')->nullable();

            $table->index('chronicle_id');
            $table->index(['ambient', 'period_start', 'period_end']);
            $table->foreign('chronicle_id')
                ->references('chronicle_id')
                ->on('chronicles')
                ->nullOnDelete();
        });

        DB::statement('ALTER TABLE map_stories ALTER COLUMN entity_id DROP NOT NULL');
        DB::statement('ALTER TABLE map_stories ADD CONSTRAINT map_stories_attached
            CHECK (entity_id IS NOT NULL OR chronicle_id IS NOT NULL)');
        DB::statement('CREATE INDEX map_stories_bbox_gist_idx ON map_stories USING GIST (bbox)');

        DB::statement(<<<'SQL'
CREATE OR REPLACE FUNCTION map_stories_drop_chronicle_layers()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM map_stories WHERE chronicle_id = OLD.chronicle_id AND entity_id IS NULL;
    RETURN OLD;
END;
$$
SQL);
        DB::statement('CREATE TRIGGER map_stories_drop_chronicle_layers_trigger
            BEFORE DELETE ON chronicles
            FOR EACH ROW
            EXECUTE FUNCTION map_stories_drop_chronicle_layers()');
    }

    public function down(): void
    {
        DB::statement('DROP TRIGGER IF EXISTS map_stories_drop_chronicle_layers_trigger ON chronicles');
        DB::statement('DROP FUNCTION IF EXISTS map_stories_drop_chronicle_layers()');
        DB::statement('DELETE FROM map_stories WHERE entity_id IS NULL');
        DB::statement('ALTER TABLE map_stories DROP CONSTRAINT IF EXISTS map_stories_attached');
        DB::statement('DROP INDEX IF EXISTS map_stories_bbox_gist_idx');

        Schema::table('map_stories', function (Blueprint $table) {
            $table->dropForeign(['chronicle_id']);
            $table->dropIndex(['ambient', 'period_start', 'period_end']);
            $table->dropIndex(['chronicle_id']);
            $table->dropColumn(['chronicle_id', 'period_start', 'period_end', 'ambient', 'bbox', 'ambient_steps']);
        });

        DB::statement('ALTER TABLE map_stories ALTER COLUMN entity_id SET NOT NULL');
    }
};
