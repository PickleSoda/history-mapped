<?php

declare(strict_types=1);

namespace Tests\Feature\Console;

use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefProvider;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ExportOhmRefIdsTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_writes_sorted_distinct_ohm_ids_with_numeric_external_ids(): void
    {
        $this->ohmRef(GeoRefExternalType::Relation, '1880');
        $this->ohmRef(GeoRefExternalType::Relation, '1880'); // same feature on a second entity
        $this->ohmRef(GeoRefExternalType::Node, '42');
        $this->ohmRef(GeoRefExternalType::Way, 'not-a-number');
        EntityGeoRef::factory()->create([
            'provider' => GeoRefProvider::Wikidata->value,
            'external_type' => GeoRefExternalType::Qid->value,
            'external_id' => 'Q2277',
        ]);

        $path = sys_get_temp_dir().'/export_ohm_ref_ids_'.uniqid().'/ids.txt';
        $this->beforeApplicationDestroyed(function () use ($path): void {
            @unlink($path);
            @rmdir(dirname($path));
        });

        $this->artisan('pipeline:export-ohm-ref-ids', ['path' => $path])->assertExitCode(0);

        $this->assertSame("node/42\nrelation/1880\n", file_get_contents($path));
    }

    private function ohmRef(GeoRefExternalType $type, string $externalId): void
    {
        EntityGeoRef::factory()->forEntity(Entity::factory()->create())->create([
            'provider' => GeoRefProvider::Ohm->value,
            'external_type' => $type->value,
            'external_id' => $externalId,
        ]);
    }
}
