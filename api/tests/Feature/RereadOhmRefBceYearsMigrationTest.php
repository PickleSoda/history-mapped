<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Enums\GeoRefProvider;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * 2026_11_14_000001: OHM refs' BCE years, stored as written, move to our
 * numbering (OHM's 0000 is 1 BCE, its -0026 is 27 BCE).
 */
class RereadOhmRefBceYearsMigrationTest extends TestCase
{
    use RefreshDatabase;

    private function migration(): Migration
    {
        return require database_path('migrations/2026_11_14_000001_reread_ohm_ref_bce_years.php');
    }

    private function ref(string $provider, ?string $start, ?int $startYear, ?string $end = null, ?int $endYear = null): EntityGeoRef
    {
        return EntityGeoRef::factory()->forEntity(Entity::factory()->create())->create([
            'provider' => $provider,
            'external_type' => 'relation',
            'external_id' => (string) random_int(1, 999_999_999),
            'temporal_start' => $start,
            'temporal_start_year' => $startYear,
            'temporal_end' => $end,
            'temporal_end_year' => $endYear,
        ]);
    }

    /** @return array{0: ?int, 1: ?int} */
    private function years(EntityGeoRef $ref): array
    {
        $ref->refresh();

        return [$ref->temporal_start_year, $ref->temporal_end_year];
    }

    public function test_it_moves_bce_years_read_as_written_and_nothing_else(): void
    {
        $ohm = GeoRefProvider::Ohm->value;
        $roman = $this->ref($ohm, '-0026-01-16', -26, '0476-09-04', 476);
        $oneBce = $this->ref($ohm, '0000', 0, '0014', 14);
        $bothBce = $this->ref($ohm, '-0305', -305, '-0029', -29);
        $edited = $this->ref($ohm, '-0100', -150);
        $otherProvider = $this->ref(GeoRefProvider::Pleiades->value, '-0026', -26);

        $this->migration()->up();

        $this->assertSame([-27, 476], $this->years($roman));
        $this->assertSame([-1, 14], $this->years($oneBce));
        $this->assertSame([-306, -30], $this->years($bothBce));
        $this->assertSame([-150, null], $this->years($edited));
        $this->assertSame([-26, null], $this->years($otherProvider));

        // A second run changes nothing; down() restores the as-written years.
        $this->migration()->up();
        $this->assertSame([-27, 476], $this->years($roman));

        $this->migration()->down();
        $this->assertSame([-26, 476], $this->years($roman));
        $this->assertSame([0, 14], $this->years($oneBce));
        $this->assertSame([-305, -29], $this->years($bothBce));
        $this->assertSame([-150, null], $this->years($edited));
    }
}
