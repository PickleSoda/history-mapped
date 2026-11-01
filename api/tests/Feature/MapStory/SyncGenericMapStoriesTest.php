<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\MapStory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/** `map-stories:sync` for schema 3: references, chronicle entries, period, extent and the ambient layer. */
class SyncGenericMapStoriesTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = MapStoryFixture::directory();
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    /** @return array<string, Entity> the entities the v3 fixture names */
    private function atlas(): array
    {
        $horde = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Golden Horde', 'wikidata_id' => 'Q79965']);
        DB::statement(
            "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, territory_geom, provenance_mode, created_by, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'territory', 1240, 1400, ST_SetSRID(ST_GeomFromText('POLYGON((40 45, 50.0001 45, 50 55, 40 55, 40 45))'), 4326), 'manual', 'test', NOW(), NOW())",
            [$horde->entity_id],
        );

        return [
            'plague' => Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['name' => 'Plague of Testland', 'wikidata_id' => 'Q42005']),
            'feodosia' => Entity::factory()->ofType(EntityType::City)->create(['name' => 'Feodosia', 'wikidata_id' => 'Q130231']),
            'jani' => Entity::factory()->ofType(EntityType::Person)->withTemporalRange('1300', '1357')->create(['name' => 'Jani Beg', 'wikidata_id' => 'Q313451']),
            'namesake' => Entity::factory()->ofType(EntityType::Person)->withTemporalRange('1700', '1760')->create(['name' => 'A later namesake', 'wikidata_id' => 'Q99']),
            'horde' => $horde,
        ];
    }

    private function chronicle(): Chronicle
    {
        $chronicle = Chronicle::factory()->create(['slug' => 'testland-trade', 'title' => 'Testland trade', 'status' => 'published']);
        foreach ([0, 1, 2] as $order) {
            ChronicleEntry::factory()->create(['chronicle_id' => $chronicle->chronicle_id, 'sequence_order' => $order]);
        }

        return $chronicle;
    }

    private function sync(): int
    {
        return $this->artisan('map-stories:sync', ['--path' => $this->dir])->run();
    }

    public function test_syncs_a_schema_3_story_with_its_references_period_and_extent(): void
    {
        $atlas = $this->atlas();
        MapStoryFixture::write($this->dir, MapStoryFixture::v3Document());

        $this->assertSame(0, $this->sync());

        $story = MapStory::query()->sole();
        $this->assertSame($atlas['plague']->entity_id, $story->entity_id);
        $this->assertNull($story->chronicle_id);
        $this->assertSame([1346, 1350, true, 'epidemic'], [$story->period_start, $story->period_end, $story->ambient, $story->kind]);

        $doc = $story->document;
        $this->assertSame($atlas['feodosia']->entity_id, $doc->features[0]->entity->entity_id);
        $this->assertSame($atlas['jani']->entity_id, $doc->steps[0]->entities[0]->entity_id);
        $this->assertNull($doc->steps[0]->entities[1]->entity_id, 'a step entity of another era (the namesake guard) resolves to null');
        $this->assertSame($atlas['horde']->entity_id, $doc->steps[0]->features->horde->area_from_entity->entity_id);
        $this->assertSame('Jani Beg', $doc->steps[0]->entities[0]->name, 'the authored ref is kept');

        // The extent covers the features, the arrows and the entity's area (to 50.0001°E, 55°N).
        $box = DB::selectOne('SELECT ST_XMin(bbox) AS w, ST_YMin(bbox) AS s, ST_XMax(bbox) AS e, ST_YMax(bbox) AS n, ST_SRID(bbox) AS srid FROM map_stories');
        $this->assertEqualsWithDelta([15.0, 37.0, 50.0, 55.0, 4326], [$box->w, $box->s, $box->e, $box->n, $box->srid], 0.01);
    }

    public function test_precomputes_the_ambient_layer_of_each_step(): void
    {
        $atlas = $this->atlas();
        MapStoryFixture::write($this->dir, MapStoryFixture::v3Document());
        $this->sync();

        $steps = MapStory::query()->sole()->ambient_steps;
        $this->assertSame([0, 1, 2], array_column($steps, 'index'));
        $this->assertSame([1346, 1347, 1350], array_column($steps, 'start'));
        $this->assertSame('The galleys sail', $steps[1]['title']);

        $byId = fn (int $i) => collect($steps[$i]['features']['features'])->keyBy('properties.id');

        // Step 1: the route is not open yet and a town is not an ambient kind.
        $first = $byId(0);
        $this->assertSame(['caffa', 'plague', 'horde'], $first->keys()->all());
        $this->assertSame(['type' => 'Point', 'coordinates' => [35.38, 45.03]], $first['caffa']['geometry']);
        $expected = [
            'id' => 'caffa', 'kind' => 'outbreak', 'region_kind' => null, 'route_kind' => null, 'label' => 'Caffa',
            'color' => '#991b1b', 'value_n' => 1000, 'value_label' => '1,000 dead', 'intensity' => null, 'state' => 'infected',
        ];
        $properties = $first['caffa']['properties'];
        ksort($expected);
        ksort($properties); // jsonb keeps its own key order
        $this->assertSame($expected, $properties);
        $this->assertSame('Polygon', $first['plague']['geometry']['type']);
        $this->assertEquals([[34, 44], [37, 44], [37, 46], [34, 46], [34, 44]], $first['plague']['geometry']['coordinates'][0], 'rings are closed');
        $this->assertSame('#7f1d1d', $first['plague']['properties']['color']);
        // The Horde's area is its atlas territory in 1346, simplified and rounded.
        $this->assertSame('Polygon', $first['horde']['geometry']['type']);
        $this->assertContainsEquals([50, 45], $first['horde']['geometry']['coordinates'][0]);
        $this->assertSame('#1d4ed8', $first['horde']['properties']['color']);

        // Step 2: the route opens (simplified), the region becomes two rings, the state carries forward.
        $second = $byId(1);
        $this->assertSame('LineString', $second['sea-lane']['geometry']['type']);
        $this->assertLessThan(5, count($second['sea-lane']['geometry']['coordinates']));
        $this->assertSame(['#b45309', 'trade', 12], [$second['sea-lane']['properties']['color'], $second['sea-lane']['properties']['route_kind'], $second['sea-lane']['properties']['value_n']]);
        $this->assertSame('MultiPolygon', $second['plague']['geometry']['type']);
        $this->assertCount(2, $second['plague']['geometry']['coordinates']);
        $this->assertSame(0.8, $second['plague']['properties']['intensity']);
        $this->assertSame('infected', $second['caffa']['properties']['state']);

        // Step 3: each key carries forward on its own.
        $third = $byId(2);
        $this->assertSame(['disrupted', 12], [$third['sea-lane']['properties']['state'], $third['sea-lane']['properties']['value_n']]);
        $this->assertSame(['recovered', 1000], [$third['caffa']['properties']['state'], $third['caffa']['properties']['value_n']]);
    }

    public function test_a_story_that_is_not_ambient_stores_no_layer(): void
    {
        $this->atlas();
        $doc = MapStoryFixture::v3Document();
        $doc['ambient'] = false;
        MapStoryFixture::write($this->dir, $doc);
        $this->sync();

        $story = MapStory::query()->sole();
        $this->assertFalse($story->ambient);
        $this->assertNull($story->ambient_steps);
    }

    public function test_a_battle_has_a_one_year_period_and_a_tight_extent(): void
    {
        Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
        $doc = MapStoryFixture::v2Document();
        // Off-stage units and `continues` tails stay out of the extent.
        $doc['steps'][0]['positions']['blue-horse']['at'] = [20.0, 45.0];
        MapStoryFixture::write($this->dir, $doc);

        $this->assertSame(0, $this->sync());

        $story = MapStory::query()->sole();
        $this->assertSame([-216, -216, false], [$story->period_start, $story->period_end, $story->ambient]);
        $box = DB::selectOne('SELECT ST_XMin(bbox) AS w, ST_YMin(bbox) AS s, ST_XMax(bbox) AS e, ST_YMax(bbox) AS n FROM map_stories');
        $this->assertEqualsWithDelta([16.10, 41.29, 16.15, 41.31], [$box->w, $box->s, $box->e, $box->n], 0.001);
    }

    public function test_syncs_a_chronicle_layer_keyed_by_entry(): void
    {
        $this->atlas();
        $chronicle = $this->chronicle();
        MapStoryFixture::write($this->dir, MapStoryFixture::chronicleLayer());

        $this->assertSame(0, $this->sync());

        $story = MapStory::query()->sole();
        $this->assertNull($story->entity_id);
        $this->assertSame($chronicle->chronicle_id, $story->chronicle_id);
        $doc = $story->document;
        $this->assertSame($chronicle->chronicle_id, $doc->chronicle->chronicle_id);
        $entries = ChronicleEntry::query()->where('chronicle_id', $chronicle->chronicle_id)->pluck('entry_id', 'sequence_order');
        $this->assertSame([$entries[0], $entries[2]], [$doc->steps[0]->entry_id, $doc->steps[1]->entry_id]);
    }

    public function test_fails_an_unknown_chronicle_or_entry(): void
    {
        $this->atlas();
        MapStoryFixture::write($this->dir, MapStoryFixture::chronicleLayer());

        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain("chronicle 'testland-trade' is not in the atlas")
            ->assertFailed();

        $this->chronicle();
        MapStoryFixture::write($this->dir, MapStoryFixture::chronicleLayer(entries: [0, 7]));
        $this->artisan('map-stories:sync', ['--path' => $this->dir])
            ->expectsOutputToContain("step 's2'.entry: chronicle 'testland-trade' has no entry 7 (its entries run 0–2)")
            ->assertFailed();
        $this->assertSame(0, MapStory::query()->count());
    }

    public function test_a_given_entity_id_is_kept_when_the_entity_exists(): void
    {
        $atlas = $this->atlas();
        $doc = MapStoryFixture::v3Document();
        $doc['steps'][0]['entities'] = [
            ['name' => 'Feodosia', 'entity_id' => $atlas['feodosia']->entity_id],
            ['name' => 'Gone', 'entity_id' => '00000000-0000-4000-8000-000000000000'],
        ];
        MapStoryFixture::write($this->dir, $doc);
        $this->sync();

        $entities = MapStory::query()->sole()->document->steps[0]->entities;
        $this->assertSame([$atlas['feodosia']->entity_id, null], [$entities[0]->entity_id, $entities[1]->entity_id]);
    }
}
