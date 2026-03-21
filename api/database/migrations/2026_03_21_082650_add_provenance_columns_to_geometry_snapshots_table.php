<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Add provenance columns to geometry_snapshots:
     *   - description: explains *why* the entity was at that geometry
     *   - relationship_id: FK to relationships (CASCADE delete) for presence snapshots
     *   - source_event_id: FK to entities (SET NULL) for territory snapshots from events
     *
     * At most one of relationship_id / source_event_id may be non-null (CHECK constraint).
     */
    public function up(): void
    {
        Schema::table('geometry_snapshots', function (Blueprint $table) {
            $table->text('description')->nullable()->after('notes');

            $table->uuid('relationship_id')->nullable()->after('description');
            $table->foreign('relationship_id', 'gs_relationship_id_fk')
                ->references('relationship_id')
                ->on('relationships')
                ->cascadeOnDelete();

            $table->uuid('source_event_id')->nullable()->after('relationship_id');
            $table->foreign('source_event_id', 'gs_source_event_id_fk')
                ->references('entity_id')
                ->on('entities')
                ->nullOnDelete();
        });

        // PostgreSQL CHECK: at most one provenance FK set
        \Illuminate\Support\Facades\DB::statement(
            'ALTER TABLE geometry_snapshots ADD CONSTRAINT gs_single_provenance
             CHECK (relationship_id IS NULL OR source_event_id IS NULL)'
        );
    }

    public function down(): void
    {
        \Illuminate\Support\Facades\DB::statement(
            'ALTER TABLE geometry_snapshots DROP CONSTRAINT IF EXISTS gs_single_provenance'
        );

        Schema::table('geometry_snapshots', function (Blueprint $table) {
            $table->dropForeign('gs_source_event_id_fk');
            $table->dropForeign('gs_relationship_id_fk');
            $table->dropColumn(['description', 'relationship_id', 'source_event_id']);
        });
    }
};
