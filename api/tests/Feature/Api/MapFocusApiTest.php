<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Models\Entity;
use App\Models\EntityRelationship;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class MapFocusApiTest extends TestCase
{
    use RefreshDatabase;

    private function placed(string $name, float $lng, float $lat, array $state = []): Entity
    {
        $entity = Entity::factory()->verified()->atLocation($name.' place')->create(['name' => $name] + $state);
        DB::update(
            'UPDATE entity_locations SET geom = ST_SetSRID(ST_Point(?, ?), 4326) WHERE entity_id = ? AND is_primary',
            [$lng, $lat, $entity->entity_id],
        );

        return $entity;
    }

    private function rel(Entity $a, Entity $b): void
    {
        EntityRelationship::create([
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $a->entity_id,
            'target_entity_id' => $b->entity_id,
            'relationship_type' => 'allied_with',
            'confidence' => 'high',
        ]);
    }

    /** @return array<string, int> name => depth */
    private function names(string $query): array
    {
        $features = $this->getJson('/api/v1/entities/map/focus?'.$query)->assertOk()->json('features');

        return array_column(array_column($features, 'properties'), 'depth', 'name');
    }

    public function test_an_entitys_relations_one_and_two_hops_out_are_points_whatever_the_year_or_place(): void
    {
        $root = $this->placed('Root', 2, 48);
        $near = $this->placed('Near', 12, 41);
        $far = $this->placed('Far', -70, -30);
        $unplaced = Entity::factory()->verified()->create(['name' => 'Nowhere']);
        $this->placed('Stranger', 5, 5);
        $this->rel($root, $near);
        $this->rel($near, $far);
        $this->rel($root, $unplaced);

        $this->assertSame(['Root' => 0, 'Near' => 1, 'Far' => 2], $this->names("related_to={$root->entity_id}"));
        $this->assertSame(['Root' => 0, 'Near' => 1], $this->names("related_to={$root->entity_id}&depth=1"));

        $feature = $this->getJson("/api/v1/entities/map/focus?related_to={$near->entity_id}&depth=1")->json('features.0');
        $this->assertSame($near->entity_id, $feature['id']);
        $this->assertSame(['type' => 'Point', 'coordinates' => [12, 41]], $feature['geometry']);
    }

    public function test_a_search_returns_the_most_prominent_placed_matches(): void
    {
        $this->placed('Zedvark Minor', 1, 1, ['impact_score' => 20]);
        $this->placed('Fort Zedvark', 2, 2, ['impact_score' => 90]);
        Entity::factory()->verified()->create(['name' => 'Zedvark the Unplaced', 'impact_score' => 99]);
        $this->placed('Elsewhere', 3, 3);

        $this->assertSame(['Fort Zedvark', 'Zedvark Minor'], array_keys($this->names('search=zedvark')));
        // A typo still finds them when nothing matches as written.
        $this->assertSame(['Fort Zedvark', 'Zedvark Minor'], array_keys($this->names('search=zedvarc')));
        $this->assertSame(['Fort Zedvark'], array_keys($this->names('search=zedvark&limit=1')));
    }

    public function test_it_needs_exactly_one_of_an_entity_or_a_search(): void
    {
        $id = (string) Str::uuid();
        $this->getJson('/api/v1/entities/map/focus')->assertStatus(422);
        $this->getJson("/api/v1/entities/map/focus?related_to={$id}&search=rome")->assertStatus(422);
        $this->getJson("/api/v1/entities/map/focus?related_to={$id}")->assertNotFound();
    }
}
