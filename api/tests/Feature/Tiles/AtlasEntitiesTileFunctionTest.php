<?php

declare(strict_types=1);

namespace Tests\Feature\Tiles;

use App\Enums\EntityGroup;
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
 * presence in a tile is a substring test on the MVT bytes.
 */
class AtlasEntitiesTileFunctionTest extends TestCase
{
    use RefreshDatabase;

    public function test_tile_contains_seeded_feature_and_name(): void
    {
        $this->seedFeature('Testland Unique Name', 1200, 50);

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
        $this->seedFeature('Etag Zed', 1200, 50);

        $first = DB::selectOne('SELECT key, key = md5(mvt) AS is_md5 FROM tiles.atlas_entities(0, 0, 0)');
        $second = DB::selectOne('SELECT key FROM tiles.atlas_entities(0, 0, 0)');

        $this->assertTrue((bool) $first->is_md5);
        $this->assertSame($first->key, $second->key);
    }

    public function test_per_century_cap_keeps_top_ranked_at_low_zoom(): void
    {
        $names = [];
        foreach (range(0, 12) as $i) {
            $name = sprintf('Cap%02d Zed', $i + 1);
            $this->seedFeature($name, 1000 + $i, 70 - $i);
            $names[] = $name;
        }
        $lowest = array_pop($names);

        // z0 keeps 12 per century: the lowest-impact feature is dropped.
        $z0 = $this->tile(0, 0, 0);
        foreach ($names as $name) {
            $this->assertTileHasName($z0, $name);
        }
        $this->assertTileLacksName($z0, $lowest);

        // z12 keeps 96 per century: everything is there.
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
        $this->seedFeature('Curated Zed', 1000, 1, displayPriority: 10);

        $names = [];
        foreach (range(0, 11) as $i) {
            $name = sprintf('Pri%02d Zed', $i + 1);
            $this->seedFeature($name, 1000 + $i, 70 - $i);
            $names[] = $name;
        }

        $z0 = $this->tile(0, 0, 0);
        $this->assertTileHasName($z0, 'Curated Zed');
        $this->assertTileLacksName($z0, end($names));
    }

    public function test_cap_is_per_century(): void
    {
        $names = [];
        foreach (range(0, 11) as $i) {
            $this->seedFeature($names[] = sprintf('CentA%02d Zed', $i + 1), 1000 + $i, 70 - $i);
            $this->seedFeature($names[] = sprintf('CentB%02d Zed', $i + 1), 1500 + $i, 70 - $i);
        }

        $z0 = $this->tile(0, 0, 0);
        foreach ($names as $name) {
            $this->assertTileHasName($z0, $name);
        }
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
        $this->seedFeature('Plain Zed', 1200, 50);
        $z0 = $this->tile(0, 0, 0);
        $this->assertTileHasName($z0, 'has_map_story');
        $this->assertStringContainsString($false, $z0);
        $this->assertStringNotContainsString($true, $z0);

        // Add a story entity: the tile now also carries true.
        $battle = $this->seedFeature('Story Zed', 1200, 40);
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

    /** One entity with one point period at (10.5, 40.5); display_priority NULL unless given. */
    private function seedFeature(string $name, int $startYear, int $impact, ?int $displayPriority = null): Entity
    {
        $entity = Entity::factory()->verified()->inGroup(EntityGroup::Polity)->create([
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

    /** The raw MVT bytes of one tile. */
    private function tile(int $z, int $x, int $y): string
    {
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
