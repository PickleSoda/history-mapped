<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class GeometrySnapshotApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_legacy_index_endpoint_is_removed(): void
    {
        $entity = Entity::factory()->create();

        $this->getJson("/api/v1/entities/{$entity->entity_id}/geometry-snapshots")
            ->assertNotFound();
    }

    public function test_legacy_at_year_endpoint_is_removed(): void
    {
        $entity = Entity::factory()->create();

        $this->getJson("/api/v1/entities/{$entity->entity_id}/geometry-snapshots/at-year/-30")
            ->assertNotFound();
    }
}
