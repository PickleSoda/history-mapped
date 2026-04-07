<?php

declare(strict_types=1);

namespace Tests\Feature\Feature;

use App\Actions\EntityGeoRef\PruneOrphanGeometryPeriodGeoRefAction;
use App\Models\Entity;
use App\Models\EntityGeoRef;
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

    public function test_pruning_orphan_geometry_period_geo_refs_keeps_shared_entity_level_references(): void
    {
        $entityA = Entity::factory()->create();
        $entityB = Entity::factory()->create();

        $sharedA = EntityGeoRef::query()->create([
            'geo_ref_id' => Str::uuid()->toString(),
            'entity_id' => $entityA->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => 'shared-1',
            'match_role' => 'primary',
            'retrieval_method' => 'rest',
            'match_score' => 0.99,
            'is_active' => true,
            'source_meta' => ['origin' => 'entity'],
        ]);

        $sharedB = EntityGeoRef::query()->create([
            'geo_ref_id' => Str::uuid()->toString(),
            'entity_id' => $entityB->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => 'shared-1',
            'match_role' => 'candidate',
            'retrieval_method' => 'rest',
            'match_score' => 0.75,
            'is_active' => true,
            'source_meta' => ['origin' => 'entity'],
        ]);

        $orphanPeriodRef = EntityGeoRef::query()->create([
            'geo_ref_id' => Str::uuid()->toString(),
            'entity_id' => $entityA->entity_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => 'orphan-period',
            'match_role' => 'candidate',
            'retrieval_method' => 'rest',
            'match_score' => 0.40,
            'is_active' => false,
            'source_meta' => ['origin' => 'geometry_period'],
        ]);

        DB::table('entities')
            ->where('entity_id', $entityA->entity_id)
            ->update(['primary_geo_ref_id' => $sharedA->geo_ref_id]);

        app(PruneOrphanGeometryPeriodGeoRefAction::class)->__invoke($entityA);

        $this->assertDatabaseMissing('entity_geo_refs', [
            'geo_ref_id' => $orphanPeriodRef->geo_ref_id,
        ]);

        $this->assertDatabaseHas('entity_geo_refs', [
            'geo_ref_id' => $sharedA->geo_ref_id,
        ]);

        $this->assertDatabaseHas('entity_geo_refs', [
            'geo_ref_id' => $sharedB->geo_ref_id,
        ]);
    }
}
