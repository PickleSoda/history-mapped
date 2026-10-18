<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use App\Support\ContentBundle\JsonLine;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;
use App\Support\ContentBundle\Serializers\ChronicleEntrySerializer;
use App\Support\ContentBundle\Serializers\ChronicleSerializer;
use App\Support\ContentBundle\Serializers\EntitySerializer;
use App\Support\ContentBundle\Serializers\GeometryPeriodSerializer;
use App\Support\ContentBundle\Serializers\GeoRefSerializer;
use App\Support\ContentBundle\Serializers\RecordSerializer;
use App\Support\ContentBundle\Serializers\RelationshipSerializer;
use App\Support\ContentBundle\Serializers\Serializers;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Opis\JsonSchema\Errors\ErrorFormatter;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class RecordSerializersTest extends TestCase
{
    use RefreshDatabase;

    private const POINT = ['type' => 'Point', 'coordinates' => [12.4963655, 41.9027835]];

    private const POLYGON = ['type' => 'Polygon', 'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 41.0]]]];

    protected function setUp(): void
    {
        parent::setUp();
        // A column dropped from a serializer's select must throw, not export null.
        Model::preventAccessingMissingAttributes();
    }

    protected function tearDown(): void
    {
        Model::preventAccessingMissingAttributes(false);
        parent::tearDown();
    }

    /** @return array<string, array{0: string}> */
    public static function types(): array
    {
        $types = array_filter(RecordType::cases(), fn (RecordType $t) => $t !== RecordType::Entities);

        return array_combine(
            array_map(fn (RecordType $t) => $t->value, $types),
            array_map(fn (RecordType $t) => [$t->value], $types),
        );
    }

    private function entity(): Entity
    {
        return Entity::factory()->create(['wikidata_id' => null]);
    }

    private function relationship(array $over = []): EntityRelationship
    {
        return EntityRelationship::query()->create($over + [
            'relationship_id' => (string) Str::uuid(),
            'source_entity_id' => $this->entity()->entity_id,
            'target_entity_id' => $this->entity()->entity_id,
            'relationship_type' => 'allied_with',
            'temporal_start' => '-0509',
            'temporal_end' => '-0027',
            'start_year' => -509,
            'end_year' => -27,
            'description' => 'Alliance against the Latin League.',
            'confidence' => 'high',
            'derive_geometry_period' => false,
            'source_citations' => ['wikidata' => ['qid' => 'Q1', 'refs' => [], 'meta' => (object) []]],
        ]);
    }

    private function period(array $over = []): GeometryPeriod
    {
        $rel = $this->relationship();

        return GeometryPeriod::query()->forceCreate($over + [
            'geometry_period_id' => (string) Str::uuid(),
            'entity_id' => $rel->source_entity_id,
            'period_type' => 'presence',
            'start_year' => -509,
            'end_year' => -27,
            'description' => 'Core territory.',
            'confidence' => 'medium',
            'provenance_mode' => 'derived',
            'relationship_id' => $rel->relationship_id,
            'source_event_id' => $this->entity()->entity_id,
            'geom' => self::POINT,
            'territory_geom' => self::POLYGON,
        ]);
    }

    private function geoRef(array $over = []): EntityGeoRef
    {
        $period = $this->period();

        return EntityGeoRef::query()->create($over + [
            'geo_ref_id' => (string) Str::uuid(),
            'entity_id' => $period->entity_id,
            'geometry_period_id' => $period->geometry_period_id,
            'provider' => 'ohm',
            'external_type' => 'relation',
            'external_id' => '2698123',
            'match_role' => 'primary',
            'retrieval_method' => 'overpass',
            'temporal_start' => '-0509',
            'temporal_end' => '-0027',
            'temporal_start_year' => -509,
            'temporal_end_year' => -27,
            'match_score' => 0.85,
            'is_active' => false,
            'external_tags' => ['name' => 'Roman Republic', 'nested' => (object) []],
            'source_meta' => ['query' => 'rel[name=Roman Republic]'],
        ]);
    }

    private function chronicle(array $over = []): Chronicle
    {
        $c = Chronicle::factory()->create($over + [
            'slug' => 'rise-'.Str::lower(Str::random(6)),
            'source_type' => 'article',
            'status' => 'published',
            'start_year' => -509,
            'end_year' => -264,
            'impact_score' => 80,
            'approximate_location' => ['lat' => 41.9, 'lon' => 12.5],
            'metadata' => ['campaign' => 'e03'],
        ]);
        foreach ([['zeta', 'manual'], ['alpha', 'curated'], ['mid', 'derived']] as [$slug, $source]) {
            DB::table('tags')->insertOrIgnore(['slug' => $slug, 'name' => $slug, 'facet' => 'theme']);
            DB::table('chronicle_tags')->insert(['chronicle_id' => $c->chronicle_id, 'tag' => $slug, 'source' => $source]);
        }

        return $c;
    }

    private function entry(array $over = []): ChronicleEntry
    {
        $entry = ChronicleEntry::factory()->create($over + [
            'sequence_order' => 3,
            'start_year' => -494,
            'end_year' => -493,
            'impact_score' => 60,
            'primary_relationship_id' => $this->relationship()->relationship_id,
            'narrative_text' => 'The plebeians withdrew from Rome.',
            'notes' => 'Dates approximate.',
            'approximate_location' => ['lat' => 41.9, 'lon' => 12.5],
            'source_evidence' => 'event:0',
            'generated_by' => 'historical-agent-pipeline',
        ]);
        foreach ([['mentioned', 2], ['participant', 1], ['location', null]] as [$role, $seq]) {
            DB::table('chronicle_entry_entities')->insert(['entry_id' => $entry->entry_id, 'entity_id' => $this->entity()->entity_id, 'role' => $role, 'sequence_in_entry' => $seq]);
        }

        return $entry;
    }

    /** Builds one fully populated record and returns its primary key. */
    private function populate(RecordType $type): string
    {
        return match ($type) {
            RecordType::Relationships => $this->relationship()->relationship_id,
            RecordType::GeometryPeriods => $this->period()->geometry_period_id,
            RecordType::GeoRefs => $this->geoRef()->geo_ref_id,
            RecordType::Chronicles => $this->chronicle()->chronicle_id,
            RecordType::ChronicleEntries => $this->entry()->entry_id,
            RecordType::Entities => $this->entity()->entity_id,
        };
    }

    private function serializer(RecordType $type): RecordSerializer
    {
        return Serializers::for($type);
    }

    /** @return array<string, mixed> */
    private function serialize(RecordType $type, string $id, Profile $p = Profile::Full): array
    {
        $s = $this->serializer($type);

        return $s->serialize($s->query()->whereKey($id)->firstOrFail(), $p);
    }

    private function assertValid(RecordType $type, array $record): void
    {
        $result = Schemas::validator()->validate(json_decode(JsonLine::encode($record)), Schemas::recordSchemaId($type));
        $this->assertTrue($result->isValid(), $result->isValid() ? '' : json_encode((new ErrorFormatter)->format($result->error())));
    }

    /** Keys whose value is not a plain copy of the same-named column, per type. */
    private static function special(RecordType $type): array
    {
        return match ($type) {
            RecordType::Relationships => ['source_citations'],
            RecordType::GeometryPeriods => ['geom', 'territory_geom'],
            RecordType::GeoRefs => ['match_score', 'external_tags', 'source_meta'],
            RecordType::Chronicles => ['approximate_location', 'metadata', 'tags'],
            RecordType::ChronicleEntries => ['approximate_location', 'source_evidence', 'entities'],
            RecordType::Entities => [],
        };
    }

    #[DataProvider('types')]
    public function test_record_shape_schema_and_raw_row(string $name): void
    {
        $type = RecordType::from($name);
        $id = $this->populate($type);
        $r = $this->serialize($type, $id);

        $this->assertSame($type->keys(), array_keys($r));
        foreach ([Profile::Full, Profile::Public] as $profile) {
            $this->assertValid($type, $this->serialize($type, $id, $profile));
        }
        foreach ($r as $key => $value) {
            $this->assertNotNull($value, $key);
        }

        $row = (array) DB::table($type->modelClass()::query()->getModel()->getTable())->where($type->primaryKey(), $id)->first();
        $this->assertSame($row[$type->primaryKey()], $r['id']);
        foreach (array_diff($type->keys(), ['id'], self::special($type)) as $key) {
            $this->assertSame($row[$key], $r[$key], $key);
        }
        // Non-empty free-form jsonb must survive byte for byte, including nested `{}`.
        foreach (array_intersect(['source_citations', 'external_tags', 'source_meta', 'metadata', 'approximate_location'], array_keys($r)) as $k) {
            $this->assertSame(JsonLine::encode(['v' => json_decode($row[$k])]), JsonLine::encode(['v' => $r[$k]]), $k);
        }
    }

    public function test_lazy_by_id_works_with_qualified_selects(): void
    {
        foreach (range(1, 5) as $_) {
            $this->period();
        }
        $s = $this->serializer(RecordType::GeometryPeriods);

        $ids = $s->query()->lazyById(2, 'geometry_periods.geometry_period_id', 'geometry_period_id')
            ->map(fn ($m) => $s->serialize($m, Profile::Full)['id'])->all();

        $this->assertCount(5, $ids);
        $this->assertCount(5, array_unique($ids));
    }

    #[DataProvider('types')]
    public function test_query_count_is_constant_per_serializer(string $name): void
    {
        $type = RecordType::from($name);
        $measure = function (int $n) use ($type): int {
            $type->modelClass()::query()->delete();
            foreach (range(1, $n) as $_) {
                $this->populate($type);
            }
            $s = $this->serializer($type);
            DB::flushQueryLog();
            DB::enableQueryLog();
            $s->query()->get()->each(fn ($m) => $s->serialize($m, Profile::Full));
            $count = count(DB::getQueryLog());
            DB::disableQueryLog();

            return $count;
        };

        $one = $measure(1);
        $this->assertSame($one, $measure(5));
        $this->assertGreaterThanOrEqual(1, $one);
        $this->assertLessThanOrEqual(5, $one);
    }

    public function test_relationship_source_citations_null_and_empty(): void
    {
        $null = $this->relationship(['source_citations' => null]);
        $empty = $this->relationship(['source_citations' => []]);
        $nested = $this->relationship();

        $this->assertStringContainsString('"source_citations":null', JsonLine::encode($this->serialize(RecordType::Relationships, $null->relationship_id)));
        $this->assertStringContainsString('"source_citations":{}', JsonLine::encode($this->serialize(RecordType::Relationships, $empty->relationship_id)));
        $line = JsonLine::encode($this->serialize(RecordType::Relationships, $nested->relationship_id));
        $this->assertStringContainsString('"meta":{}', $line);
        $this->assertStringContainsString('"refs":[]', $line);
    }

    public function test_geometry_is_geojson_with_at_most_seven_decimals(): void
    {
        $r = $this->serialize(RecordType::GeometryPeriods, $this->period()->geometry_period_id);

        $this->assertSame(self::POINT, $r['geom']);
        $this->assertSame(self::POLYGON['type'], $r['territory_geom']['type']);
        $this->assertDoesNotMatchRegularExpression('/\.\d{8,}/', JsonLine::encode($r));

        $onlyTerritory = $this->period(['geom' => null, 'relationship_id' => $this->relationship()->relationship_id]);
        $r = $this->serialize(RecordType::GeometryPeriods, $onlyTerritory->geometry_period_id);
        $this->assertNull($r['geom']);
        $this->assertNotNull($r['territory_geom']);
    }

    public function test_missing_geojson_alias_throws_instead_of_exporting_null(): void
    {
        $id = $this->period()->geometry_period_id;
        $model = GeometryPeriod::query()
            ->select(['geometry_period_id', 'entity_id', 'period_type', 'start_year', 'end_year', 'description', 'confidence', 'provenance_mode', 'relationship_id', 'source_event_id'])
            ->selectRaw('ST_AsGeoJSON(geom, 7) as geom_geojsn') // mistyped alias
            ->selectRaw('ST_AsGeoJSON(territory_geom, 7) as territory_geom_geojson')
            ->whereKey($id)->firstOrFail();

        $this->expectException(\LogicException::class);
        (new GeometryPeriodSerializer)->serialize($model, Profile::Full);
    }

    public function test_match_score_is_a_float_or_null(): void
    {
        $r = $this->serialize(RecordType::GeoRefs, $this->geoRef(['match_score' => 0.85])->geo_ref_id);
        $this->assertSame(0.85, $r['match_score']);
        $this->assertStringContainsString('"match_score":0.85', JsonLine::encode($r));

        $one = $this->serialize(RecordType::GeoRefs, $this->geoRef(['match_score' => 1])->geo_ref_id);
        $this->assertStringContainsString('"match_score":1.0', JsonLine::encode($one));

        $this->assertNull($this->serialize(RecordType::GeoRefs, $this->geoRef(['match_score' => null])->geo_ref_id)['match_score']);
    }

    public function test_geo_ref_empty_jsonb_is_object_and_null_stays_null(): void
    {
        $empty = $this->geoRef(['external_tags' => [], 'source_meta' => []]);
        $null = $this->geoRef(['external_tags' => null, 'source_meta' => null]);

        $line = JsonLine::encode($this->serialize(RecordType::GeoRefs, $empty->geo_ref_id));
        $this->assertStringContainsString('"external_tags":{}', $line);
        $this->assertStringContainsString('"source_meta":{}', $line);
        $line = JsonLine::encode($this->serialize(RecordType::GeoRefs, $null->geo_ref_id));
        $this->assertStringContainsString('"external_tags":null', $line);
        $this->assertStringContainsString('"source_meta":null', $line);
    }

    public function test_public_profile_nulls_source_meta_only(): void
    {
        $id = $this->geoRef()->geo_ref_id;
        $full = $this->serialize(RecordType::GeoRefs, $id);
        $public = $this->serialize(RecordType::GeoRefs, $id, Profile::Public);

        $this->assertNotNull($full['source_meta']);
        $this->assertNull($public['source_meta']);
        $this->assertEquals($full, [...$public, 'source_meta' => $full['source_meta']]);
        $this->assertSame(RecordType::GeoRefs->keys(), array_keys($public));
    }

    public function test_chronicle_tags_are_curated_and_manual_only_and_sorted(): void
    {
        $r = $this->serialize(RecordType::Chronicles, $this->chronicle()->chronicle_id);

        $this->assertSame([['slug' => 'alpha', 'source' => 'curated'], ['slug' => 'zeta', 'source' => 'manual']], $r['tags']);
    }

    public function test_chronicle_empty_jsonb_is_object_and_null_location_stays_null(): void
    {
        $empty = $this->chronicle(['metadata' => [], 'approximate_location' => []]);
        $null = $this->chronicle(['approximate_location' => null]);

        $line = JsonLine::encode($this->serialize(RecordType::Chronicles, $empty->chronicle_id));
        $this->assertStringContainsString('"approximate_location":{}', $line);
        $this->assertStringContainsString('"metadata":{}', $line);
        $this->assertStringContainsString('"approximate_location":null', JsonLine::encode($this->serialize(RecordType::Chronicles, $null->chronicle_id)));
    }

    public function test_entry_entities_carry_role_and_sequence_sorted_without_hydrating_entities(): void
    {
        $entry = $this->entry();
        DB::flushQueryLog();
        DB::enableQueryLog();
        $r = $this->serialize(RecordType::ChronicleEntries, $entry->entry_id);
        $queries = array_column(DB::getQueryLog(), 'query');
        DB::disableQueryLog();

        $this->assertSame([['participant', 1], ['mentioned', 2], ['location', null]], array_map(fn ($e) => [$e['role'], $e['sequence_in_entry']], $r['entities']));
        foreach ($r['entities'] as $e) {
            $this->assertSame(['entity_id', 'role', 'sequence_in_entry'], array_keys($e));
        }
        foreach ($queries as $q) {
            $this->assertStringNotContainsString('from "entities"', $q);
        }
    }

    public function test_entry_ties_on_sequence_break_on_entity_id(): void
    {
        $entry = $this->entry();
        DB::table('chronicle_entry_entities')->where('entry_id', $entry->entry_id)->delete();
        $ids = ['22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111'];
        foreach ($ids as $id) {
            Entity::factory()->create(['entity_id' => $id, 'wikidata_id' => null]);
            DB::table('chronicle_entry_entities')->insert(['entry_id' => $entry->entry_id, 'entity_id' => $id, 'role' => 'participant', 'sequence_in_entry' => 1]);
        }

        $r = $this->serialize(RecordType::ChronicleEntries, $entry->entry_id);
        $this->assertSame(array_reverse($ids), array_column($r['entities'], 'entity_id'));
    }

    public function test_source_evidence_is_emitted_exactly_as_stored(): void
    {
        foreach (['"event:0"', '["a",{"b":{}}]', '{"k":[]}', 'null'] as $json) {
            $entry = $this->entry();
            DB::table('chronicle_entries')->where('entry_id', $entry->entry_id)->update(['source_evidence' => DB::raw("'".$json."'::jsonb")]);
            $line = JsonLine::encode($this->serialize(RecordType::ChronicleEntries, $entry->entry_id));
            $this->assertStringContainsString('"source_evidence":'.$json.',', $line);
        }

        $entry = $this->entry(['source_evidence' => null]);
        $this->assertNull($this->serialize(RecordType::ChronicleEntries, $entry->entry_id)['source_evidence']);
    }

    public function test_entry_without_links_emits_empty_list_and_null_location_stays_null(): void
    {
        $entry = $this->entry(['approximate_location' => null]);
        DB::table('chronicle_entry_entities')->where('entry_id', $entry->entry_id)->delete();

        $line = JsonLine::encode($this->serialize(RecordType::ChronicleEntries, $entry->entry_id));
        $this->assertStringContainsString('"approximate_location":null', $line);
        $this->assertStringEndsWith('"entities":[]}', $line);
    }

    public function test_serializers_resolve_in_record_type_order_through_the_container(): void
    {
        $all = Serializers::all();

        $this->assertSame(array_map(fn (RecordType $t) => $t->value, RecordType::cases()), array_keys($all));
        foreach (RecordType::cases() as $type) {
            $this->assertSame($type, $all[$type->value]->type());
        }
        $this->assertInstanceOf(EntitySerializer::class, $all['entities']);
        $this->assertInstanceOf(RelationshipSerializer::class, $all['relationships']);
        $this->assertInstanceOf(GeometryPeriodSerializer::class, $all['geometry_periods']);
        $this->assertInstanceOf(GeoRefSerializer::class, $all['geo_refs']);
        $this->assertInstanceOf(ChronicleSerializer::class, $all['chronicles']);
        $this->assertInstanceOf(ChronicleEntrySerializer::class, $all['chronicle_entries']);
    }
}
