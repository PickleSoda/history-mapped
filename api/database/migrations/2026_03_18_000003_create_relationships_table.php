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
        });

        // ── PG enum columns ──────────────────────────────
        DB::statement("
            ALTER TABLE relationships
                ADD COLUMN relationship_type relationship_type NOT NULL
        ");

        DB::statement("
            ALTER TABLE relationships
                ADD COLUMN confidence confidence_level
        ");

        // ── Indexes requiring raw SQL ────────────────────

        // B-tree on the enum column
        DB::statement("
            CREATE INDEX relationships_relationship_type_index
                ON relationships (relationship_type)
        ");

        // Composite indexes
        DB::statement("
            CREATE INDEX relationships_source_entity_id_relationship_type_index
                ON relationships (source_entity_id, relationship_type)
        ");

        DB::statement("
            CREATE INDEX relationships_target_entity_id_relationship_type_index
                ON relationships (target_entity_id, relationship_type)
        ");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('relationships');
    }
};
