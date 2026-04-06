<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("DO $$ BEGIN
            CREATE TYPE geo_ref_provider AS ENUM ('ohm', 'wikidata', 'geonames', 'pleiades', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;");

        DB::statement("DO $$ BEGIN
            CREATE TYPE geo_ref_external_type AS ENUM ('node', 'way', 'relation', 'feature', 'qid');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;");

        DB::statement("DO $$ BEGIN
            CREATE TYPE geo_ref_match_role AS ENUM ('primary', 'candidate', 'fallback', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;");

        DB::statement("DO $$ BEGIN
            CREATE TYPE geo_ref_retrieval_method AS ENUM ('overpass', 'nominatim', 'rest', 'manual');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;");

        Schema::create('entity_geo_refs', function (Blueprint $table) {
            $table->uuid('geo_ref_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('external_id');
            $table->text('temporal_start')->nullable();
            $table->text('temporal_end')->nullable();
            $table->integer('temporal_start_year')->nullable();
            $table->integer('temporal_end_year')->nullable();
            $table->jsonb('external_tags')->nullable();
            $table->jsonb('source_meta')->nullable();
            $table->decimal('match_score', 6, 4)->nullable();
            $table->boolean('is_active')->default(true);
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement('ALTER TABLE entity_geo_refs ADD COLUMN provider geo_ref_provider NOT NULL');
        DB::statement('ALTER TABLE entity_geo_refs ADD COLUMN external_type geo_ref_external_type NOT NULL');
        DB::statement('ALTER TABLE entity_geo_refs ADD COLUMN match_role geo_ref_match_role NOT NULL');
        DB::statement('ALTER TABLE entity_geo_refs ADD COLUMN retrieval_method geo_ref_retrieval_method NOT NULL');

        DB::statement('ALTER TABLE entity_geo_refs ADD CONSTRAINT egr_valid_year_range
            CHECK (
                temporal_start_year IS NULL
                OR temporal_end_year IS NULL
                OR temporal_start_year <= temporal_end_year
            )');

        DB::statement('CREATE UNIQUE INDEX egr_entity_geo_ref_idx ON entity_geo_refs (entity_id, geo_ref_id)');
        DB::statement('CREATE UNIQUE INDEX egr_entity_external_unique_idx ON entity_geo_refs (entity_id, provider, external_type, external_id)');
        DB::statement('CREATE INDEX egr_lookup_idx ON entity_geo_refs (provider, external_type, external_id, is_active)');
        DB::statement('CREATE INDEX egr_entity_role_active_idx ON entity_geo_refs (entity_id, match_role, is_active)');
        DB::statement('CREATE INDEX egr_temporal_year_idx ON entity_geo_refs (temporal_start_year, temporal_end_year)');
        DB::statement("CREATE UNIQUE INDEX egr_one_active_primary_per_entity_idx
            ON entity_geo_refs (entity_id)
            WHERE match_role = 'primary' AND is_active = true");

        Schema::table('entities', function (Blueprint $table) {
            $table->uuid('primary_geo_ref_id')->nullable()->after('successor_entity_id');
            $table->index('primary_geo_ref_id', 'entities_primary_geo_ref_idx');
        });

        DB::statement('ALTER TABLE entities
            ADD CONSTRAINT entities_primary_geo_ref_fk
            FOREIGN KEY (primary_geo_ref_id)
            REFERENCES entity_geo_refs (geo_ref_id)
            ON DELETE SET NULL');

        DB::statement('ALTER TABLE entities
            ADD CONSTRAINT entities_primary_geo_ref_owner_fk
            FOREIGN KEY (entity_id, primary_geo_ref_id)
            REFERENCES entity_geo_refs (entity_id, geo_ref_id)');
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_primary_geo_ref_owner_fk');
        DB::statement('ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_primary_geo_ref_fk');

        Schema::table('entities', function (Blueprint $table) {
            $table->dropIndex('entities_primary_geo_ref_idx');
            $table->dropColumn('primary_geo_ref_id');
        });

        DB::statement('DROP INDEX IF EXISTS egr_one_active_primary_per_entity_idx');
        DB::statement('DROP INDEX IF EXISTS egr_temporal_year_idx');
        DB::statement('DROP INDEX IF EXISTS egr_entity_role_active_idx');
        DB::statement('DROP INDEX IF EXISTS egr_lookup_idx');
        DB::statement('DROP INDEX IF EXISTS egr_entity_external_unique_idx');
        DB::statement('DROP INDEX IF EXISTS egr_entity_geo_ref_idx');

        Schema::dropIfExists('entity_geo_refs');

        DB::statement('DROP TYPE IF EXISTS geo_ref_retrieval_method CASCADE');
        DB::statement('DROP TYPE IF EXISTS geo_ref_match_role CASCADE');
        DB::statement('DROP TYPE IF EXISTS geo_ref_external_type CASCADE');
        DB::statement('DROP TYPE IF EXISTS geo_ref_provider CASCADE');
    }
};
