<?php

declare(strict_types=1);

namespace Tests\Feature\Tiles;

use App\Enums\EntityGroup;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

/**
 * `tiles.atlas_entities(z, x, y)` — the MVT function Martin publishes (D1, D4, D8).
 *
 * Every seeded entity sits at ST_Point(10.5, 40.5), which lies in tile z0 0/0
 * and z12 2167/1543. Names are fixed-width so that none is a prefix of another:
 * presence in a tile is a substring test on the MVT bytes. Tiles are cut from
 * `tiles.atlas_features`, refreshed before each read here.
 */
class AtlasEntitiesTileFunctionTest extends TestCase
{
    use RefreshDatabase;

    public function test_tile_contains_seeded_feature_and_name(): void
    {
        $this->seedFeature('Testland Unique Name', 1200, 95);
        $this->refreshFeatures();

        $row = DB::selectOne(
            "SELECT length(mvt) AS len,
                    position(convert_to('Testland Unique Name', 'UTF8') IN mvt) > 0 AS has_name
             FROM tiles.atlas_entities(0, 0, 0)",
        );

        $this->assertGreaterThan(0, (int) $row->len);
        $this->assertTrue((bool) $row->has_name);
    }

    public function test_etag_is_md5_of_tile_and_stable(): void
    {
        $this->seedFeature('Etag Zed', 1200, 95);
        $this->refreshFeatures();

        $first = DB::selectOne('SELECT key, key = md5(mvt) AS is_md5 FROM tiles.atlas_entities(0, 0, 0)');
        $second = DB::selectOne('SELECT key FROM tiles.atlas_entities(0, 0, 0)');

        $this->assertTrue((bool) $first->is_md5);
        $this->assertSame($first->key, $second->key);
    }

    public function test_per_century_cap_keeps_top_ranked_at_low_zoom(): void
    {
        $names = [];
        foreach (range(0, 8) as $i) {
            $name = sprintf('Cap%02d Zed', $i + 1);
            $this->seedFeature($name, 1000 + $i, 99 - $i);
            $names[] = $name;
        }
        $lowest = array_pop($names);

        // z0 keeps 8 per century: the lowest-impact feature is dropped.
        $z0 = $this->tile(0, 0, 0);
        foreach ($names as $name) {
            $this->assertTileHasName($z0, $name);
        }
        $this->assertTileLacksName($z0, $lowest);

        // z12 keeps 64 per century: everything is there.
        $this->assertTrue((bool) DB::selectOne(
            'SELECT ST_Intersects(ST_TileEnvelope(12, 2167, 1543),
                    ST_Transform(ST_SetSRID(ST_Point(10.5, 40.5), 4326), 3857)) AS inside',
        )->inside);
        $z12 = $this->tile(12, 2167, 1543);
        foreach ([...$names, $lowest] as $name) {
            $this->assertTileHasName($z12, $name);
        }
    }

    public function test_curated_priority_outranks_impact(): void
    {
        // A curated priority both opens the feature at z0 and ranks it first.
        $this->seedFeature('Curated Zed', 1000, 1, displayPriority: 95);

        $names = [];
        foreach (range(0, 7) as $i) {
            $name = sprintf('Pri%02d Zed', $i + 1);
            $this->seedFeature($name, 1000 + $i, 99 - $i);
            $names[] = $name;
        }

        $z0 = $this->tile(0, 0, 0);
        $this->assertTileHasName($z0, 'Curated Zed');
        $this->assertTileLacksName($z0, end($names));
    }

    public function test_cap_is_per_century(): void
    {
        $names = [];
        foreach (range(0, 7) as $i) {
            $this->seedFeature($names[] = sprintf('CentA%02d Zed', $i + 1), 1000 + $i, 99 - $i);
            $this->seedFeature($names[] = sprintf('CentB%02d Zed', $i + 1), 1500 + $i, 99 - $i);
        }

        $z0 = $this->tile(0, 0, 0);
        foreach ($names as $name) {
            $this->assertTileHasName($z0, $name);
        }
    }

    public function test_importance_sets_the_first_zoom_a_feature_appears_at(): void
    {
        $this->seedFeature('Major Zed', 1200, 92);
        $this->seedFeature('Middle Zed', 1210, 85);
        $this->seedFeature('Minor Zed', 1220, 65);

        $z2 = $this->tile(2, ...$this->seedTile(2));
        $this->assertTileHasName($z2, 'Major Zed');
        $this->assertTileLacksName($z2, 'Middle Zed');

        $z3 = $this->tile(3, ...$this->seedTile(3));
        $this->assertTileHasName($z3, 'Middle Zed');
        $this->assertTileLacksName($z3, 'Minor Zed');

        $this->assertTileHasName($this->tile(7, ...$this->seedTile(7)), 'Minor Zed');
    }

    public function test_cities_and_other_places_wait_for_closer_zooms(): void
    {
        $this->seedFeature('Great City Zed', 1200, 95, type: EntityType::City);
        $this->seedFeature('Small City Zed', 1210, 60, type: EntityType::City);
        $this->seedFeature('Monument Zed', 1220, 95, type: EntityType::InfrastructureMonument);

        foreach ([0, 3, 6] as $z) {
            $tile = $this->tile($z, ...$this->seedTile($z));
            $this->assertTileLacksName($tile, 'Great City Zed');
            $this->assertTileLacksName($tile, 'Monument Zed');
        }

        $z7 = $this->tile(7, ...$this->seedTile(7));
        $this->assertTileHasName($z7, 'Great City Zed');
        $this->assertTileLacksName($z7, 'Small City Zed');

        $z9 = $this->tile(9, ...$this->seedTile(9));
        $this->assertTileHasName($z9, 'Small City Zed');
        $this->assertTileHasName($z9, 'Monument Zed');
    }

    public function test_refresh_command_runs_only_when_the_content_changed(): void
    {
        $this->artisan('tiles:refresh')->expectsOutputToContain('refreshed')->assertSuccessful();
        $this->artisan('tiles:refresh')->expectsOutputToContain('current')->assertSuccessful();

        $this->seedFeature('Fresh Zed', 1200, 95);
        $this->artisan('tiles:refresh')->expectsOutputToContain('refreshed')->assertSuccessful();
        $this->assertSame(1, DB::table('tiles.atlas_features')->where('name', 'Fresh Zed')->count());

        $this->artisan('tiles:refresh --force')->expectsOutputToContain('refreshed')->assertSuccessful();
    }

    public function test_out_of_range_coordinates_return_an_empty_tile(): void
    {
        foreach ([[0, 5, 5], [3, -1, 0], [2, 0, 4], [31, 0, 0]] as [$z, $x, $y]) {
            $row = DB::selectOne(
                "SELECT mvt = ''::bytea AS is_empty, key = md5(''::bytea) AS key_ok FROM tiles.atlas_entities(?, ?, ?)",
                [$z, $x, $y],
            );
            $this->assertTrue((bool) $row->is_empty, "z{$z}/{$x}/{$y}");
            $this->assertTrue((bool) $row->key_ok);
        }
    }

    public function test_empty_tile_returns_empty_bytea_not_null(): void
    {
        $this->seedFeature('Elsewhere Zed', 1200, 50);

        $row = DB::selectOne(
            "SELECT mvt IS NULL AS is_null, mvt = ''::bytea AS is_empty, key
             FROM tiles.atlas_entities(14, 0, 0)",
        );

        $this->assertFalse((bool) $row->is_null);
        $this->assertTrue((bool) $row->is_empty);
        $this->assertSame(md5(''), $row->key);
    }

    public function test_tilejson_comment_declares_the_entities_layer(): void
    {
        $comment = DB::selectOne(
            "SELECT obj_description('tiles.atlas_entities(integer,integer,integer)'::regprocedure, 'pg_proc') AS c",
        )->c;

        $tileJson = json_decode((string) $comment, true, flags: JSON_THROW_ON_ERROR);

        $this->assertSame('entities', $tileJson['vector_layers'][0]['id']);
        $this->assertSame([
            'id', 'name', 'entity_type', 'entity_group', 'impact_score', 'display_priority',
            'start_year', 'end_year', 'start_decdate', 'end_decdate', 'entity_color', 'ohm_osm_id',
            'has_map_story',
        ], array_keys($tileJson['vector_layers'][0]['fields']));
        $this->assertSame('Boolean', $tileJson['vector_layers'][0]['fields']['has_map_story']);
    }

    public function test_tile_carries_has_map_story(): void
    {
        // An MVT bool value is the layer `values` entry 0x22 0x02 0x38 <0|1>
        // (field 4 length 2, Value.bool_value = field 7); no other tile
        // property is a boolean.
        $true = "\x22\x02\x38\x01";
        $false = "\x22\x02\x38\x00";

        // Only a plain entity: the key is there, with false.
        $this->seedFeature('Plain Zed', 1200, 95);
        $z0 = $this->tile(0, 0, 0);
        $this->assertTileHasName($z0, 'has_map_story');
        $this->assertStringContainsString($false, $z0);
        $this->assertStringNotContainsString($true, $z0);

        // Add a story entity: the tile now also carries true.
        $battle = $this->seedFeature('Story Zed', 1200, 94);
        DB::statement(
            "INSERT INTO map_stories (entity_id, slug, kind, title, year, step_count, document, created_at, updated_at)
             VALUES (?, 'battle-of-story-zed', 'battle', 'Story Zed', 1200, 1, '{}'::jsonb, NOW(), NOW())",
            [$battle->entity_id],
        );
        $z0 = $this->tile(0, 0, 0);
        $this->assertTileHasName($z0, 'Story Zed');
        $this->assertTileHasName($z0, 'has_map_story');
        $this->assertStringContainsString($true, $z0);
    }

    /**
     * One entity with one point period at (10.5, 40.5); display_priority NULL
     * unless given, a polity unless a type is given.
     */
    private function seedFeature(string $name, int $startYear, int $impact, ?int $displayPriority = null, ?EntityType $type = null): Entity
    {
        $factory = Entity::factory()->verified();
        $factory = $type === null ? $factory->inGroup(EntityGroup::Polity) : $factory->ofType($type);
        $entity = $factory->create([
            'name' => $name,
            'impact_score' => $impact,
            'display_priority' => $displayPriority,
        ]);

        DB::statement(
            "INSERT INTO geometry_periods (
                geometry_period_id, entity_id, period_type, start_year, end_year,
                geom, provenance_mode, created_by, created_at, updated_at
            ) VALUES (
                ?, ?, 'territory', ?, ?,
                ST_SetSRID(ST_Point(10.5, 40.5), 4326),
                'manual', 'test', NOW(), NOW()
            )",
            [Str::uuid()->toString(), $entity->entity_id, $startYear, $startYear + 50],
        );

        return $entity;
    }

    private function refreshFeatures(): void
    {
        DB::statement('REFRESH MATERIALIZED VIEW tiles.atlas_features');
    }

    /** The tile [x, y] that holds the seed point (10.5, 40.5) at zoom z. */
    private function seedTile(int $z): array
    {
        $n = 2 ** $z;
        $lat = deg2rad(40.5);

        return [
            (int) floor((10.5 + 180) / 360 * $n),
            (int) floor((1 - log(tan($lat) + 1 / cos($lat)) / M_PI) / 2 * $n),
        ];
    }

    /** The raw MVT bytes of one tile, cut after a refresh of the feature table. */
    private function tile(int $z, int $x, int $y): string
    {
        $this->refreshFeatures();
        $hex = DB::selectOne(
            "SELECT encode(mvt, 'hex') AS hex FROM tiles.atlas_entities(?, ?, ?)",
            [$z, $x, $y],
        )->hex;

        return (string) hex2bin((string) $hex);
    }

    private function assertTileHasName(string $tile, string $name): void
    {
        $this->assertTrue(str_contains($tile, $name), "Expected '{$name}' in the tile.");
    }

    private function assertTileLacksName(string $tile, string $name): void
    {
        $this->assertFalse(str_contains($tile, $name), "Did not expect '{$name}' in the tile.");
    }
}
