<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * The entity hierarchy params (parent_id / include_children) referenced a
 * non-existent `childrenOf` scope and a non-existent `children` relation /
 * `parent_id` column, so passing them used to 500. They are now removed and
 * silently ignored.
 */
class EntityHierarchyParamsRemovedTest extends TestCase
{
    use RefreshDatabase;

    public function test_list_endpoint_ignores_parent_id_instead_of_500(): void
    {
        Entity::factory()->verified()->create();

        $response = $this->getJson(route('api.v1.entities.index', [
            'parent_id' => Str::uuid()->toString(),
        ]));

        $response->assertOk();
    }

    public function test_show_endpoint_ignores_include_children_and_omits_key(): void
    {
        $entity = Entity::factory()->verified()->create();

        $response = $this->getJson(route('api.v1.entities.show', [
            'entity' => $entity->entity_id,
            'include_children' => 1,
        ]));

        $response->assertOk();
        $response->assertJsonMissingPath('data.children');
    }
}
