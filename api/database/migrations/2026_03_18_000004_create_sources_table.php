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
     * Creates the sources table (entity spec section 5).
     * Tracks every ingested document/dataset with its reliability metadata.
     */
    public function up(): void
    {
        Schema::create('sources', function (Blueprint $table) {
            $table->uuid('source_id')->primary()->default(DB::raw('gen_random_uuid()'));

            $table->text('title');

            // source_type — added via DB::statement below (PG enum reliability_tier)

            $table->text('document_type')->nullable();
            $table->text('author')->nullable();
            $table->text('date_created')->nullable();
            $table->text('date_discovered')->nullable();
            $table->text('language')->nullable();
            $table->text('current_location')->nullable();
            $table->text('source_url')->nullable();
            $table->text('content_hash')->nullable();
            $table->timestamp('ingestion_date')->nullable();
            $table->text('geographic_scope')->nullable();
            $table->text('temporal_scope')->nullable();
            $table->text('contemporaneity')->nullable();
            $table->text('author_bias')->nullable();
            $table->text('corroboration')->nullable();
            $table->text('scholarly_consensus')->nullable();
            $table->text('raw_file_path')->nullable();
            $table->text('nlp_output_path')->nullable();
            $table->text('llm_log_path')->nullable();

            $table->timestamps();

            // ── Standard indexes ──────────────────────────
            // source_type index added via DB::statement below
            $table->unique('content_hash');
        });

        // ── PG enum column ───────────────────────────────
        DB::statement('
            ALTER TABLE sources
                ADD COLUMN source_type reliability_tier NOT NULL
        ');

        // ── Indexes requiring raw SQL ────────────────────

        // B-tree on the enum column
        DB::statement('
            CREATE INDEX sources_source_type_index
                ON sources (source_type)
        ');

        // Full-text search on title (GIN with to_tsvector)
        DB::statement("
            CREATE INDEX sources_title_fulltext_index
                ON sources USING GIN (to_tsvector('english', title))
        ");
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('sources');
    }
};
