<?php

declare(strict_types=1);

namespace Tests\Feature\Api;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Models\Entity;
use App\Pagination\CappedLengthAwarePaginator;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

/**
 * GET /api/v1/entities: the bbox filter on the primary point and the capped
 * total (`meta.total_capped`).
 */
class EntityListApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_bbox_keeps_only_entities_whose_primary_point_is_inside(): void
    {
        $inside = $this->placed('Inside Zed', 10.5, 40.5);
        $this->placed('Outside Zed', 100.0, -20.0);
        Entity::factory()->verified()->create(['name' => 'Unplaced Zed']);

        $response = $this->getJson('/api/v1/entities?bbox_min_lng=0&bbox_min_lat=30&bbox_max_lng=20&bbox_max_lat=50');

        $response->assertOk()
            ->assertJsonPath('meta.total', 1)
            ->assertJsonPath('meta.total_capped', false)
            ->assertJsonPath('data.0.id', $inside->entity_id);
    }

    public function test_the_total_stops_at_the_cap(): void
    {
        foreach (['A', 'B', 'C'] as $letter) {
            $this->placed("Capped {$letter} Zed", 10.5, 40.5);
        }
        $filters = EntityFilterData::fromArray(['per_page' => 2]);

        $capped = app(ListEntitiesAction::class)($filters, totalCap: 2);
        $this->assertInstanceOf(CappedLengthAwarePaginator::class, $capped);
        $this->assertSame(2, $capped->total());
        $this->assertTrue($capped->totalCapped);
        $this->assertTrue($capped->toArray()['total_capped']);
        $this->assertCount(2, $capped->items());

        $roomy = app(ListEntitiesAction::class)($filters, totalCap: 3);
        $this->assertSame(3, $roomy->total());
        $this->assertFalse($roomy->totalCapped);

        // Without a cap (the admin list) the count is exact and plain.
        $exact = app(ListEntitiesAction::class)($filters);
        $this->assertNotInstanceOf(CappedLengthAwarePaginator::class, $exact);
        $this->assertSame(3, $exact->total());
    }

    public function test_a_one_or_two_letter_search_matches_name_prefixes_by_impact(): void
    {
        Entity::factory()->verified()->create(['name' => 'Rostov Zed', 'impact_score' => 40]);
        Entity::factory()->verified()->create(['name' => 'Rome Zed', 'impact_score' => 90]);
        Entity::factory()->verified()->create(['name' => 'Cairo Zed', 'impact_score' => 99]);
        Entity::factory()->verified()->create(['name' => '100% Zed', 'impact_score' => 50]);

        $names = collect($this->getJson('/api/v1/entities?search=ro&sort=relevance')->assertOk()->json('data'))->pluck('name')->all();
        $this->assertSame(['Rome Zed', 'Rostov Zed'], $names);

        // LIKE wildcards in the term are literal.
        $this->assertSame([], $this->getJson('/api/v1/entities?search=%25')->assertOk()->json('data'));

        // From three letters the substring match is back.
        $names = collect($this->getJson('/api/v1/entities?search=air')->assertOk()->json('data'))->pluck('name')->all();
        $this->assertSame(['Cairo Zed'], $names);
    }

    private function placed(string $name, float $lng, float $lat): Entity
    {
        $entity = Entity::factory()->verified()->atLocation($name.' place')->create(['name' => $name]);
        DB::update(
            'UPDATE entity_locations SET geom = ST_SetSRID(ST_Point(?, ?), 4326) WHERE entity_id = ? AND is_primary',
            [$lng, $lat, $entity->entity_id],
        );

        return $entity;
    }
}
