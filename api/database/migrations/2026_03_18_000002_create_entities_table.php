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
     * Creates the main `entities` table for the Historical Atlas platform.
     * All 30 entity types are stored in a single table (STI pattern) with
     * type-specific data in a JSONB `attributes` column.
     *
     * Enum-typed columns are added via DB::statement() because the PG enum
     * types were created in a previous migration and cannot be expressed
     * through the Laravel schema builder.
     */
    public function up(): void
    {
        // ──────────────────────────────────────────────
        // 1. Create table with native Laravel columns
        // ──────────────────────────────────────────────

        Schema::create('entities', function (Blueprint $table) {
            // Core identity
            $table->uuid('entity_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->text('name');
            $table->text('alternative_names')->nullable(); // placeholder, replaced below
            $table->text('wikidata_id')->nullable()->index();

            // Spatial (PostGIS macros)
            $table->geometry('geom')->nullable();
            $table->geometry('territory_geom')->nullable();
            $table->text('location_name')->nullable();

            // Temporal
            $table->text('temporal_start')->nullable()->index();
            $table->text('temporal_end')->nullable()->index();
            $table->text('date_raw')->nullable();

            // Content
            $table->text('summary')->nullable();
            $table->text('significance')->nullable();
            $table->text('confidence_notes')->nullable();
            $table->text('tags')->nullable();        // placeholder, replaced below
            $table->integer('impact_score')->nullable()->index();
            $table->jsonb('attributes')->default('{}');

            // Hierarchy
            $table->uuid('parent_entity_id')->nullable()->index();
            $table->uuid('successor_entity_id')->nullable()->index();

            // Verification
            $table->unsignedBigInteger('reviewer_id')->nullable();
            $table->timestamp('review_date')->nullable();
            $table->text('validation_flags')->nullable(); // placeholder, replaced below

            // Sources / Media
            $table->jsonb('source_citations')->nullable();
            $table->jsonb('media_refs')->nullable();

            // Embeddings (pgvector)
            $table->vector('embedding', 1536)->nullable();
            $table->text('embedding_version')->nullable();

            // Display
            $table->integer('display_priority')->nullable();
            $table->text('entity_color')->nullable();

            // Computed / cached
            $table->jsonb('confidence_breakdown')->nullable();
            $table->jsonb('relationship_summary')->nullable();
            $table->integer('source_diversity_score')->nullable();
            $table->text('temporal_display_range')->nullable();
            $table->integer('nearby_entity_count')->nullable();
            $table->integer('cluster_id')->nullable();
            $table->text('era_label')->nullable();

            // Audit
            $table->text('created_by')->nullable();
            $table->timestamps();

            // reviewer FK (non-self-referencing — safe here)
            $table->foreign('reviewer_id')
                ->references('id')
                ->on('users');
        });

        // Self-referencing FKs must be added AFTER the table (and its PK) exist.
        Schema::table('entities', function (Blueprint $table) {
            $table->foreign('parent_entity_id')
                ->references('entity_id')
                ->on('entities');

            $table->foreign('successor_entity_id')
                ->references('entity_id')
                ->on('entities');
        });

        // ──────────────────────────────────────────────
        // 2. Replace placeholder columns with proper PG array types
        // ──────────────────────────────────────────────

        DB::statement('ALTER TABLE entities ALTER COLUMN alternative_names TYPE text[] USING NULL');
        DB::statement('ALTER TABLE entities ALTER COLUMN tags TYPE text[] USING NULL');
        DB::statement('ALTER TABLE entities ALTER COLUMN validation_flags TYPE text[] USING NULL');

        // ──────────────────────────────────────────────
        // 3. Add columns that use PostgreSQL enum types
        // ──────────────────────────────────────────────

        // Core identity
        DB::statement("ALTER TABLE entities ADD COLUMN entity_type entity_type NOT NULL");
        DB::statement("ALTER TABLE entities ADD COLUMN entity_group entity_group NOT NULL");

        // Spatial
        DB::statement("ALTER TABLE entities ADD COLUMN location_confidence confidence_level");
        DB::statement("ALTER TABLE entities ADD COLUMN location_method location_resolution_method");

        // Temporal
        DB::statement("ALTER TABLE entities ADD COLUMN date_method date_resolution_method");
        DB::statement("ALTER TABLE entities ADD COLUMN date_confidence confidence_level");
        DB::statement("ALTER TABLE entities ADD COLUMN duration_type duration_type");

        // Verification
        DB::statement("ALTER TABLE entities ADD COLUMN verification_status verification_status NOT NULL DEFAULT 'pipeline_draft'");
        DB::statement("ALTER TABLE entities ADD COLUMN confidence confidence_level");

        // Display
        DB::statement("ALTER TABLE entities ADD COLUMN icon_class icon_class");

        // ──────────────────────────────────────────────
        // 4. Indexes
        // ──────────────────────────────────────────────

        // B-tree indexes on enum columns
        DB::statement('CREATE INDEX entities_entity_type_idx ON entities (entity_type)');
        DB::statement('CREATE INDEX entities_entity_group_idx ON entities (entity_group)');
        DB::statement('CREATE INDEX entities_verification_status_idx ON entities (verification_status)');

        // GIST spatial indexes
        DB::statement('CREATE INDEX entities_geom_gist_idx ON entities USING gist (geom)');
        DB::statement('CREATE INDEX entities_territory_geom_gist_idx ON entities USING gist (territory_geom)');

        // HNSW vector index for cosine similarity search
        DB::statement('CREATE INDEX entities_embedding_hnsw_idx ON entities USING hnsw (embedding vector_cosine_ops)');

        // GIN indexes
        DB::statement('CREATE INDEX entities_tags_gin_idx ON entities USING gin (tags)');
        DB::statement('CREATE INDEX entities_attributes_gin_idx ON entities USING gin (attributes)');
        DB::statement('CREATE INDEX entities_source_citations_gin_idx ON entities USING gin (source_citations)');

        // Full-text search on name
        DB::statement("CREATE INDEX entities_name_search_idx ON entities USING gin(to_tsvector('english', name))");

        // B-tree composite indexes
        DB::statement('CREATE INDEX entities_type_status_idx ON entities (entity_type, verification_status)');
        DB::statement('CREATE INDEX entities_temporal_range_idx ON entities (temporal_start, temporal_end)');
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('entities');
    }
};
