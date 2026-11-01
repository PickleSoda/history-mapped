<?php

declare(strict_types=1);

namespace Tests\Feature\Tiles;

use App\Enums\EntityGroup;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * The app as tile server (`TILES_DRIVER=app`): routes/tiles.php answers
 * Martin's URLs with Martin's semantics (docs/schemas/atlas-tiles.md).
 * Seeded entities sit at ST_Point(10.5, 40.5), inside tile z0 0/0.
 */
class TileEndpointTest extends TestCase
{
    use RefreshDatabase;

    public function test_tile_is_protobuf_with_etag_cache_control_and_open_cors(): void
    {
        $this->seedFeature('Tileland Zed');

        $response = $this->get('/tiles/atlas_entities/0/0/0');

        $response->assertOk()
            ->assertHeader('Content-Type', 'application/x-protobuf')
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertHeader('Cache-Control', 'max-age=300, public');
        $body = (string) $response->getContent();
        $this->assertStringContainsString('Tileland Zed', $body);
        $this->assertSame('"'.md5($body).'"', $response->headers->get('ETag'));
    }

    public function test_matching_if_none_match_is_304_without_a_body(): void
    {
        $this->seedFeature('Etag Zed');
        $etag = (string) $this->get('/tiles/atlas_entities/0/0/0')->headers->get('ETag');

        $response = $this->get('/tiles/atlas_entities/0/0/0', ['If-None-Match' => $etag]);

        $response->assertStatus(304);
        $this->assertSame('', $response->getContent());
        $this->assertSame($etag, $response->headers->get('ETag'));

        $this->get('/tiles/atlas_entities/0/0/0', ['If-None-Match' => '"stale"'])->assertOk();
    }

    public function test_empty_and_out_of_range_tiles_are_204(): void
    {
        $this->seedFeature('Elsewhere Zed');

        $this->get('/tiles/atlas_entities/14/0/0')->assertNoContent()->assertHeader('Access-Control-Allow-Origin', '*');
        $this->get('/tiles/atlas_entities/0/5/5')->assertNoContent();
        $this->get('/tiles/atlas_entities/31/0/0')->assertNoContent();
    }

    public function test_unknown_source_and_malformed_coordinates_are_404(): void
    {
        $this->get('/tiles/nope/0/0/0')->assertNotFound();
        $this->get('/tiles/nope')->assertNotFound();
        $this->get('/tiles/atlas_entities/x/0/0')->assertNotFound();
        $this->get('/tiles/atlas_entities/123/0/0')->assertNotFound();
        $this->get('/tiles/atlas_entities/0/0')->assertNotFound();
    }

    public function test_tilejson_mirrors_martin_and_honours_the_forwarded_host(): void
    {
        $response = $this->get('/tiles/atlas_entities', [
            'X-Forwarded-Proto' => 'https',
            'X-Forwarded-Host' => 'api.example.org',
        ]);

        $response->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertHeader('Cache-Control', 'max-age=300, public');
        $json = $response->json();
        $this->assertSame('3.0.0', $json['tilejson']);
        $this->assertSame('atlas_entities', $json['name']);
        $this->assertSame('tiles.atlas_entities', $json['description']);
        $this->assertSame(['https://api.example.org/tiles/atlas_entities/{z}/{x}/{y}'], $json['tiles']);
        $this->assertSame(0, $json['minzoom']);
        $this->assertSame(14, $json['maxzoom']);
        $this->assertSame('entities', $json['vector_layers'][0]['id']);
        $this->assertCount(13, $json['vector_layers'][0]['fields']);
        $this->assertSame('Boolean', $json['vector_layers'][0]['fields']['has_map_story']);
    }

    public function test_catalog_lists_the_sources(): void
    {
        $this->get('/tiles/catalog')
            ->assertOk()
            ->assertJsonPath('tiles.atlas_entities.content_type', 'application/x-protobuf')
            ->assertJsonPath('tiles.atlas_entities.description', 'tiles.atlas_entities');
    }

    public function test_rendered_tiles_are_cached_until_the_ttl_or_a_flush(): void
    {
        $this->seedFeature('Cached Zed');
        $first = (string) $this->get('/tiles/atlas_entities/0/0/0')->getContent();

        $this->seedFeature('Later Zed');
        $this->assertStringNotContainsString('Later Zed', (string) $this->get('/tiles/atlas_entities/0/0/0')->getContent());

        Cache::flush();
        $fresh = (string) $this->get('/tiles/atlas_entities/0/0/0')->getContent();
        $this->assertStringContainsString('Later Zed', $fresh);
        $this->assertNotSame($first, $fresh);
    }

    public function test_a_zero_ttl_turns_the_cache_off(): void
    {
        config(['tiles.cache_ttl' => 0]);
        $this->seedFeature('Live Zed');
        $this->get('/tiles/atlas_entities/0/0/0')->assertOk();

        $this->seedFeature('Newer Zed');
        $this->assertStringContainsString('Newer Zed', (string) $this->get('/tiles/atlas_entities/0/0/0')->getContent());
    }

    public function test_tile_routes_carry_no_middleware_group_or_throttle(): void
    {
        foreach (['tiles.tile', 'tiles.tilejson', 'tiles.catalog'] as $name) {
            $route = Route::getRoutes()->getByName($name);
            $this->assertNotNull($route, $name);
            $this->assertSame([], $route->gatherMiddleware(), $name);
        }
    }

    /** One verified polity with one point period at (10.5, 40.5). */
    private function seedFeature(string $name): Entity
    {
        $entity = Entity::factory()->verified()->inGroup(EntityGroup::Polity)->create([
            'name' => $name,
            'impact_score' => 50,
        ]);

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'territory', 1200, 1250,
                ST_SetSRID(ST_Point(10.5, 40.5), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [Str::uuid()->toString(), $entity->entity_id],
        );

        return $entity;
    }
}
