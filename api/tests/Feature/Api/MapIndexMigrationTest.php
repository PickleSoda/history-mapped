<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class MapIndexMigrationTest extends TestCase
{
    use RefreshDatabase;

    public function test_map_optimization_indexes_exist(): void
    {
        $indexes = [
            'entity_aliases_primary_unique',
            'entity_locations_primary_unique',
            'entity_temporal_ranges_primary_unique',
            'gp_map_geom_gist',
            'entities_display_priority_idx',
        ];

        foreach ($indexes as $indexName) {
            $row = DB::selectOne('SELECT 1 AS ok FROM pg_indexes WHERE indexname = ?', [$indexName]);
            $this->assertNotNull($row, "Expected index {$indexName} to exist");
        }
    }
}
