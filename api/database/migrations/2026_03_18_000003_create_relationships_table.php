<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * Creates the relationships table (entity spec section 6).
     * Links any two entities with a typed, temporally-scoped relationship.
     */
    public function up(): void
    {
        Schema::create('relationships', function (Blueprint $table) {
            $table->uuid('relationship_id')->primary()->default(DB::raw('gen_random_uuid()'));

            $table->uuid('source_entity_id');
            $table->uuid('target_entity_id');

            // relationship_type — added via DB::statement below (PG enum)

            $table->text('temporal_start')->nullable();
            $table->text('temporal_end')->nullable();
            $table->text('description')->nullable();

            // confidence — added via DB::statement below (PG enum)

            $table->jsonb('source_citations')->nullable();

            $table->timestamp('created_at')->nullable();
            $table->text('created_by')->nullable();

            // ── Foreign keys ──────────────────────────────
            $table->foreign('source_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->onDelete('cascade');

            $table->foreign('target_entity_id')
                ->references('entity_id')
                ->on('entities')
                ->onDelete('cascade');

            // ── Standard B-tree indexes ───────────────────
            $table->index('source_entity_id');
            $table->index('target_entity_id');
            // relationship_type index added via DB::statement below

            // Temporal year range
            $table->integer('start_year')->nullable();
            $table->integer('end_year')->nullable();

            // Geometry period derivation toggle
            $table->boolean('derive_geometry_period')->default(true);
        });

        // ── PG enum columns ──────────────────────────────
        DB::statement('
            ALTER TABLE relationships
                ADD COLUMN relationship_type relationship_type NOT NULL
        ');

        DB::statement('
            ALTER TABLE relationships
            ADD COLUMN confidence confidence_level
        ');

        DB::unprepared(<<<'SQL'
CREATE OR REPLACE FUNCTION relationships_sync_years()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.start_year := CASE
        WHEN NEW.temporal_start IS NULL
            THEN NULL
        WHEN NEW.temporal_start !~ '^-?\d+'
            THEN NEW.start_year
        ELSE CAST(SUBSTRING(NEW.temporal_start FROM '^-?\d+') AS integer)
    END;

    NEW.end_year := CASE
        WHEN NEW.temporal_end IS NULL
            THEN NULL
        WHEN NEW.temporal_end !~ '^-?\d+'
            THEN NEW.end_year
        ELSE CAST(SUBSTRING(NEW.temporal_end FROM '^-?\d+') AS integer)
    END;

    RETURN NEW;
END;
$$;
SQL);

        DB::statement('CREATE TRIGGER relationships_sync_years_trigger
            BEFORE INSERT OR UPDATE ON relationships
            FOR EACH ROW
            EXECUTE FUNCTION relationships_sync_years()');

        DB::statement('ALTER TABLE relationships ADD CONSTRAINT relationships_valid_year_range
            CHECK (start_year IS NULL OR end_year IS NULL OR start_year <= end_year)');

        // ── Indexes requiring raw SQL ────────────────────

        // B-tree on the enum column
        DB::statement('
            CREATE INDEX relationships_relationship_type_index
                ON relationships (relationship_type)
        ');

        // Composite indexes
        DB::statement('
            CREATE INDEX relationships_source_entity_id_relationship_type_index
                ON relationships (source_entity_id, relationship_type)
        ');

        DB::statement('
            CREATE INDEX relationships_target_entity_id_relationship_type_index
                ON relationships (target_entity_id, relationship_type)
        ');

        DB::statement('CREATE INDEX relationships_start_year_idx ON relationships (start_year)');
        DB::statement('CREATE INDEX relationships_end_year_idx ON relationships (end_year)');
        DB::statement('CREATE INDEX relationships_year_range_idx ON relationships (start_year, end_year)');
        DB::statement("CREATE INDEX relationships_active_range_gist_idx
            ON relationships USING GIST (int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year + 1 END, '[)'))");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('relationships');
        DB::unprepared('DROP FUNCTION IF EXISTS relationships_sync_years()');
    }
};
