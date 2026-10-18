<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Enums\ChronicleEntryRole;
use App\Enums\ChronicleStatus;
use App\Enums\ConfidenceLevel;
use App\Enums\DateResolutionMethod;
use App\Enums\DurationType;
use App\Enums\EntityType;
use App\Enums\GeoRefExternalType;
use App\Enums\GeoRefMatchRole;
use App\Enums\GeoRefProvider;
use App\Enums\GeoRefRetrievalMethod;
use App\Enums\IconClass;
use App\Enums\LocationResolutionMethod;
use App\Enums\RelationshipType;
use App\Enums\SourceType;
use App\Enums\TagSource;
use App\Enums\VerificationStatus;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;
use App\Support\ContentBundle\BundleFormat;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Opis\JsonSchema\Errors\ErrorFormatter;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\Support\ContentBundleFixtures;
use Tests\TestCase;

class SchemasTest extends TestCase
{
    use RefreshDatabase;

    private const UUID = '11111111-1111-4111-8111-111111111111';

    /**
     * Every enum-backed column: [record type, property path, model, column, enum].
     * The path is relative to the record schema ('aliases.items' style for nested lists).
     *
     * @return array<string, array{0: RecordType, 1: list<string>, 2: class-string, 3: string, 4: class-string}>
     */
    public static function enumColumns(): array
    {
        $rows = [];
        $add = function (RecordType $type, array $path, string $model, string $column, string $enum) use (&$rows): void {
            $rows[$type->value.'.'.implode('.', $path)] = [$type, $path, $model, $column, $enum];
        };

        $entityEnums = [
            'entity_type' => EntityType::class,
            'verification_status' => VerificationStatus::class,
            'confidence' => ConfidenceLevel::class,
            'location_confidence' => ConfidenceLevel::class,
            'date_confidence' => ConfidenceLevel::class,
            'date_method' => DateResolutionMethod::class,
            'duration_type' => DurationType::class,
            'location_method' => LocationResolutionMethod::class,
            'icon_class' => IconClass::class,
        ];
        foreach ($entityEnums as $column => $enum) {
            $add(RecordType::Entities, [$column], Entity::class, $column, $enum);
        }
        $add(RecordType::Entities, ['temporal_ranges', 'duration_type'], EntityTemporalRange::class, 'duration_type', DurationType::class);
        $add(RecordType::Entities, ['temporal_ranges', 'date_method'], EntityTemporalRange::class, 'date_method', DateResolutionMethod::class);
        $add(RecordType::Entities, ['temporal_ranges', 'date_confidence'], EntityTemporalRange::class, 'date_confidence', ConfidenceLevel::class);
        $add(RecordType::Entities, ['locations', 'location_method'], EntityLocation::class, 'location_method', LocationResolutionMethod::class);
        $add(RecordType::Entities, ['locations', 'location_confidence'], EntityLocation::class, 'location_confidence', ConfidenceLevel::class);

        $add(RecordType::Relationships, ['relationship_type'], EntityRelationship::class, 'relationship_type', RelationshipType::class);
        $add(RecordType::Relationships, ['confidence'], EntityRelationship::class, 'confidence', ConfidenceLevel::class);
        $add(RecordType::GeometryPeriods, ['confidence'], GeometryPeriod::class, 'confidence', ConfidenceLevel::class);

        foreach ([
            'provider' => GeoRefProvider::class,
            'external_type' => GeoRefExternalType::class,
            'match_role' => GeoRefMatchRole::class,
            'retrieval_method' => GeoRefRetrievalMethod::class,
        ] as $column => $enum) {
            $add(RecordType::GeoRefs, [$column], EntityGeoRef::class, $column, $enum);
        }

        $add(RecordType::Chronicles, ['status'], Chronicle::class, 'status', ChronicleStatus::class);
        $add(RecordType::Chronicles, ['source_type'], Chronicle::class, 'source_type', SourceType::class);

        return $rows;
    }

    private function load(string $path): array
    {
        return json_decode((string) file_get_contents($path), true, flags: JSON_THROW_ON_ERROR);
    }

    /** @return list<string> */
    private function enumValues(array $property): array
    {
        if (isset($property['$ref'])) {
            $this->assertStringStartsWith('common.schema.json#/$defs/', $property['$ref']);
            $def = substr($property['$ref'], strlen('common.schema.json#/$defs/'));

            return $this->load(BundleFormat::schemaDir().'/common.schema.json')['$defs'][$def]['enum'];
        }
        if (isset($property['enum'])) {
            return $property['enum'];
        }
        foreach ($property['anyOf'] ?? [] as $branch) {
            if (isset($branch['$ref']) || isset($branch['enum'])) {
                return $this->enumValues($branch);
            }
        }
        $this->fail('No enum in property '.json_encode($property));
    }

    /** @param list<string> $path */
    private function property(RecordType $type, array $path): array
    {
        $node = $this->load($type->schemaPath());
        foreach ($path as $i => $key) {
            $node = $node['properties'][$key];
            if ($i < count($path) - 1) {
                $node = $node['items'];
            }
        }

        return $node;
    }

    public function test_every_schema_parses_and_compiles(): void
    {
        $files = glob(BundleFormat::schemaDir().'/*.schema.json');
        $this->assertCount(8, $files);

        foreach ($files as $file) {
            $this->assertIsArray($this->load($file));
        }
    }

    public function test_fully_populated_line_is_valid_for_every_type(): void
    {
        foreach (RecordType::cases() as $type) {
            $line = ContentBundleFixtures::all()[$type->value];
            $this->assertSame($type->keys(), array_keys($line), $type->value.' fixture keys');
            foreach ($line as $key => $value) {
                $this->assertNotNull($value, $type->value.'.'.$key);
            }
            foreach (array_keys($type->nestedKeys()) as $field) {
                $this->assertCount(1, $line[$field], $type->value.'.'.$field);
            }
            $result = Schemas::validator()->validate(json_decode(json_encode($line)), Schemas::recordSchemaId($type));
            $this->assertTrue($result->isValid(), $type->value.': '.json_encode($result->error()?->message()));
        }
    }

    /**
     * @param  list<string>  $path
     * @param  class-string  $model
     * @param  class-string<\BackedEnum>  $enum
     */
    #[DataProvider('enumColumns')]
    public function test_schema_enums_match_php_enums_and_postgres(RecordType $type, array $path, string $model, string $column, string $enum): void
    {
        $expected = array_column($enum::cases(), 'value');
        $this->assertSame($expected, $this->enumValues($this->property($type, $path)));

        // Where the model casts the column, it must cast to this enum.
        $casts = (new $model)->getCasts();
        $this->assertArrayHasKey($column, $casts);
        $this->assertSame($enum, $casts[$column]);

        // Where Postgres has a native enum for the column, the labels must match too.
        $table = (new $model)->getTable();
        $udt = DB::selectOne(
            'select c.udt_name, t.typtype from information_schema.columns c join pg_type t on t.typname = c.udt_name
             where c.table_name = ? and c.column_name = ? and c.table_schema = current_schema()',
            [$table, $column]
        );
        $this->assertNotNull($udt);
        if ($udt->typtype === 'e') {
            $labels = DB::table('pg_enum as e')->join('pg_type as t', 't.oid', '=', 'e.enumtypid')
                ->where('t.typname', $udt->udt_name)->orderBy('e.enumsortorder')->pluck('e.enumlabel')->all();
            // Labels added later by ALTER TYPE sit at the end in Postgres, so compare as sets.
            sort($labels);
            $sorted = $expected;
            sort($sorted);
            $this->assertSame($labels, $sorted);
        }
    }

    public function test_remaining_enums_match_their_sources(): void
    {
        $this->assertSame(
            array_column(ChronicleEntryRole::cases(), 'value'),
            $this->enumValues($this->property(RecordType::ChronicleEntries, ['entities', 'role']))
        );
        $this->assertSame(
            ['derived', 'manual', 'ohm_import'],
            $this->enumValues($this->property(RecordType::GeometryPeriods, ['provenance_mode']))
        );
        $tag = $this->load(BundleFormat::schemaDir().'/common.schema.json')['$defs']['tag'];
        $this->assertSame(
            [TagSource::Manual->value, TagSource::Curated->value],
            $this->enumValues($tag['properties']['source'])
        );
        $this->assertSame(['merge', 'replace', 'delete'], $this->load(BundleFormat::schemaDir().'/common.schema.json')['$defs']['op']['enum']);
    }

    public function test_property_keys_match_record_type_keys_in_order(): void
    {
        foreach (RecordType::cases() as $type) {
            $keys = array_keys($this->load($type->schemaPath())['properties']);
            $this->assertSame([...$type->keys(), '_op'], $keys, $type->value);
        }
    }

    public function test_nested_item_keys_are_fixed(): void
    {
        $nested = [
            [RecordType::Entities, 'aliases', ['name', 'language', 'source', 'is_primary']],
            [RecordType::Entities, 'temporal_ranges', ['range_type', 'start_year', 'end_year', 'start_date', 'end_date', 'duration_type', 'date_method', 'date_confidence', 'is_primary', 'notes']],
            [RecordType::Entities, 'locations', ['location_name', 'location_method', 'location_confidence', 'is_primary', 'notes', 'geom', 'territory_geom']],
            [RecordType::ChronicleEntries, 'entities', ['entity_id', 'role', 'sequence_in_entry']],
        ];
        foreach ($nested as [$type, $key, $expected]) {
            $items = $this->load($type->schemaPath())['properties'][$key]['items'];
            $this->assertSame($expected, array_keys($items['properties']), $key);
            $this->assertFalse($items['additionalProperties'], $key);
        }
    }

    /** @return array<string, array<string, mixed>> minimal valid line per type */
    private function minimalLines(): array
    {
        return [
            'entities' => ['name' => 'Rome', 'entity_type' => 'political_entity'],
            'relationships' => ['source_entity_id' => self::UUID, 'target_entity_id' => self::UUID, 'relationship_type' => 'part_of'],
            'geometry_periods' => ['entity_id' => self::UUID, 'period_type' => 'territory', 'start_year' => -500, 'provenance_mode' => 'manual'],
            'geo_refs' => ['entity_id' => self::UUID, 'provider' => 'ohm', 'external_type' => 'relation', 'external_id' => '1', 'match_role' => 'primary', 'retrieval_method' => 'manual'],
            'chronicles' => ['title' => 'T', 'slug' => 't', 'source_type' => 'manual'],
            'chronicle_entries' => ['chronicle_id' => self::UUID, 'narrative_text' => 'Text'],
        ];
    }

    private function valid(RecordType $type, array $line): bool
    {
        return Schemas::validator()
            ->validate(json_decode(json_encode($line)), Schemas::recordSchemaId($type))
            ->isValid();
    }

    public function test_minimal_valid_line_passes_for_every_type(): void
    {
        foreach (RecordType::cases() as $type) {
            $line = $this->minimalLines()[$type->value];
            $this->assertTrue($this->valid($type, $line), $type->value);
            $this->assertTrue($this->valid($type, ['id' => self::UUID, ...$line]), $type->value.' with id');
            $this->assertTrue($this->valid($type, ['id' => self::UUID]), $type->value.' id only');
        }
    }

    public function test_unknown_keys_are_rejected(): void
    {
        foreach (RecordType::cases() as $type) {
            $line = ['id' => self::UUID, 'bogus' => 1];
            $this->assertFalse($this->valid($type, $line), $type->value);
        }
        $this->assertFalse($this->valid(RecordType::Entities, [
            'id' => self::UUID, 'aliases' => [['name' => 'x', 'bogus' => 1]],
        ]));
    }

    public function test_delete_requires_an_id(): void
    {
        foreach (RecordType::cases() as $type) {
            $this->assertFalse($this->valid($type, ['_op' => 'delete']), $type->value);
            $this->assertTrue($this->valid($type, ['_op' => 'delete', 'id' => self::UUID]), $type->value);
        }
    }

    public function test_new_records_need_their_creation_fields(): void
    {
        $creation = [
            'entities' => ['name', 'entity_type'],
            'relationships' => ['source_entity_id', 'target_entity_id', 'relationship_type'],
            'geometry_periods' => ['entity_id', 'period_type', 'start_year', 'provenance_mode'],
            'geo_refs' => ['entity_id', 'provider', 'external_type', 'external_id', 'match_role', 'retrieval_method'],
            'chronicles' => ['title', 'slug', 'source_type'],
            'chronicle_entries' => ['chronicle_id', 'narrative_text'],
        ];
        foreach (RecordType::cases() as $type) {
            $full = $this->minimalLines()[$type->value];
            $this->assertSame($creation[$type->value], array_keys($full), $type->value);
            foreach ($creation[$type->value] as $field) {
                $missing = $full;
                unset($missing[$field]);
                $this->assertFalse($this->valid($type, $missing), $type->value.' without '.$field);
            }
        }
    }

    public function test_value_rules(): void
    {
        $this->assertFalse($this->valid(RecordType::Entities, ['id' => 'NOT-A-UUID']));
        $this->assertFalse($this->valid(RecordType::Entities, ['id' => self::UUID, 'wikidata_id' => 'Q0']));
        $this->assertTrue($this->valid(RecordType::Entities, ['id' => self::UUID, 'wikidata_id' => null]));
        $this->assertTrue($this->valid(RecordType::Entities, ['id' => self::UUID, 'wikidata_id' => 'Q12']));
        $this->assertFalse($this->valid(RecordType::Entities, ['id' => self::UUID, 'entity_type' => 'nope']));
        $this->assertTrue($this->valid(RecordType::Entities, ['id' => self::UUID, 'confidence' => null]));
        $this->assertFalse($this->valid(RecordType::Entities, ['id' => self::UUID, 'verification_status' => null]));
        $this->assertFalse($this->valid(RecordType::GeometryPeriods, ['id' => self::UUID, 'start_year' => 3001]));
        $this->assertTrue($this->valid(RecordType::GeometryPeriods, ['id' => self::UUID, 'start_year' => -20000, 'end_year' => null]));
        $this->assertTrue($this->valid(RecordType::GeometryPeriods, [
            'id' => self::UUID, 'geom' => ['type' => 'Point', 'coordinates' => [1.5, 2.5]],
        ]));
        $this->assertFalse($this->valid(RecordType::GeometryPeriods, [
            'id' => self::UUID, 'geom' => ['type' => 'Circle', 'coordinates' => [1, 2]],
        ]));
        $this->assertTrue($this->valid(RecordType::Chronicles, ['id' => self::UUID, 'slug' => 'chavín-horizon-c-750330-bce']));
        $this->assertFalse($this->valid(RecordType::Chronicles, ['id' => self::UUID, 'slug' => 'Has Space']));
        $this->assertTrue($this->valid(RecordType::GeoRefs, ['id' => self::UUID, 'match_score' => 0.8731, 'external_tags' => (object) [], 'source_meta' => null]));
        $this->assertTrue($this->valid(RecordType::ChronicleEntries, ['id' => self::UUID, 'source_evidence' => 'event:0']));
        $this->assertTrue($this->valid(RecordType::Chronicles, ['id' => self::UUID, 'tags' => [['slug' => 'war', 'source' => 'manual']]]));
        $this->assertFalse($this->valid(RecordType::Chronicles, ['id' => self::UUID, 'tags' => [['slug' => 'war', 'source' => 'derived']]]));
    }

    /** @return array<string, mixed> */
    private static function validManifest(): array
    {
        return [
            'format' => BundleFormat::FORMAT,
            'version' => 1,
            'profile' => 'full',
            'exported_at' => '2026-10-18T10:00:00Z',
            'source' => 'history-mapped',
            'scope' => ['all'],
            'base' => 'export',
            'counts' => ['entities' => 3],
            'checksums' => ['_base/entities.jsonl' => 'sha256:'.str_repeat('a', 64)],
        ];
    }

    /** @param array<string, mixed> $manifest */
    private function manifestValid(array $manifest): bool
    {
        return Schemas::validator()
            ->validate(json_decode(json_encode($manifest)), Schemas::manifestSchemaId())->isValid();
    }

    /** @return array<string, array{0: string}> */
    public static function manifestKeys(): array
    {
        return array_combine(array_keys(self::validManifest()), array_map(fn ($k) => [$k], array_keys(self::validManifest())));
    }

    #[DataProvider('manifestKeys')]
    public function test_manifest_requires_every_key(string $key): void
    {
        $manifest = self::validManifest();
        $this->assertTrue($this->manifestValid($manifest));
        unset($manifest[$key]);
        $this->assertFalse($this->manifestValid($manifest));
    }

    public function test_manifest_schema(): void
    {
        $manifest = self::validManifest();

        $this->assertFalse($this->manifestValid([...$manifest, 'format' => 'other']));
        $this->assertFalse($this->manifestValid([...$manifest, 'extra' => 1]));
        $this->assertFalse($this->manifestValid([...$manifest, 'base' => 'whatever']));
        $this->assertTrue($this->manifestValid([...$manifest, 'base' => 'baseline:2026-q4']));
        $this->assertFalse($this->manifestValid([...$manifest, 'checksums' => ['_base/entities.jsonl' => 'md5:abc']]));
        $this->assertFalse($this->manifestValid([...$manifest, 'profile' => 'secret']));
    }

    public function test_manifest_counts_only_allow_record_stems(): void
    {
        $manifest = self::validManifest();
        $this->assertTrue($this->manifestValid([...$manifest, 'counts' => ['geo_refs' => 1, 'chronicle_entries' => 2]]));
        $this->assertFalse($this->manifestValid([...$manifest, 'counts' => ['widgets' => 1]]));
    }

    public function test_nested_items_require_their_not_null_columns(): void
    {
        $entity = ContentBundleFixtures::entity();
        $entry = ContentBundleFixtures::chronicleEntry();

        $noName = $entity;
        unset($noName['aliases'][0]['name']);
        $this->assertFalse($this->valid(RecordType::Entities, $noName));

        $noEntity = $entry;
        unset($noEntity['entities'][0]['entity_id']);
        $this->assertFalse($this->valid(RecordType::ChronicleEntries, $noEntity));

        $noSlug = ContentBundleFixtures::chronicle();
        unset($noSlug['tags'][0]['slug']);
        $this->assertFalse($this->valid(RecordType::Chronicles, $noSlug));
    }

    public function test_null_in_non_null_nested_field_is_rejected(): void
    {
        $entity = ContentBundleFixtures::entity();
        foreach ([['aliases', 'is_primary'], ['temporal_ranges', 'is_primary'], ['locations', 'is_primary'], ['temporal_ranges', 'range_type']] as [$list, $key]) {
            $bad = $entity;
            $bad[$list][0][$key] = null;
            $this->assertFalse($this->valid(RecordType::Entities, $bad), $list.'.'.$key);
        }
        $entry = ContentBundleFixtures::chronicleEntry();
        $entry['entities'][0]['role'] = null;
        $this->assertFalse($this->valid(RecordType::ChronicleEntries, $entry));
    }

    public function test_invalid_op_is_rejected(): void
    {
        foreach (RecordType::cases() as $type) {
            $this->assertFalse($this->valid($type, ['id' => self::UUID, '_op' => 'upsert']), $type->value);
            $this->assertTrue($this->valid($type, ['id' => self::UUID, '_op' => 'replace']), $type->value);
        }
    }

    public function test_validator_collects_all_errors(): void
    {
        $result = Schemas::validator()->validate(
            json_decode(json_encode(['id' => 'bad', 'bogus' => 1, 'entity_type' => 'nope'])),
            Schemas::recordSchemaId(RecordType::Entities)
        );
        $this->assertFalse($result->isValid());
        $this->assertGreaterThan(1, count((new ErrorFormatter)->formatFlat($result->error())));
    }

    public function test_nested_keys_match_schema_item_property_order(): void
    {
        foreach (RecordType::cases() as $type) {
            $schema = $this->load($type->schemaPath());
            $expected = [];
            foreach ($schema['properties'] as $key => $property) {
                if (($property['type'] ?? null) === 'array') {
                    $items = $property['items'];
                    $expected[$key] = isset($items['$ref'])
                        ? array_keys($this->load(BundleFormat::schemaDir().'/common.schema.json')['$defs']['tag']['properties'])
                        : array_keys($items['properties']);
                }
            }
            $this->assertSame($expected, $type->nestedKeys(), $type->value);
        }
    }

    public function test_record_type_helpers(): void
    {
        $this->assertSame(['entities', 'relationships', 'geometry_periods', 'geo_refs', 'chronicles', 'chronicle_entries'], array_column(RecordType::cases(), 'value'));
        $this->assertSame('geo_refs.jsonl', RecordType::GeoRefs->file());
        $this->assertSame(RecordType::GeoRefs, RecordType::fromFile('geo_refs.jsonl'));
        $this->assertNull(RecordType::fromFile('nope.jsonl'));
        $this->assertSame('entity_id', RecordType::Entities->primaryKey());
        $this->assertSame(Entity::class, RecordType::Entities->modelClass());
        $this->assertFileExists(RecordType::Chronicles->schemaPath());
    }
}
