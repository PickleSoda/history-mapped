<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class EntityModelV2SchemaTest extends TestCase
{
    use RefreshDatabase;

    public function test_geometry_periods_table_exists_with_required_columns(): void
    {
        $this->assertTrue(Schema::hasTable('geometry_periods'));

        $this->assertTrue(Schema::hasColumns('geometry_periods', [
            'geometry_period_id',
            'entity_id',
            'period_type',
            'start_year',
            'end_year',
            'geom',
            'territory_geom',
            'provenance_mode',
            'relationship_id',
            'source_event_id',
        ]));
    }

    public function test_geometry_periods_has_core_integrity_constraints(): void
    {
        $this->assertTrue($this->constraintExists('geometry_periods', 'gp_valid_year_range'));
        $this->assertTrue($this->constraintExists('geometry_periods', 'gp_has_geometry'));
        $this->assertTrue($this->constraintExists('geometry_periods', 'gp_provenance_mode'));
        $this->assertTrue($this->constraintExists('geometry_periods', 'gp_derived_requires_source'));
        $this->assertTrue($this->constraintExists('geometry_periods', 'gp_presence_requires_relationship'));
    }

    public function test_entity_timeline_entries_table_exists_with_required_columns(): void
    {
        $this->assertTrue(Schema::hasTable('entity_timeline_entries'));

        $this->assertTrue(Schema::hasColumns('entity_timeline_entries', [
            'timeline_entry_id',
            'entity_id',
            'entry_kind',
            'start_year',
            'end_year',
            'title',
            'source_table',
            'source_id',
            'derived_at',
        ]));

        $this->assertTrue($this->constraintExists('entity_timeline_entries', 'ete_valid_year_range'));
    }

    public function test_phase_a_drops_legacy_entity_indexes_before_hard_drop(): void
    {
        $this->assertFalse($this->indexExists('entities_geom_gist_idx'));
        $this->assertFalse($this->indexExists('entities_territory_geom_gist_idx'));
        $this->assertFalse($this->indexExists('entities_temporal_range_idx'));
        $this->assertFalse($this->indexExists('entities_temporal_start_index'));
        $this->assertFalse($this->indexExists('entities_temporal_end_index'));
        $this->assertFalse($this->indexExists('entities_tags_gin_idx'));
    }

    private function constraintExists(string $table, string $constraint): bool
    {
        /** @var object{exists: bool}|null $row */
        $row = DB::selectOne(
            'SELECT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = ? AND c.conname = ?
            ) AS exists',
            [$table, $constraint],
        );

        return (bool) ($row?->exists ?? false);
    }

    private function indexExists(string $indexName): bool
    {
        /** @var object{exists: bool}|null $row */
        $row = DB::selectOne(
            'SELECT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE indexname = ?
            ) AS exists',
            [$indexName],
        );

        return (bool) ($row?->exists ?? false);
    }

    public function test_legacy_entity_columns_are_removed(): void
    {
        $legacyColumns = [
            'geom',
            'territory_geom',
            'location_name',
            'temporal_start',
            'temporal_end',
            'temporal_start_year',
            'temporal_end_year',
            'alternative_names',
            'tags',
        ];

        foreach ($legacyColumns as $column) {
            $this->assertFalse(
                Schema::hasColumn('entities', $column),
                "Column entities.{$column} should be absent after legacy hard-drop",
            );
        }
    }

    public function test_geometry_snapshots_table_is_gone(): void
    {
        $this->assertFalse(
            Schema::hasTable('geometry_snapshots'),
            'Table geometry_snapshots should not exist after legacy hard-drop',
        );
    }
}
