<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use Tests\TestCase;

class RebuildEntityTimelineMemoryRegressionTest extends TestCase
{
    use RefreshDatabase;

    #[RunInSeparateProcess]
    public function test_rebuild_command_handles_large_territory_geometries_with_worker_memory_limit(): void
    {
        $entity = Entity::factory()->create(['name' => 'Roman Empire']);

        DB::statement(
            <<<'SQL'
            WITH polygon AS (
                SELECT ST_SetSRID(
                    ST_MakePolygon(
                        ST_MakeLine(points.point ORDER BY points.seq)
                    ),
                    4326
                ) AS territory_geom
                FROM (
                    SELECT seq, ST_MakePoint(
                        cos((2 * pi() * seq) / 136423::double precision),
                        sin((2 * pi() * seq) / 136423::double precision)
                    ) AS point
                    FROM generate_series(0, 136423) AS seq
                    UNION ALL
                    SELECT 136424, ST_MakePoint(1, 0)
                ) AS points
            )
            INSERT INTO geometry_periods (
                geometry_period_id,
                entity_id,
                period_type,
                start_year,
                end_year,
                territory_geom,
                provenance_mode,
                created_by,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                ?,
                'territory',
                117 + periods.seq,
                395 + periods.seq,
                polygon.territory_geom,
                'manual',
                'test',
                NOW(),
                NOW()
            FROM polygon
            CROSS JOIN generate_series(1, 19) AS periods(seq)
            SQL,
            [$entity->entity_id],
        );

        ini_set('memory_limit', '128M');

        $this->artisan('timeline:rebuild', ['entity_id' => $entity->entity_id])->assertExitCode(0);

        $this->assertDatabaseHas('entity_timeline_entries', [
            'entity_id' => $entity->entity_id,
            'entry_kind' => 'territory_period',
            'source_table' => 'geometry_periods',
        ]);
    }
}