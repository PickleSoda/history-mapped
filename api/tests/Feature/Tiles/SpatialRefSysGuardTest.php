<?php

declare(strict_types=1);

namespace Tests\Feature\Tiles;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * The guard migration restores the EPSG:4326 / EPSG:3857 rows that
 * `tiles.atlas_entities` needs (production had lost them, 2026-11-03).
 */
class SpatialRefSysGuardTest extends TestCase
{
    use RefreshDatabase;

    public function test_guard_restores_the_two_tile_srids_and_is_idempotent(): void
    {
        DB::delete('DELETE FROM spatial_ref_sys WHERE srid IN (4326, 3857)');
        $this->assertSame(0, $this->tileSridCount());

        $migration = require database_path('migrations/2026_11_03_000001_ensure_tile_srids.php');
        $migration->up();

        $rows = DB::select('SELECT srid, auth_name, auth_srid, proj4text FROM spatial_ref_sys WHERE srid IN (4326, 3857) ORDER BY srid');
        $this->assertSame([3857, 4326], array_map(fn ($r) => (int) $r->srid, $rows));
        $this->assertSame([3857, 4326], array_map(fn ($r) => (int) $r->auth_srid, $rows));
        $this->assertSame(['EPSG', 'EPSG'], array_map(fn ($r) => $r->auth_name, $rows));
        $this->assertStringContainsString('+proj=merc', $rows[0]->proj4text);
        $this->assertStringContainsString('+proj=longlat', $rows[1]->proj4text);

        $migration->up();
        $this->assertSame(2, $this->tileSridCount());

        // The tile function transforms through both SRIDs again (empty ocean tile).
        $row = DB::selectOne("SELECT mvt = ''::bytea AS is_empty FROM tiles.atlas_entities(14, 100, 8000)");
        $this->assertTrue((bool) $row->is_empty);
    }

    private function tileSridCount(): int
    {
        return (int) DB::selectOne('SELECT count(*) AS n FROM spatial_ref_sys WHERE srid IN (4326, 3857)')->n;
    }
}
