<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Actions\ContentBundle\ExportContentBundleAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\RecordType;
use App\Support\ContentBundle\Schemas;
use App\Support\ContentBundle\Scope\ExportScope;
use App\Support\ContentBundle\Serializers\RecordSerializer;
use App\Support\ContentBundle\Serializers\RelationshipSerializer;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\TestCase;

class ContentExportCommandTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    private string $e1;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = sys_get_temp_dir().'/cb-exp-'.bin2hex(random_bytes(6));
        mkdir($this->dir);

        $a = Entity::factory()->create(['wikidata_id' => null, 'attributes' => ['kept' => 1, '_internal' => 'secret']]);
        $b = Entity::factory()->create(['wikidata_id' => null]);
        $this->e1 = $a->entity_id;
        DB::table('entity_aliases')->insert(['entity_id' => $a->entity_id, 'name' => 'Alias', 'language' => 'en', 'is_primary' => false]);
        DB::table('entity_temporal_ranges')->insert(['entity_id' => $a->entity_id, 'range_type' => 'primary', 'start_date' => '-500', 'end_date' => '-400', 'is_primary' => true]);
        $rel = EntityRelationship::query()->create(['relationship_id' => (string) Str::uuid(), 'source_entity_id' => $a->entity_id, 'target_entity_id' => $b->entity_id, 'relationship_type' => 'allied_with']);
        GeometryPeriod::query()->forceCreate([
            'geometry_period_id' => (string) Str::uuid(), 'entity_id' => $a->entity_id, 'period_type' => 'territory', 'start_year' => -500, 'end_year' => -400,
            'confidence' => 'high', 'provenance_mode' => 'manual', 'geom' => ['type' => 'Polygon', 'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 41.0]]]],
        ]);
        EntityGeoRef::factory()->create(['entity_id' => $a->entity_id]);
        $c = Chronicle::factory()->create(['slug' => 'rome']);
        Chronicle::factory()->create(['slug' => 'other']);
        foreach ([1, 2] as $i) {
            ChronicleEntry::factory()->create(['chronicle_id' => $c->chronicle_id, 'sequence_order' => $i, 'primary_relationship_id' => $i === 1 ? $rel->relationship_id : null]);
        }
    }

    protected function tearDown(): void
    {
        exec('rm -rf '.escapeshellarg($this->dir));
        parent::tearDown();
    }

    public function test_exports_seeded_dataset_with_valid_lines(): void
    {
        $this->artisan('content:export', ['path' => $this->dir.'/out.zip'])->assertExitCode(0);

        $r = BundleReader::open($this->dir.'/out.zip');
        $this->assertSame(['entities' => 2, 'relationships' => 1, 'geometry_periods' => 1, 'geo_refs' => 1, 'chronicles' => 2, 'chronicle_entries' => 2], $r->manifest()['counts']);
        $this->assertSame(['all'], $r->manifest()['scope']);
        foreach (RecordType::cases() as $type) {
            $n = 0;
            foreach ($r->lines($type->file()) as $line) {
                $n++;
                $result = Schemas::validator()->validate(json_decode($line), Schemas::recordSchemaId($type));
                $this->assertTrue($result->isValid(), $type->value.' line '.$n);
            }
            $this->assertSame($r->manifest()['counts'][$type->value], $n);
            $this->assertSame($r->manifest()['checksums']['_base/'.$type->file()], $r->sha256('_base/'.$type->file()));
        }
        $this->assertFalse($r->has('LICENSE.md'));
        $this->assertStringContainsString('_internal', implode("\n", iterator_to_array($r->lines('entities.jsonl'))));
    }

    public function test_output_is_deterministic_even_when_nested_rows_are_inserted_in_another_order(): void
    {
        $insert = fn (string $name) => DB::table('entity_aliases')->insert(['alias_id' => (string) Str::uuid(), 'entity_id' => $this->e1, 'name' => $name, 'language' => 'en', 'is_primary' => false]);
        DB::table('entity_aliases')->where('entity_id', $this->e1)->delete();
        $insert('Zed');
        $insert('Alpha');
        $action = app(ExportContentBundleAction::class);
        $action($this->dir.'/a', ExportScope::parse([]), Profile::Full);

        DB::table('entity_aliases')->where('entity_id', $this->e1)->delete();
        $insert('Alpha');
        $insert('Zed');
        $action($this->dir.'/b', ExportScope::parse([]), Profile::Full);

        foreach (RecordType::cases() as $type) {
            $this->assertSame(file_get_contents($this->dir.'/a/'.$type->file()), file_get_contents($this->dir.'/b/'.$type->file()));
            $this->assertSame(file_get_contents($this->dir.'/a/'.$type->file()), file_get_contents($this->dir.'/a/_base/'.$type->file()));
        }
    }

    public function test_public_profile_adds_license_and_strips_internal_attributes(): void
    {
        $this->artisan('content:export', ['path' => $this->dir.'/pub', '--profile' => 'public', '--source' => 'unit'])->assertExitCode(0);
        $this->assertFileExists($this->dir.'/pub/LICENSE.md');
        $this->assertStringNotContainsString('_internal', file_get_contents($this->dir.'/pub/entities.jsonl'));
        $this->assertSame('unit', BundleReader::open($this->dir.'/pub')->manifest()['source']);
    }

    public function test_chronicle_scope_exports_only_the_closure(): void
    {
        $this->artisan('content:export', ['path' => $this->dir.'/c', '--scope' => ['chronicle:rome']])->assertExitCode(0);
        $counts = BundleReader::open($this->dir.'/c')->manifest()['counts'];
        $this->assertSame(1, $counts['chronicles']);
        $this->assertSame(2, $counts['chronicle_entries']);
        $this->assertSame(2, $counts['entities']);
        $this->assertSame(1, $counts['geometry_periods']);
        $this->assertSame(1, $counts['geo_refs']);
        $this->assertSame(1, $counts['relationships']);
    }

    public function test_invalid_scope_and_profile_exit_one(): void
    {
        $this->artisan('content:export', ['path' => $this->dir.'/x', '--scope' => ['bogus:1']])->assertExitCode(1);
        $this->artisan('content:export', ['path' => $this->dir.'/x', '--profile' => 'secret'])->assertExitCode(1);
        $this->assertDirectoryDoesNotExist($this->dir.'/x');
    }

    public function test_non_empty_target_exits_one_without_writing(): void
    {
        file_put_contents($this->dir.'/keep', 'x');
        $this->artisan('content:export', ['path' => $this->dir])->assertExitCode(1);
        $this->assertSame(['keep'], array_values(array_diff(scandir($this->dir), ['.', '..'])));
    }

    public function test_empty_selection_warns_but_succeeds(): void
    {
        $this->artisan('content:export', ['path' => $this->dir.'/none', '--scope' => ['chronicle:nope']])
            ->expectsOutputToContain('scope selected no entities')
            ->assertExitCode(0);
    }

    public function test_all_scope_on_empty_selection_does_not_warn(): void
    {
        DB::table('chronicles')->delete();
        DB::table('entities')->delete();
        $this->artisan('content:export', ['path' => $this->dir.'/empty'])->doesntExpectOutputToContain('scope selected no entities')->assertExitCode(0);
    }

    public function test_failure_midway_leaves_no_temp_dir_and_no_zip(): void
    {
        $before = glob(storage_path('app/tmp/bundle-*')) ?: [];
        $real = app(RelationshipSerializer::class);
        $this->app->bind(RelationshipSerializer::class, fn () => new class($real) implements RecordSerializer
        {
            public function __construct(private RelationshipSerializer $inner) {}

            public function type(): RecordType
            {
                return $this->inner->type();
            }

            public function query(): Builder
            {
                return $this->inner->query();
            }

            public function serialize(Model $model, Profile $profile): array
            {
                throw new RuntimeException('serializer failed');
            }
        });

        try {
            app(ExportContentBundleAction::class)($this->dir.'/f.zip', ExportScope::parse([]), Profile::Full);
            $this->fail('expected exception');
        } catch (RuntimeException $e) {
            $this->assertSame('serializer failed', $e->getMessage());
        }
        $this->assertFileDoesNotExist($this->dir.'/f.zip');
        $this->assertSame($before, glob(storage_path('app/tmp/bundle-*')) ?: []);
    }
}
