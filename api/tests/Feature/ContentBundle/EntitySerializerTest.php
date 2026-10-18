<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityLocation;
use App\Support\ContentBundle\JsonLine;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;
use App\Support\ContentBundle\Serializers\EntitySerializer;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Opis\JsonSchema\Errors\ErrorFormatter;
use Tests\TestCase;

class EntitySerializerTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        // A column dropped from the serializer's select must throw, not export null.
        Model::preventAccessingMissingAttributes();
    }

    protected function tearDown(): void
    {
        Model::preventAccessingMissingAttributes(false);
        parent::tearDown();
    }

    private function entity(array $attrs = []): Entity
    {
        return Entity::factory()->create($attrs + ['wikidata_id' => null]);
    }

    private function seedChildren(Entity $e): void
    {
        $id = $e->entity_id;
        foreach ([['zeta', 'manual'], ['alpha', 'curated'], ['mid', 'derived']] as [$slug, $_]) {
            DB::table('tags')->insertOrIgnore(['slug' => $slug, 'name' => $slug, 'facet' => 'theme']);
        }
        foreach ([['zeta', 'manual'], ['alpha', 'curated'], ['mid', 'derived']] as [$slug, $source]) {
            DB::table('entity_tags')->insert(['entity_tag_id' => (string) Str::uuid(), 'entity_id' => $id, 'tag' => $slug, 'source' => $source]);
        }
        foreach ([['Beta', null, false], ['Zed', 'el', true], ['Alpha', 'en', false], ['Alpha', null, false]] as [$name, $lang, $primary]) {
            DB::table('entity_aliases')->insert(['alias_id' => (string) Str::uuid(), 'entity_id' => $id, 'name' => $name, 'language' => $lang, 'is_primary' => $primary]);
        }
        foreach ([['secondary', 10, 20, false], ['primary', 5, 30, true]] as [$type, $s, $en, $primary]) {
            DB::table('entity_temporal_ranges')->insert(['temporal_range_id' => (string) Str::uuid(), 'entity_id' => $id, 'range_type' => $type, 'start_year' => $s, 'end_year' => $en, 'is_primary' => $primary]);
        }
        EntityLocation::query()->create(['entity_id' => $id, 'location_name' => 'Rome', 'is_primary' => true, 'geom' => ['type' => 'Point', 'coordinates' => [12.4963655, 41.9027835]]]);
        EntityLocation::query()->create(['entity_id' => $id, 'location_name' => 'Alba', 'is_primary' => false]);
    }

    private function serialize(Entity $e, Profile $p = Profile::Full): array
    {
        $s = new EntitySerializer;

        return $s->serialize($s->query()->whereKey($e->entity_id)->firstOrFail(), $p);
    }

    public function test_record_has_exact_key_order_and_nested_key_order(): void
    {
        $e = $this->entity();
        $this->seedChildren($e);
        $r = $this->serialize($e);

        $this->assertSame(RecordType::Entities->keys(), array_keys($r));
        foreach (RecordType::Entities->nestedKeys() as $field => $keys) {
            $this->assertNotEmpty($r[$field]);
            foreach ($r[$field] as $item) {
                $this->assertSame($keys, array_keys($item), $field);
            }
        }
        $this->assertSame($e->entity_id, $r['id']);
        $this->assertSame($e->entity_type->value, $r['entity_type']);
    }

    public function test_nested_lists_are_sorted(): void
    {
        $e = $this->entity();
        $this->seedChildren($e);
        $r = $this->serialize($e);

        $this->assertSame([['Zed', 'el'], ['Alpha', 'en'], ['Alpha', null], ['Beta', null]], array_map(fn ($a) => [$a['name'], $a['language']], $r['aliases']));
        $this->assertSame(['primary', 'secondary'], array_column($r['temporal_ranges'], 'range_type'));
        $this->assertSame(['Rome', 'Alba'], array_column($r['locations'], 'location_name'));
    }

    public function test_derived_tags_are_not_exported_and_tags_sorted(): void
    {
        $e = $this->entity();
        $this->seedChildren($e);
        $r = $this->serialize($e);

        $this->assertSame([['slug' => 'alpha', 'source' => 'curated'], ['slug' => 'zeta', 'source' => 'manual']], $r['tags']);
    }

    public function test_geometry_is_geojson_with_at_most_seven_decimals(): void
    {
        $e = $this->entity();
        $this->seedChildren($e);
        $r = $this->serialize($e);

        $geom = $r['locations'][0]['geom'];
        $this->assertSame('Point', $geom['type']);
        $this->assertSame([12.4963655, 41.9027835], $geom['coordinates']);
        $this->assertNull($r['locations'][0]['territory_geom']);
        $this->assertNull($r['locations'][1]['geom']);
        $this->assertDoesNotMatchRegularExpression('/\.\d{8,}/', JsonLine::encode($r));
    }

    public function test_public_profile_drops_underscore_attributes_only(): void
    {
        $e = $this->entity(['attributes' => ['_rejected_wikidata_id' => 'Q1', 'entity_color' => '#fff']]);

        // jsonb does not preserve key order, so compare unordered.
        $this->assertEqualsCanonicalizing(['_rejected_wikidata_id' => 'Q1', 'entity_color' => '#fff'], (array) $this->serialize($e, Profile::Full)['attributes']);
        $this->assertSame(['entity_color' => '#fff'], (array) $this->serialize($e, Profile::Public)['attributes']);
    }

    public function test_empty_attributes_encode_as_empty_object(): void
    {
        $e = $this->entity(['attributes' => []]);
        $onlyPrivate = $this->entity(['attributes' => ['_x' => 1]]);

        $this->assertStringContainsString('"attributes":{}', JsonLine::encode($this->serialize($e)));
        $this->assertStringContainsString('"attributes":{}', JsonLine::encode($this->serialize($onlyPrivate, Profile::Public)));
    }

    public function test_nested_empty_jsonb_values_are_kept_as_stored(): void
    {
        $raw = '{"a_obj":{},"b_list":[],"c_full":{"k":{},"l":[1]},"_p":{}}';
        $e = $this->entity();
        DB::table('entities')->where('entity_id', $e->entity_id)->update(['attributes' => DB::raw("'".$raw."'::jsonb")]);

        $line = JsonLine::encode($this->serialize($e));
        $this->assertStringContainsString('"a_obj":{}', $line);
        $this->assertStringContainsString('"b_list":[]', $line);
        $this->assertStringContainsString('"c_full":{"k":{},"l":[1]}', $line);
        $this->assertSame($line, json_encode(json_decode($line), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION));

        $public = JsonLine::encode($this->serialize($e, Profile::Public));
        $this->assertStringNotContainsString('"_p"', $public);
        $this->assertStringContainsString('"a_obj":{}', $public);
    }

    public function test_source_citations_null_stays_null_and_empty_becomes_object(): void
    {
        $this->assertStringContainsString('"source_citations":null', JsonLine::encode($this->serialize($this->entity(['source_citations' => null]))));
        $this->assertStringContainsString('"source_citations":{}', JsonLine::encode($this->serialize($this->entity(['source_citations' => []]))));
    }

    public function test_serialized_record_validates_against_schema(): void
    {
        $e = $this->entity(['attributes' => ['_rejected_wikidata_id' => 'Q1', 'k' => 'v'], 'source_citations' => ['wikipedia' => ['url' => 'https://en.wikipedia.org/wiki/X']]]);
        $this->seedChildren($e);

        foreach ([Profile::Full, Profile::Public] as $profile) {
            $data = json_decode(JsonLine::encode($this->serialize($e, $profile)));
            $result = Schemas::validator()->validate($data, Schemas::recordSchemaId(RecordType::Entities));
            $this->assertTrue($result->isValid(), $result->isValid() ? '' : json_encode((new ErrorFormatter)->format($result->error())));
        }
    }

    private function assertValid(array $record): void
    {
        $result = Schemas::validator()->validate(json_decode(JsonLine::encode($record)), Schemas::recordSchemaId(RecordType::Entities));
        $this->assertTrue($result->isValid(), $result->isValid() ? '' : json_encode((new ErrorFormatter)->format($result->error())));
    }

    public function test_embedding_is_not_selected(): void
    {
        $e = $this->entity();
        $model = (new EntitySerializer)->query()->whereKey($e->entity_id)->firstOrFail();

        $this->assertArrayNotHasKey('embedding', $model->getAttributes());
    }

    public function test_query_count_is_constant(): void
    {
        $measure = function (int $n): int {
            Entity::query()->delete();
            foreach (range(1, $n) as $_) {
                $this->seedChildren($this->entity());
            }
            $s = new EntitySerializer;
            DB::flushQueryLog();
            DB::enableQueryLog();
            $s->query()->get()->each(fn ($m) => $s->serialize($m, Profile::Full));
            $count = count(DB::getQueryLog());
            DB::disableQueryLog();

            return $count;
        };

        $this->assertSame($measure(1), $measure(5));
        $this->assertSame(5, $measure(5));
    }

    public function test_fully_populated_entity_matches_raw_rows(): void
    {
        $e = $this->entity(['wikidata_id' => 'Q123', 'source_citations' => ['k' => 'v']]);
        $ref = EntityGeoRef::factory()->create(['entity_id' => $e->entity_id]);
        $e->forceFill(['primary_geo_ref_id' => $ref->geo_ref_id])->save();
        $e->update(['impact_score' => 7]);
        DB::table('entity_aliases')->insert(['alias_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'name' => 'Rome', 'language' => 'en', 'source' => 'wikidata', 'is_primary' => true]);
        DB::table('entity_temporal_ranges')->insert([
            'temporal_range_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'range_type' => 'primary', 'start_year' => -509, 'end_year' => -27,
            'start_date' => '-0509', 'end_date' => '-0027', 'duration_type' => 'period', 'date_method' => 'source_database', 'date_confidence' => 'high', 'is_primary' => true, 'notes' => 'n',
        ]);
        DB::table('entity_locations')->insert([
            'location_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'location_name' => 'Rome', 'location_method' => 'wikidata',
            'location_confidence' => 'high', 'is_primary' => true, 'notes' => 'n',
        ]);

        $r = $this->serialize($e);
        $row = (array) DB::table('entities')->where('entity_id', $e->entity_id)->first();

        $scalars = array_diff(RecordType::Entities->keys(), ['id', 'attributes', 'source_citations', 'aliases', 'tags', 'temporal_ranges', 'locations']);
        foreach ($scalars as $key) {
            $this->assertNotNull($r[$key], $key);
            $this->assertSame($row[$key], $r[$key], $key);
        }
        $this->assertSame($row['entity_id'], $r['id']);

        $alias = (array) DB::table('entity_aliases')->where('entity_id', $e->entity_id)->first();
        $this->assertSame(array_intersect_key($alias, array_flip(['name', 'language', 'source', 'is_primary'])), $r['aliases'][0]);
        $range = (array) DB::table('entity_temporal_ranges')->where('entity_id', $e->entity_id)->first();
        $this->assertSame(array_intersect_key($range, array_flip(RecordType::Entities->nestedKeys()['temporal_ranges'])), $r['temporal_ranges'][0]);
        $loc = (array) DB::table('entity_locations')->where('entity_id', $e->entity_id)->first();
        $expected = array_intersect_key($loc, array_flip(['location_name', 'location_method', 'location_confidence', 'is_primary', 'notes']));
        $actual = array_diff_key($r['locations'][0], ['geom' => 1, 'territory_geom' => 1]);
        $this->assertSame($expected, $actual);
        foreach ([...$r['temporal_ranges'][0], ...$actual] as $k => $v) {
            $this->assertNotNull($v, $k);
        }
        $this->assertNotNull($r['aliases'][0]['source']);
        $this->assertValid($r);
    }

    public function test_tied_items_serialize_identically_regardless_of_insert_order(): void
    {
        $make = function (bool $reverse): string {
            $e = $this->entity(['attributes' => []]);
            $aliases = [['source' => 'a'], ['source' => 'b']];
            $ranges = [['notes' => 'x'], ['notes' => 'y']];
            $locs = [['notes' => 'x'], ['notes' => 'y']];
            foreach ($reverse ? [array_reverse($aliases), array_reverse($ranges), array_reverse($locs)] : [$aliases, $ranges, $locs] as $i => $list) {
                foreach ($list as $row) {
                    match ($i) {
                        0 => DB::table('entity_aliases')->insert($row + ['alias_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'name' => 'Same', 'language' => 'en', 'is_primary' => false]),
                        1 => DB::table('entity_temporal_ranges')->insert($row + ['temporal_range_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'range_type' => 'primary', 'start_year' => 1, 'end_year' => 2, 'is_primary' => false]),
                        2 => DB::table('entity_locations')->insert($row + ['location_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'location_name' => 'Same', 'is_primary' => false]),
                    };
                }
            }
            $r = $this->serialize($e);

            return JsonLine::encode([$r['aliases'], $r['temporal_ranges'], $r['locations']]);
        };

        $this->assertSame($make(false), $make(true));
    }

    public function test_unknown_enum_value_is_exported_as_is_and_fails_validation(): void
    {
        $e = $this->entity();
        DB::table('entity_temporal_ranges')->insert(['temporal_range_id' => (string) Str::uuid(), 'entity_id' => $e->entity_id, 'range_type' => 'primary', 'is_primary' => true, 'date_method' => 'bogus_method']);

        $r = $this->serialize($e);
        $this->assertSame('bogus_method', $r['temporal_ranges'][0]['date_method']);

        $result = Schemas::validator()->validate(json_decode(JsonLine::encode($r)), Schemas::recordSchemaId(RecordType::Entities));
        $this->assertFalse($result->isValid());
    }

    public function test_entity_without_children_emits_empty_lists(): void
    {
        $line = JsonLine::encode($this->serialize($this->entity()));

        foreach (['aliases', 'tags', 'temporal_ranges', 'locations'] as $field) {
            $this->assertStringContainsString('"'.$field.'":[]', $line);
        }
    }
}
