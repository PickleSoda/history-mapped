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
        Schema::create('entity_temporal_ranges', function (Blueprint $table) {
            $table->uuid('temporal_range_id')->primary()->default(DB::raw('gen_random_uuid()'));
            $table->uuid('entity_id');
            $table->text('range_type')->default('primary'); // primary | secondary | disputed
            $table->integer('start_year')->nullable();
            $table->integer('end_year')->nullable();
            $table->text('start_date')->nullable(); // ISO-8601 string
            $table->text('end_date')->nullable();
            $table->text('duration_type')->nullable();
            $table->text('date_method')->nullable();
            $table->text('date_confidence')->nullable();
            $table->boolean('is_primary')->default(false);
            $table->text('notes')->nullable();
            $table->timestamps();

            $table->foreign('entity_id')
                ->references('entity_id')
                ->on('entities')
                ->cascadeOnDelete();
        });

        DB::statement("ALTER TABLE entity_temporal_ranges ADD CONSTRAINT etr_valid_year_range
            CHECK (start_year IS NULL OR end_year IS NULL OR start_year <= end_year)");

        DB::unprepared(<<<'SQL'
CREATE OR REPLACE FUNCTION entity_temporal_ranges_sync_years()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.start_year := CASE
        WHEN NEW.start_date IS NULL OR NEW.start_date !~ '^-?\d+'
            THEN NEW.start_year
        ELSE CAST(SUBSTRING(NEW.start_date FROM '^-?\d+') AS integer)
    END;

    NEW.end_year := CASE
        WHEN NEW.end_date IS NULL OR NEW.end_date !~ '^-?\d+'
            THEN NEW.end_year
        ELSE CAST(SUBSTRING(NEW.end_date FROM '^-?\d+') AS integer)
    END;

    RETURN NEW;
END;
$$;
SQL);

        DB::statement('CREATE TRIGGER entity_temporal_ranges_sync_years_trigger
            BEFORE INSERT OR UPDATE ON entity_temporal_ranges
            FOR EACH ROW
            EXECUTE FUNCTION entity_temporal_ranges_sync_years()');

        DB::statement('CREATE INDEX etr_entity_idx ON entity_temporal_ranges (entity_id)');
        DB::statement('CREATE INDEX etr_year_range_idx ON entity_temporal_ranges (start_year, end_year)');
        DB::statement("CREATE INDEX etr_active_range_gist_idx
            ON entity_temporal_ranges USING GIST (int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year + 1 END, '[)'))");
    }

    public function down(): void
    {
        DB::statement('DROP TRIGGER IF EXISTS entity_temporal_ranges_sync_years_trigger ON entity_temporal_ranges');
        DB::statement('DROP FUNCTION IF EXISTS entity_temporal_ranges_sync_years()');
        Schema::dropIfExists('entity_temporal_ranges');
    }
};
