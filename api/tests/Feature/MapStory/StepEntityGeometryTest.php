<?php

declare(strict_types=1);

namespace Tests\Feature\MapStory;

use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryFile;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

/** Sync gives each shown step entity its atlas geometry at the step's year. */
class StepEntityGeometryTest extends TestCase
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

    private function period(Entity $entity, int $start, ?int $end, string $column, string $wkt): void
    {
        DB::statement(
            "INSERT INTO geometry_periods (geometry_period_id, entity_id, period_type, start_year, end_year, {$column}, provenance_mode, created_by, created_at, updated_at)
             VALUES (gen_random_uuid(), ?, 'territory', ?, ?, ST_SetSRID(ST_GeomFromText(?), 4326), 'manual', 'test', NOW(), NOW())",
            [$entity->entity_id, $start, $end, $wkt],
        );
    }

    /** @param  list<array<string, mixed>>  $entities */
    private static function step(string $id, ?int $year, array $entities): array
    {
        return array_filter([
            'id' => $id, 'title' => $id, 'narrative' => 'Something happens.',
            'date' => $year === null ? null : ['year' => $year],
            'entities' => $entities,
        ], fn (mixed $v) => $v !== null);
    }

    /**
     * A realm with a territory 1300–1347, a dated point 1348–1400 and an
     * undated location; a realm the atlas has no geometry for.
     *
     * @return array{0: Entity, 1: Entity}
     */
    private function atlas(): array
    {
        Entity::factory()->ofType(EntityType::EpidemicDisease)->create(['name' => 'Plague of Testland', 'wikidata_id' => 'Q42005']);
        $realm = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Realm', 'wikidata_id' => 'Q1001']);
        $this->period($realm, 1300, 1347, 'territory_geom', 'POLYGON((40 45, 50 45, 50 55, 40 55, 40 45))');
        $this->period($realm, 1348, 1400, 'geom', 'POINT(44.5 50.25)');
        DB::table('entity_locations')->insert([
            'entity_id' => $realm->entity_id, 'location_name' => 'Capital', 'is_primary' => true,
            'geom' => DB::raw("ST_SetSRID(ST_GeomFromText('POINT(1.5 2.5)'), 4326)"),
        ]);
        $bare = Entity::factory()->ofType(EntityType::PoliticalEntity)->create(['name' => 'Bare realm', 'wikidata_id' => 'Q1002']);

        return [$realm, $bare];
    }

    public function test_a_shown_entity_gets_its_area_or_falls_back_by_the_steps_year(): void
    {
        [$realm] = $this->atlas();
        $show = ['name' => 'Realm', 'wikidata' => 'Q1001', 'show' => true];
        $doc = MapStoryFixture::v3Document();
        $doc['ambient'] = false; // so a step may be undated
        $doc['steps'] = [
            self::step('s1', 1346, [$show, ['name' => 'Realm', 'wikidata' => 'Q1001'], ['name' => 'Bare realm', 'wikidata' => 'Q1002', 'show' => true], ['name' => 'Unknown', 'wikidata' => 'Q1003', 'show' => true]]),
            self::step('s2', 1350, [$show]),
            self::step('s3', 1500, [$show]),
            self::step('s4', null, [$show]),
        ];
        MapStoryFixture::write($this->dir, $doc);

        $this->assertSame(0, $this->artisan('map-stories:sync', ['--path' => $this->dir])->run());
        $steps = MapStory::query()->sole()->document->steps;

        // 1346: the territory period covering the year.
        $first = $steps[0]->entities[0];
        $this->assertSame($realm->entity_id, $first->entity_id);
        $this->assertSame('Polygon', $first->geometry->type);
        $this->assertContainsEquals([50, 55], $first->geometry->coordinates[0]);
        // Not shown, or not in the atlas: no geometry. Shown but the atlas has none: null.
        $this->assertObjectNotHasProperty('geometry', $steps[0]->entities[1]);
        $this->assertObjectNotHasProperty('geometry', $steps[0]->entities[3]);
        $this->assertTrue(property_exists($steps[0]->entities[2], 'geometry'));
        $this->assertNull($steps[0]->entities[2]->geometry);

        // 1350: past the territory, the dated point covering the year.
        $this->assertEquals(['type' => 'Point', 'coordinates' => [44.5, 50.25]], (array) $steps[1]->entities[0]->geometry);
        // 1500: outside every period, the undated location.
        $this->assertEquals(['type' => 'Point', 'coordinates' => [1.5, 2.5]], (array) $steps[2]->entities[0]->geometry);
        // An undated step is at the story's year (1346).
        $this->assertSame('Polygon', $steps[3]->entities[0]->geometry->type);

        // It is resolved, not authored: the authored copy (export, the editor, revisions) has none.
        $authored = MapStoryFile::authored(MapStory::query()->sole()->document);
        $this->assertObjectNotHasProperty('geometry', $authored->steps[0]->entities[0]);
        $this->assertObjectNotHasProperty('geometry', MapStory::query()->sole()->revisions()->first()->document->steps[0]->entities[0]);

        // And the API serves it.
        $this->getJson('/api/v1/map-stories/plague-of-testland')
            ->assertOk()
            ->assertJsonPath('data.document.steps.0.entities.0.geometry.type', 'Polygon')
            ->assertJsonPath('data.document.steps.1.entities.0.geometry.coordinates', [44.5, 50.25]);
    }

    /** @param  array<string, mixed>  $attributes */
    private function ohmRef(Entity $entity, string $ref, ?int $start, ?int $end, array $attributes = []): void
    {
        [$type, $id] = explode('/', $ref);
        EntityGeoRef::factory()->forEntity($entity)->create([
            'external_type' => $type, 'external_id' => $id, 'temporal_start_year' => $start, 'temporal_end_year' => $end,
            'external_tags' => ['type' => 'boundary'], 'match_score' => 0.9, ...$attributes,
        ]);
    }

    public function test_a_shown_entity_lists_the_ohm_boundaries_covering_the_steps_year(): void
    {
        [$realm, $bare] = $this->atlas();
        // Never outlined: a node, a chronology, an inactive or a rejected ref.
        $this->ohmRef($realm, 'node/15', 1300, 1400, ['match_role' => 'primary']);
        $this->ohmRef($realm, 'relation/10', 1300, 1400, ['external_tags' => ['type' => 'chronology']]);
        $this->ohmRef($realm, 'relation/16', 1300, 1400, ['is_active' => false]);
        $this->ohmRef($realm, 'relation/17', 1300, 1400, ['match_role' => 'rejected']);
        // The dated boundaries.
        $this->ohmRef($realm, 'relation/12', 1300, 1347);
        $this->ohmRef($realm, 'relation/13', 1348, null);
        // A primary boundary wins over a candidate covering the same year.
        $this->ohmRef($bare, 'relation/21', 1300, 1400, ['match_score' => 1.0]);
        $this->ohmRef($bare, 'relation/20', null, 1400, ['match_role' => 'primary', 'match_score' => 0.5]);

        $show = ['name' => 'Realm', 'wikidata' => 'Q1001', 'show' => true];
        $doc = MapStoryFixture::v3Document();
        $doc['ambient'] = false;
        $doc['steps'] = [
            self::step('s1', 1346, [$show, ['name' => 'Bare realm', 'wikidata' => 'Q1002', 'show' => true], ['name' => 'Realm', 'wikidata' => 'Q1001']]),
            self::step('s2', 1350, [$show]),
            self::step('s3', 1200, [$show]),
            self::step('s4', null, [$show]),
        ];
        MapStoryFixture::write($this->dir, $doc);
        $this->assertSame(0, $this->artisan('map-stories:sync', ['--path' => $this->dir])->run());
        $steps = MapStory::query()->sole()->document->steps;

        $this->assertSame(['relation/12'], $steps[0]->entities[0]->ohm);
        $this->assertSame(['relation/20'], $steps[0]->entities[1]->ohm);
        $this->assertObjectNotHasProperty('ohm', $steps[0]->entities[2], 'not shown');
        $this->assertSame(['relation/13'], $steps[1]->entities[0]->ohm, 'an open end covers');
        $this->assertObjectNotHasProperty('ohm', $steps[2]->entities[0], 'no boundary covers 1200');
        $this->assertSame(['relation/12'], $steps[3]->entities[0]->ohm, "an undated step is at the story's year");
        $this->assertObjectNotHasProperty('ohm', MapStoryFile::authored(MapStory::query()->sole()->document)->steps[0]->entities[0]);
    }
}
