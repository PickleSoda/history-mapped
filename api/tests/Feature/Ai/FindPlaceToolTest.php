<?php

namespace Tests\Feature\Ai;

use App\Ai\Tools\FindPlace;
use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityAlias;
use App\Models\EntityLocation;
use App\Models\EntityTemporalRange;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Laravel\Ai\Tools\Request;
use LogicException;
use Tests\TestCase;

class FindPlaceToolTest extends TestCase
{
    use RefreshDatabase;

    private function place(string $name, EntityType $type, float $lon, float $lat, ?string $start = null, ?string $end = null): Entity
    {
        $entity = Entity::factory()->create([
            'name' => $name,
            'entity_type' => $type->value,
            'entity_group' => $type->group()->value,
        ]);
        EntityLocation::create([
            'entity_id' => $entity->entity_id,
            'is_primary' => true,
            'geom' => ['type' => 'Point', 'coordinates' => [$lon, $lat]],
        ]);
        if ($start !== null || $end !== null) {
            EntityTemporalRange::create([
                'entity_id' => $entity->entity_id,
                'is_primary' => true,
                'range_type' => 'primary',
                'start_date' => $start,
                'end_date' => $end,
            ]);
        }

        return $entity;
    }

    /** @return array<string, mixed> */
    private function find(array $args): array
    {
        return json_decode(app(FindPlace::class)->handle(new Request($args)), true);
    }

    public function test_finds_our_entity_by_name_without_asking_ohm(): void
    {
        Http::fake();
        $ostia = $this->place('Ostia', EntityType::City, 12.2917, 41.7556);

        $data = $this->find(['name' => 'ostia']);

        $first = $data['candidates'][0];
        $this->assertSame('entity', $first['source']);
        $this->assertSame($ostia->entity_id, $first['entity_id']);
        $this->assertEqualsWithDelta(12.2917, $first['lon'], 1e-4);
        $this->assertEqualsWithDelta(41.7556, $first['lat'], 1e-4);
        $this->assertSame('exact', $first['precision']);
        $this->assertTrue($first['exact_name']);
        $this->assertArrayHasKey('next', $data);
        Http::assertNothingSent();
    }

    public function test_matches_an_alternative_name(): void
    {
        Http::fake();
        $byzantium = $this->place('Byzantium', EntityType::City, 28.976, 41.012);
        EntityAlias::create(['entity_id' => $byzantium->entity_id, 'name' => 'Constantinople', 'is_primary' => false]);

        $data = $this->find(['name' => 'Constantinople']);

        $this->assertSame($byzantium->entity_id, $data['candidates'][0]['entity_id']);
        $this->assertTrue($data['candidates'][0]['exact_name']);
    }

    public function test_flags_a_shared_fallback_point_as_approximate(): void
    {
        Http::fake(['*' => Http::response([])]);
        $severans = $this->place('Severan dynasty', EntityType::Dynasty, 12.48, 41.89);
        foreach (range(1, 5) as $i) {
            $this->place("Roman thing {$i}", EntityType::Person, 12.48, 41.89);
        }
        $rome = $this->place('Rome', EntityType::City, 12.48, 41.89);

        $dynasty = $this->find(['name' => 'Severan dynasty'])['candidates'][0];
        $this->assertSame($severans->entity_id, $dynasty['entity_id']);
        $this->assertSame('approximate', $dynasty['precision']);
        $this->assertStringContainsString('shared by 6 other entities', $dynasty['note']);

        // The city the others were pinned to is still a good anchor.
        $city = $this->find(['name' => 'Rome'])['candidates'][0];
        $this->assertSame($rome->entity_id, $city['entity_id']);
        $this->assertSame('exact', $city['precision']);
    }

    public function test_prefers_the_place_that_existed_in_the_year(): void
    {
        Http::fake();
        $modern = $this->place('Carthage', EntityType::City, 10.33, 36.86, '1900', null);
        $ancient = $this->place('Carthage', EntityType::City, 10.32, 36.85, '-814', '-146');

        $this->assertSame($ancient->entity_id, $this->find(['name' => 'Carthage', 'year' => -200])['candidates'][0]['entity_id']);
        $this->assertSame($modern->entity_id, $this->find(['name' => 'Carthage', 'year' => 1950])['candidates'][0]['entity_id']);
    }

    public function test_filters_by_entity_type(): void
    {
        Http::fake();
        $this->place('Alexandria', EntityType::City, 29.92, 31.2);
        $battle = $this->place('Alexandria', EntityType::EventBattle, 29.9, 31.1);

        $data = $this->find(['name' => 'Alexandria', 'entity_type' => 'event_battle']);

        $this->assertCount(1, $data['candidates']);
        $this->assertSame($battle->entity_id, $data['candidates'][0]['entity_id']);
    }

    public function test_falls_back_to_the_ohm_gazetteer(): void
    {
        Http::fake([
            'nominatim.openhistoricalmap.org/*' => Http::response([[
                'osm_type' => 'relation',
                'osm_id' => 42,
                'display_name' => 'Ephesus, Selçuk, Türkiye',
                'class' => 'historic',
                'type' => 'archaeological_site',
                'lat' => '37.9411',
                'lon' => '27.3419',
                'extratags' => ['name' => 'Ephesus', 'start_date' => '-1000'],
            ]]),
        ]);

        $data = $this->find(['name' => 'Ephesus']);

        $first = $data['candidates'][0];
        $this->assertSame('ohm', $first['source']);
        $this->assertSame('Ephesus', $first['name']);
        $this->assertSame('relation/42', $first['osm']);
        $this->assertSame(27.3419, $first['lon']);
        $this->assertSame(37.9411, $first['lat']);
        $this->assertSame('-1000', $first['start_date']);
    }

    public function test_reports_when_the_gazetteer_is_down(): void
    {
        Http::fake(['*' => Http::response('', 503)]);

        $data = $this->find(['name' => 'Atlantis']);

        $this->assertSame([], $data['candidates']);
        $this->assertArrayHasKey('message', $data);
    }

    public function test_requires_a_name(): void
    {
        $this->assertArrayHasKey('error', $this->find(['name' => '  ']));
    }

    public function test_is_read_only(): void
    {
        $this->expectException(LogicException::class);
        app(FindPlace::class)->buildParts([]);
    }
}
