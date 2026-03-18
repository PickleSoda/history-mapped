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
     * Creates the 10 reference tables for the Historical Atlas platform.
     * These are manually curated lookup tables used for entity resolution,
     * display formatting, and analytical grouping. They do not flow through
     * the 8-stage pipeline.
     *
     * Table creation order respects FK dependencies:
     *   1. ref_geographic_regions      (self-referencing)
     *   2. ref_historical_periods      (FK → regions, self-referencing)
     *   3. ref_historiographical_schools
     *   4. ref_calendar_systems
     *   5. ref_era_date_lookup         (FK → periods)
     *   6. ref_writing_systems         (self-referencing)
     *   7. ref_religious_traditions    (self-referencing)
     *   8. ref_measurement_units
     *   9. ref_language_families       (self-referencing)
     *  10. ref_source_type_definitions
     */
    public function up(): void
    {
        // ──────────────────────────────────────────────
        // 1. ref_geographic_regions
        // ──────────────────────────────────────────────

        Schema::create('ref_geographic_regions', function (Blueprint $table) {
            $table->increments('region_id');
            $table->text('name');
            $table->text('alternative_names')->nullable();   // placeholder → text[]

            // Hierarchy
            $table->unsignedInteger('parent_region_id')->nullable();
            $table->integer('depth_level')->default(0);

            // Spatial (PostGIS)
            $table->geometry('bounding_box')->nullable();
            $table->geometry('center_point')->nullable();

            // Context
            $table->text('modern_countries')->nullable();     // placeholder → text[]
            $table->text('historical_names')->nullable();     // placeholder → text[]

            // Pipeline usage
            $table->text('typical_periods')->nullable();      // placeholder → text[]
            $table->integer('batch_priority')->default(0);

            $table->integer('sort_order')->nullable();
        });

        // Self-referencing FK added after table exists
        Schema::table('ref_geographic_regions', function (Blueprint $table) {
            $table->foreign('parent_region_id')
                ->references('region_id')
                ->on('ref_geographic_regions');
        });

        // Replace placeholders with PG array types
        DB::statement('ALTER TABLE ref_geographic_regions ALTER COLUMN alternative_names TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_geographic_regions ALTER COLUMN modern_countries TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_geographic_regions ALTER COLUMN historical_names TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_geographic_regions ALTER COLUMN typical_periods TYPE text[] USING NULL');

        // Indexes
        DB::statement('CREATE INDEX ref_geographic_regions_bbox_gist_idx ON ref_geographic_regions USING GIST (bounding_box)');
        DB::statement('CREATE INDEX ref_geographic_regions_parent_idx ON ref_geographic_regions (parent_region_id)');

        // ──────────────────────────────────────────────
        // 2. ref_historical_periods
        // ──────────────────────────────────────────────

        Schema::create('ref_historical_periods', function (Blueprint $table) {
            $table->increments('period_id');
            $table->text('name');
            $table->text('alternative_names')->nullable();    // placeholder → text[]

            // Temporal bounds (EDTF)
            $table->text('start_date');
            $table->text('end_date');
            $table->text('date_precision')->nullable();

            // Scope
            $table->text('geographic_scope');
            $table->unsignedInteger('region_id')->nullable();

            // Classification
            $table->text('periodization_scheme');
            $table->unsignedInteger('parent_period_id')->nullable();
            $table->integer('depth_level')->default(0);

            // Metadata
            $table->text('defining_characteristics')->nullable();
            $table->text('conventional_start_event')->nullable();
            $table->text('conventional_end_event')->nullable();
            $table->text('historiographical_notes')->nullable();
            $table->text('value_judgments')->nullable();

            // Display
            $table->text('color_hex')->nullable();
            $table->integer('sort_order')->nullable();

            // FK to regions (non-self-referencing — safe here)
            $table->foreign('region_id')
                ->references('region_id')
                ->on('ref_geographic_regions');
        });

        // Self-referencing FK added after table exists
        Schema::table('ref_historical_periods', function (Blueprint $table) {
            $table->foreign('parent_period_id')
                ->references('period_id')
                ->on('ref_historical_periods');
        });

        // Replace placeholder with PG array type
        DB::statement('ALTER TABLE ref_historical_periods ALTER COLUMN alternative_names TYPE text[] USING NULL');

        // Indexes
        DB::statement('CREATE INDEX ref_historical_periods_dates_idx ON ref_historical_periods (start_date, end_date)');
        DB::statement('CREATE INDEX ref_historical_periods_scheme_idx ON ref_historical_periods (periodization_scheme)');
        DB::statement('CREATE INDEX ref_historical_periods_region_idx ON ref_historical_periods (region_id)');

        // ──────────────────────────────────────────────
        // 3. ref_historiographical_schools
        // ──────────────────────────────────────────────

        Schema::create('ref_historiographical_schools', function (Blueprint $table) {
            $table->increments('school_id');
            $table->text('name');
            $table->text('alternative_names')->nullable();    // placeholder → text[]

            // Temporal scope
            $table->text('active_from')->nullable();
            $table->text('active_to')->nullable();

            // Description
            $table->text('interpretive_framework');
            $table->text('methodological_approach')->nullable();
            $table->text('evidence_emphasized')->nullable();
            $table->text('evidence_downplayed')->nullable();
            $table->text('political_commitments')->nullable();

            // Influence
            $table->text('geographic_center')->nullable();
            $table->text('dominant_regions')->nullable();      // placeholder → text[]
            $table->text('dominant_periods')->nullable();      // placeholder → text[]

            // Key figures
            $table->text('key_historians')->nullable();        // placeholder → text[]
            $table->text('foundational_works')->nullable();    // placeholder → text[]

            // Relationships
            $table->text('influenced_by')->nullable();         // placeholder → integer[]
            $table->text('opposed_to')->nullable();            // placeholder → integer[]

            $table->integer('sort_order')->nullable();
        });

        // Replace placeholders with PG array types
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN alternative_names TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN dominant_regions TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN dominant_periods TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN key_historians TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN foundational_works TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN influenced_by TYPE integer[] USING NULL');
        DB::statement('ALTER TABLE ref_historiographical_schools ALTER COLUMN opposed_to TYPE integer[] USING NULL');

        // ──────────────────────────────────────────────
        // 4. ref_calendar_systems
        // ──────────────────────────────────────────────

        Schema::create('ref_calendar_systems', function (Blueprint $table) {
            $table->increments('calendar_id');
            $table->text('name');
            $table->text('code')->unique();

            // Type
            $table->text('calendar_type');

            // Epoch
            $table->text('epoch_description')->nullable();
            $table->text('epoch_gregorian')->nullable();

            // Conversion
            $table->text('conversion_formula')->nullable();
            $table->text('conversion_notes')->nullable();

            // Usage
            $table->text('used_by_regions')->nullable();       // placeholder → text[]
            $table->text('used_by_periods')->nullable();       // placeholder → text[]
            $table->boolean('still_in_use')->default(false);

            // Display
            $table->jsonb('month_names')->nullable();
            $table->text('special_cycles')->nullable();
        });

        // Replace placeholders with PG array types
        DB::statement('ALTER TABLE ref_calendar_systems ALTER COLUMN used_by_regions TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_calendar_systems ALTER COLUMN used_by_periods TYPE text[] USING NULL');

        // ──────────────────────────────────────────────
        // 5. ref_era_date_lookup
        // ──────────────────────────────────────────────

        Schema::create('ref_era_date_lookup', function (Blueprint $table) {
            $table->increments('lookup_id');
            $table->text('search_term');
            $table->text('search_variants')->nullable();       // placeholder → text[]

            // Resolution
            $table->text('resolved_start');
            $table->text('resolved_end');

            // Scope
            $table->text('geographic_scope')->nullable();

            // Metadata
            $table->text('confidence')->default('medium-low');
            $table->text('notes')->nullable();
            $table->unsignedInteger('period_id')->nullable();

            // FK to periods
            $table->foreign('period_id')
                ->references('period_id')
                ->on('ref_historical_periods');
        });

        // Replace placeholder with PG array type
        DB::statement('ALTER TABLE ref_era_date_lookup ALTER COLUMN search_variants TYPE text[] USING NULL');

        // Indexes
        DB::statement('CREATE INDEX ref_era_date_lookup_term_idx ON ref_era_date_lookup (search_term)');
        DB::statement('CREATE INDEX ref_era_date_lookup_variants_gin_idx ON ref_era_date_lookup USING GIN (search_variants)');

        // ──────────────────────────────────────────────
        // 6. ref_writing_systems
        // ──────────────────────────────────────────────

        Schema::create('ref_writing_systems', function (Blueprint $table) {
            $table->increments('system_id');
            $table->text('name');
            $table->text('code')->unique()->nullable();

            // Classification
            $table->text('system_type');
            $table->text('direction')->nullable();

            // History
            $table->text('origin_date')->nullable();
            $table->text('origin_location')->nullable();
            $table->unsignedInteger('derived_from')->nullable();

            // Usage
            $table->text('languages_using')->nullable();       // placeholder → text[]
            $table->boolean('still_in_use')->default(false);

            // Technical
            $table->text('unicode_block')->nullable();
            $table->text('ocr_support_level')->nullable();
        });

        // Self-referencing FK added after table exists
        Schema::table('ref_writing_systems', function (Blueprint $table) {
            $table->foreign('derived_from')
                ->references('system_id')
                ->on('ref_writing_systems');
        });

        // Replace placeholder with PG array type
        DB::statement('ALTER TABLE ref_writing_systems ALTER COLUMN languages_using TYPE text[] USING NULL');

        // ──────────────────────────────────────────────
        // 7. ref_religious_traditions
        // ──────────────────────────────────────────────

        Schema::create('ref_religious_traditions', function (Blueprint $table) {
            $table->increments('tradition_id');
            $table->text('name');
            $table->unsignedInteger('parent_tradition_id')->nullable();
            $table->integer('depth_level')->default(0);

            $table->text('origin_date')->nullable();
            $table->text('origin_region')->nullable();
            $table->text('founder')->nullable();

            $table->text('tradition_type')->nullable();

            // Display
            $table->integer('sort_order')->nullable();
            $table->text('color_hex')->nullable();
        });

        // Self-referencing FK added after table exists
        Schema::table('ref_religious_traditions', function (Blueprint $table) {
            $table->foreign('parent_tradition_id')
                ->references('tradition_id')
                ->on('ref_religious_traditions');
        });

        // ──────────────────────────────────────────────
        // 8. ref_measurement_units
        // ──────────────────────────────────────────────

        Schema::create('ref_measurement_units', function (Blueprint $table) {
            $table->increments('unit_id');
            $table->text('name');
            $table->text('symbol')->nullable();

            // Classification
            $table->text('measurement_type');

            // Conversion
            $table->decimal('si_equivalent', 65, 30)->nullable(); // placeholder, replaced below
            $table->text('si_unit')->nullable();
            $table->text('conversion_notes')->nullable();

            // Historical context
            $table->text('used_by_region')->nullable();
            $table->text('used_by_period')->nullable();
            $table->boolean('approximate')->default(true);

            $table->integer('sort_order')->nullable();
        });

        // Replace decimal placeholder with PG numeric (unconstrained)
        DB::statement('ALTER TABLE ref_measurement_units ALTER COLUMN si_equivalent TYPE numeric USING si_equivalent::numeric');

        // ──────────────────────────────────────────────
        // 9. ref_language_families
        // ──────────────────────────────────────────────

        Schema::create('ref_language_families', function (Blueprint $table) {
            $table->increments('family_id');
            $table->text('name');
            $table->unsignedInteger('parent_family_id')->nullable();
            $table->integer('depth_level')->default(0);

            $table->text('proto_language')->nullable();
            $table->text('estimated_origin')->nullable();
            $table->text('estimated_homeland')->nullable();

            $table->integer('living_languages')->nullable();
            $table->text('status')->nullable();

            $table->integer('sort_order')->nullable();
        });

        // Self-referencing FK added after table exists
        Schema::table('ref_language_families', function (Blueprint $table) {
            $table->foreign('parent_family_id')
                ->references('family_id')
                ->on('ref_language_families');
        });

        // ──────────────────────────────────────────────
        // 10. ref_source_type_definitions
        // ──────────────────────────────────────────────

        Schema::create('ref_source_type_definitions', function (Blueprint $table) {
            $table->increments('definition_id');

            $table->text('enum_name');
            $table->text('enum_value');

            $table->text('description');
            $table->text('examples')->nullable();              // placeholder → text[]

            // Pipeline behavior
            $table->text('default_confidence')->nullable();
            $table->boolean('requires_corroboration')->default(false);
            $table->decimal('weight_in_scoring', 65, 30)->default(1.0); // placeholder, replaced below

            // Review guidance
            $table->text('reviewer_notes')->nullable();
        });

        // Replace placeholders with correct PG types
        DB::statement('ALTER TABLE ref_source_type_definitions ALTER COLUMN examples TYPE text[] USING NULL');
        DB::statement('ALTER TABLE ref_source_type_definitions ALTER COLUMN weight_in_scoring TYPE numeric USING weight_in_scoring::numeric');
        DB::statement('ALTER TABLE ref_source_type_definitions ALTER COLUMN weight_in_scoring SET DEFAULT 1.0');
    }

    /**
     * Reverse the migrations.
     *
     * Drop tables in reverse FK-dependency order.
     */
    public function down(): void
    {
        Schema::dropIfExists('ref_source_type_definitions');
        Schema::dropIfExists('ref_language_families');
        Schema::dropIfExists('ref_measurement_units');
        Schema::dropIfExists('ref_religious_traditions');
        Schema::dropIfExists('ref_writing_systems');
        Schema::dropIfExists('ref_era_date_lookup');
        Schema::dropIfExists('ref_calendar_systems');
        Schema::dropIfExists('ref_historiographical_schools');
        Schema::dropIfExists('ref_historical_periods');
        Schema::dropIfExists('ref_geographic_regions');
    }
};
