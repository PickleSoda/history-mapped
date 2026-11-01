<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\MapStory;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/** Schema 3 over the API: the ambient layer, chronicle map layers, and stories without an entity. */
class MapStoryAmbientApiTest extends TestCase
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

    /** @param  array<string, mixed>  $doc */
    private function sync(array $doc): MapStory
    {
        MapStoryFixture::write($this->dir, $doc);
        $this->artisan('map-stories:sync', ['--path' => $this->dir])->assertSuccessful();

        return MapStory::query()->where('slug', $doc['slug'])->sole();
    }

    private function plague(): MapStory
    {
        Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['name' => 'Plague of Testland', 'wikidata_id' => 'Q42005']);

        return $this->sync(MapStoryFixture::v3Document());
    }

    private function chronicle(string $slug = 'testland-trade'): Chronicle
    {
        $chronicle = Chronicle::factory()->create(['slug' => $slug, 'title' => 'Testland trade', 'status' => 'published']);
        foreach ([0, 1, 2] as $order) {
            ChronicleEntry::factory()->create(['chronicle_id' => $chronicle->chronicle_id, 'sequence_order' => $order]);
        }

        return $chronicle;
    }

    /** @param  array<string, mixed>  $query */
    private function ambient(array $query): array
    {
        return $this->getJson(route('api.v1.map-stories.ambient', $query))->assertOk()->json('data');
    }

    public function test_returns_each_ambient_story_at_its_state_for_the_year(): void
    {
        $this->plague();

        $data = $this->ambient(['year' => 1348, 'bbox' => '-15,25,50,65']);
        $this->assertCount(1, $data);
        $this->assertSame(
            ['plague-of-testland', 'epidemic', 'The plague of Testland', 1, 'The galleys sail'],
            [$data[0]['slug'], $data[0]['kind'], $data[0]['title'], $data[0]['step_index'], $data[0]['step_title']],
        );
        $this->assertSame('FeatureCollection', $data[0]['features']['type']);
        $features = collect($data[0]['features']['features'])->keyBy('properties.id');
        $this->assertSame(['caffa', 'sea-lane', 'plague'], $features->keys()->all());
        $this->assertSame(['route', 'trade', null, '#b45309', 12], [
            $features['sea-lane']['properties']['kind'], $features['sea-lane']['properties']['route_kind'],
            $features['sea-lane']['properties']['region_kind'], $features['sea-lane']['properties']['color'],
            $features['sea-lane']['properties']['value_n'],
        ]);
        $this->assertSame('MultiPolygon', $features['plague']['geometry']['type']);

        // The last step that starts in or before the year; nothing outside the period.
        $this->assertSame(0, $this->ambient(['year' => 1346])[0]['step_index']);
        $this->assertSame(2, $this->ambient(['year' => 1350])[0]['step_index']);
        $this->assertSame([], $this->ambient(['year' => 1345]));
        $this->assertSame([], $this->ambient(['year' => 1351]));
    }

    public function test_filters_by_the_box_and_wraps_the_antimeridian(): void
    {
        $this->plague();

        $this->assertSame([], $this->ambient(['year' => 1348, 'bbox' => '100,0,120,10']));
        $this->assertCount(1, $this->ambient(['year' => 1348, 'bbox' => '36,45,38,47']), 'a box inside the extent');
        $this->assertCount(1, $this->ambient(['year' => 1348, 'bbox' => '170,30,40,60']), 'west > east crosses the antimeridian');
        $this->assertCount(1, $this->ambient(['year' => 1348, 'bbox' => '330,30,400,60']), 'wrapped longitudes');
        $this->assertCount(1, $this->ambient(['year' => 1348, 'bbox' => '-200,-80,200,80']), 'the whole world');
        $this->assertCount(1, $this->ambient(['year' => 1348]), 'no box');
    }

    public function test_leaves_out_stories_that_are_not_ambient(): void
    {
        Entity::factory()->ofType(EntityType::EventBattle)->create(['name' => 'Battle of Testfield', 'wikidata_id' => 'Q179591']);
        $this->sync(MapStoryFixture::v2Document());
        $this->plague()->update(['ambient' => false]);

        $this->assertSame([], $this->ambient(['year' => -216]));
        $this->assertSame([], $this->ambient(['year' => 1348]));
    }

    public function test_is_etag_cached(): void
    {
        $this->plague();
        $url = route('api.v1.map-stories.ambient', ['year' => 1348, 'bbox' => '-15,25,50,65']);

        $first = $this->get($url)->assertOk()->assertHeader('Cache-Control', 'max-age=60, public');
        $etag = $first->headers->get('ETag');
        $this->assertNotEmpty($etag);

        $this->get($url, ['If-None-Match' => $etag])->assertStatus(304);
        $this->get($url, ['If-None-Match' => 'W/'.$etag])->assertStatus(304);
        $this->assertNotSame($etag, $this->get(route('api.v1.map-stories.ambient', ['year' => 1349]))->headers->get('ETag'));

        DB::table('map_stories')->update(['updated_at' => now()->addMinute()]);
        $this->get($url, ['If-None-Match' => $etag])->assertOk();
    }

    public function test_validates_its_parameters(): void
    {
        $this->getJson(route('api.v1.map-stories.ambient'))->assertUnprocessable()->assertJsonValidationErrors('year');
        $this->getJson(route('api.v1.map-stories.ambient', ['year' => 'soon']))->assertUnprocessable()->assertJsonValidationErrors('year');
        $this->getJson(route('api.v1.map-stories.ambient', ['year' => 1348, 'bbox' => '1,2,3']))->assertUnprocessable()->assertJsonValidationErrors('bbox');
        $this->getJson(route('api.v1.map-stories.ambient', ['year' => 1348, 'bbox' => '0,60,10,50']))->assertUnprocessable()->assertJsonValidationErrors('bbox');
    }

    public function test_show_carries_the_chronicle_period_and_ambient_flag(): void
    {
        $chronicle = $this->chronicle();
        $layer = $this->sync(MapStoryFixture::chronicleLayer());
        $plague = $this->plague();

        $this->getJson('/api/v1/map-stories/testland-trade-map')
            ->assertOk()
            ->assertJsonPath('data.id', $layer->story_id)
            ->assertJsonPath('data.entity_id', null)
            ->assertJsonPath('data.chronicle_id', $chronicle->chronicle_id)
            ->assertJsonPath('data.period', ['start' => 1346, 'end' => 1348])
            ->assertJsonPath('data.ambient', false)
            ->assertJsonPath('data.document.chronicle.chronicle_id', $chronicle->chronicle_id)
            ->assertJsonMissingPath('data.ambient_steps');

        $this->getJson('/api/v1/map-stories/plague-of-testland')
            ->assertOk()
            ->assertJsonPath('data.entity_id', $plague->entity_id)
            ->assertJsonPath('data.chronicle_id', null)
            ->assertJsonPath('data.period', ['start' => 1346, 'end' => 1350])
            ->assertJsonPath('data.ambient', true);

        $this->getJson('/api/v1/map-stories/ambient-but-not-a-route')->assertNotFound();
    }

    public function test_a_chronicle_carries_its_map_layer(): void
    {
        $chronicle = $this->chronicle();
        $other = $this->chronicle('testland-war');
        $layer = $this->sync(MapStoryFixture::chronicleLayer());
        $summary = [
            'id' => $layer->story_id, 'slug' => 'testland-trade-map', 'kind' => 'trade_route',
            'title' => 'The plague of Testland', 'year' => 1346, 'step_count' => 2,
        ];

        $this->getJson("/api/v1/chronicles/{$chronicle->slug}")->assertOk()->assertJsonPath('data.map_story', $summary);
        $this->getJson("/api/v1/chronicles/{$other->slug}")->assertOk()->assertJsonPath('data.map_story', null);

        $list = collect($this->getJson('/api/v1/chronicles')->assertOk()->json('data'))->keyBy('slug');
        $this->assertSame($summary, $list['testland-trade']['map_story']);
        $this->assertNull($list['testland-war']['map_story']);
    }

    public function test_entity_detail_and_map_are_unaffected_by_stories_without_an_entity(): void
    {
        $this->chronicle();
        $this->sync(MapStoryFixture::chronicleLayer());
        $city = Entity::factory()->verified()->ofType(EntityType::City)->create(['impact_score' => 90]);
        DB::statement(
            "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, geom, provenance_mode, created_by, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'point', 1000, 1500, ST_SetSRID(ST_MakePoint(10.5, 40.5), 4326), 'manual', 'test', NOW(), NOW())",
            [$city->entity_id],
        );

        $this->getJson("/api/v1/entities/{$city->entity_id}")->assertOk()->assertJsonPath('data.map_stories', []);
        $query = ['bbox_min_lng' => 0, 'bbox_min_lat' => 30, 'bbox_max_lng' => 30, 'bbox_max_lat' => 50, 'year' => 1348];
        $features = $this->getJson(route('api.v1.entities.map', $query))->assertOk()->json('features');
        $this->assertFalse(collect($features)->firstWhere('properties.id', $city->entity_id)['properties']['has_map_story']);
        $this->getJson(route('api.v1.entities.map.year', ['year' => 1348]))->assertOk();
    }

    public function test_deleting_a_chronicle_drops_its_own_layer_and_detaches_a_shared_one(): void
    {
        $chronicle = $this->chronicle();
        $layer = $this->sync(MapStoryFixture::chronicleLayer());
        $entity = Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['wikidata_id' => 'Q42005']);
        $shared = MapStoryFixture::chronicleLayer('testland-trade-plague');
        $shared['entity'] = ['name' => 'Plague of Testland', 'wikidata' => 'Q42005'];
        $both = $this->sync($shared);
        $this->assertSame([$entity->entity_id, $chronicle->chronicle_id], [$both->entity_id, $both->chronicle_id]);

        $chronicle->delete();

        $this->assertNull(MapStory::query()->find($layer->story_id));
        $both->refresh();
        $this->assertSame([$entity->entity_id, null], [$both->entity_id, $both->chronicle_id]);
    }

    public function test_a_story_needs_an_entity_or_a_chronicle(): void
    {
        $this->expectException(QueryException::class);

        MapStory::query()->create([
            'slug' => 'orphan', 'kind' => 'event', 'title' => 'Orphan', 'year' => 1, 'step_count' => 0, 'document' => (object) [],
        ]);
    }
}
