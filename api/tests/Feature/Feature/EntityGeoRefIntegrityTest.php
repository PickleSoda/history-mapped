<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Models\Entity;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class EntityGeoRefIntegrityTest extends TestCase
{
    use RefreshDatabase;

    public function test_entity_primary_geo_ref_must_belong_to_same_entity(): void
    {
        $entityA = Entity::factory()->create();
        $entityB = Entity::factory()->create();
        $geoRefId = Str::uuid()->toString();

        DB::table('entity_geo_refs')->insert([
            'geo_ref_id' => $geoRefId,
            'entity_id' => $entityB->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '300',
            'match_role' => 'primary',
            'retrieval_method' => 'rest',
            'match_score' => 0.95,
            'is_active' => true,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->expectException(QueryException::class);

        DB::table('entities')
            ->where('entity_id', $entityA->entity_id)
            ->update(['primary_geo_ref_id' => $geoRefId]);
    }
}
