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
     * All entity types are stored in a single table (STI pattern) with
     * type-specific data in a JSONB `attributes` column.
     * Includes all indexes (B-tree, GIN, HNSW, expression) in final form.
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
            $table->text('wikidata_id')->nullable()->index();

            // Content
            $table->text('summary')->nullable();
            $table->text('significance')->nullable();
            $table->integer('impact_score')->nullable()->index();
            $table->jsonb('attributes')->default('{}');

            // Verification
            $table->unsignedBigInteger('reviewer_id')->nullable();
            $table->timestamp('review_date')->nullable();

            // Sources
            $table->jsonb('source_citations')->nullable();

            // Embeddings (pgvector)
            $table->vector('embedding', 1536)->nullable();

            // Display
            $table->integer('display_priority')->nullable();

            // Audit
            $table->text('created_by')->nullable();
            $table->timestamps();

            // reviewer FK
            $table->foreign('reviewer_id')
                ->references('id')
                ->on('users');
        });

        // ──────────────────────────────────────────────
        // 2. Add columns that use PostgreSQL enum types
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
        // 3. Indexes
        // ──────────────────────────────────────────────

        // B-tree indexes on enum columns
        DB::statement('CREATE INDEX entities_entity_type_idx ON entities (entity_type)');
        DB::statement('CREATE INDEX entities_entity_group_idx ON entities (entity_group)');
        DB::statement('CREATE INDEX entities_verification_status_idx ON entities (verification_status)');

        // HNSW vector index for cosine similarity search
        DB::statement('CREATE INDEX entities_embedding_hnsw_idx ON entities USING hnsw (embedding vector_cosine_ops)');

        // GIN indexes
        DB::statement('CREATE INDEX entities_attributes_gin_idx ON entities USING gin (attributes)');
        DB::statement('CREATE INDEX entities_source_citations_gin_idx ON entities USING gin (source_citations)');

        // Full-text search on name
        DB::statement("CREATE INDEX entities_name_search_idx ON entities USING gin(to_tsvector('english', name))");

        // B-tree composite indexes
        DB::statement('CREATE INDEX entities_type_status_idx ON entities (entity_type, verification_status)');

        // ──────────────────────────────────────────────
        // 4. JSONB expression indexes for admin-panel filters
        // ──────────────────────────────────────────────

        DB::statement("CREATE INDEX entities_attr_political_subtype_idx
            ON entities ((attributes->>'political_subtype'))
            WHERE entity_type = 'political_entity'");

        DB::statement("CREATE INDEX entities_attr_government_type_idx
            ON entities ((attributes->>'government_type'))
            WHERE entity_type = 'political_entity'");

        DB::statement("CREATE INDEX entities_attr_settlement_subtype_idx
            ON entities ((attributes->>'settlement_subtype'))
            WHERE entity_type = 'city'");

        DB::statement("CREATE INDEX entities_attr_unit_subtype_idx
            ON entities ((attributes->>'unit_subtype'))
            WHERE entity_type = 'military_unit'");

        DB::statement("CREATE INDEX entities_attr_monument_subtype_idx
            ON entities ((attributes->>'monument_subtype'))
            WHERE entity_type = 'infrastructure_monument'");

        DB::statement("CREATE INDEX entities_attr_war_subtype_idx
            ON entities ((attributes->>'war_subtype'))
            WHERE entity_type = 'event_war'");

        DB::statement("CREATE INDEX entities_attr_battle_outcome_idx
            ON entities ((attributes->>'outcome'))
            WHERE entity_type = 'event_battle'");

        DB::statement("CREATE INDEX entities_attr_route_subtype_idx
            ON entities ((attributes->>'route_subtype'))
            WHERE entity_type = 'trade_route'");

        DB::statement("CREATE INDEX entities_attr_resource_category_idx
            ON entities ((attributes->>'resource_category'))
            WHERE entity_type = 'natural_resource'");

        DB::statement("CREATE INDEX entities_attr_epidemic_subtype_idx
            ON entities ((attributes->>'epidemic_subtype'))
            WHERE entity_type = 'epidemic_disease'");

        DB::statement("CREATE INDEX entities_attr_person_gender_idx
            ON entities ((attributes->>'gender'))
            WHERE entity_type = 'person'");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('entities');
    }
};
