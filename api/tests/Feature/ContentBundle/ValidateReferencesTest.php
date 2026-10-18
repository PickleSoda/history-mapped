<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Actions\ContentBundle\ExportContentBundleAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityLocation;
use App\Models\EntityRelationship;
use App\Models\GeometryPeriod;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\Scope\ExportScope;
use App\Support\ContentBundle\Validation\BundleValidator;
use App\Support\ContentBundle\Validation\ReferenceChecks;
use App\Support\ContentBundle\Validation\ValidationReport;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ValidateReferencesTest extends TestCase
{
    use RefreshDatabase;

    private const POINT = ['type' => 'Point', 'coordinates' => [12.4963655, 41.9027835]];

    private const POLYGON = ['type' => 'Polygon', 'coordinates' => [[[12.0, 41.0], [13.0, 41.0], [13.0, 42.0], [12.0, 41.0]]]];

    private const BOWTIE = ['type' => 'Polygon', 'coordinates' => [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]];

    private string $dir;

    private string $bundle;

    private string $a;

    private string $b;

    private string $rel;

    private string $period;

    private string $refA;

    private string $refB;

    private string $entry;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = sys_get_temp_dir().'/cb-ref-'.bin2hex(random_bytes(6));
        mkdir($this->dir);

        $a = Entity::factory()->create(['wikidata_id' => null]);
        $b = Entity::factory()->create(['wikidata_id' => null]);
        $this->a = $a->entity_id;
        $this->b = $b->entity_id;
        DB::table('entity_aliases')->insert(['entity_id' => $this->a, 'name' => 'Alias', 'language' => 'en', 'is_primary' => false]);
        EntityLocation::query()->forceCreate(['entity_id' => $this->a, 'location_name' => 'Rome', 'geom' => self::POINT, 'territory_geom' => self::POLYGON, 'is_primary' => true]);
        $this->rel = EntityRelationship::query()->create(['relationship_id' => (string) Str::uuid(), 'source_entity_id' => $this->a, 'target_entity_id' => $this->b, 'relationship_type' => 'allied_with'])->relationship_id;
        $this->period = GeometryPeriod::query()->forceCreate([
            'geometry_period_id' => (string) Str::uuid(), 'entity_id' => $this->a, 'period_type' => 'presence',
            'start_year' => -500, 'end_year' => -27, 'provenance_mode' => 'derived', 'relationship_id' => $this->rel,
            'source_event_id' => $this->b, 'geom' => self::POINT, 'territory_geom' => self::POLYGON,
        ])->geometry_period_id;
        $this->refA = EntityGeoRef::factory()->create(['entity_id' => $this->a, 'geometry_period_id' => $this->period])->geo_ref_id;
        $this->refB = EntityGeoRef::factory()->create(['entity_id' => $this->b])->geo_ref_id;
        DB::table('entities')->where('entity_id', $this->a)->update(['primary_geo_ref_id' => $this->refA]);
        $c = Chronicle::factory()->create(['slug' => 'rome']);
        $this->entry = ChronicleEntry::factory()->create(['chronicle_id' => $c->chronicle_id, 'sequence_order' => 1, 'primary_relationship_id' => $this->rel])->entry_id;
        DB::table('chronicle_entry_entities')->insert(['entry_id' => $this->entry, 'entity_id' => $this->a, 'role' => 'participant', 'sequence_in_entry' => 1]);

        $this->bundle = $this->dir.'/b';
        app(ExportContentBundleAction::class)($this->bundle, ExportScope::parse([]), Profile::Full);
    }

    protected function tearDown(): void
    {
        exec('rm -rf '.escapeshellarg($this->dir));
        parent::tearDown();
    }

    private function validate(bool $site = false): ValidationReport
    {
        return BundleValidator::validatePath($this->bundle, $site);
    }

    /** @return list<string> */
    private function strings(ValidationReport $r): array
    {
        return array_map('strval', $r->issues());
    }

    /** @return list<array<string, mixed>> */
    private function read(string $file): array
    {
        return array_map(fn ($l) => json_decode($l, true), explode("\n", rtrim((string) file_get_contents($this->bundle.'/'.$file), "\n")));
    }

    /** @param  list<array<string, mixed>>  $rows */
    private function write(string $file, array $rows): void
    {
        file_put_contents($this->bundle.'/'.$file, implode("\n", array_map('json_encode', $rows))."\n");
    }

    /** @param  callable(array<string, mixed>): array<string, mixed>  $fn applied to the row with the given id */
    private function edit(string $file, string $id, callable $fn): void
    {
        $this->write($file, array_map(fn ($r) => $r['id'] === $id ? $fn($r) : $r, $this->read($file)));
    }

    /** @param  array<string, mixed>  $row */
    private function append(string $file, array $row): void
    {
        $this->write($file, [...$this->read($file), $row]);
    }

    private function rebase(string $file): void
    {
        copy($this->bundle.'/'.$file, $this->bundle.'/_base/'.$file);
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/'.$file] = 'sha256:'.hash_file('sha256', $this->bundle.'/_base/'.$file);
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
    }

    /** 1-based line of the row with this id (rows are sorted by id, so it is not fixed). */
    private function lineOf(string $file, string $id): int
    {
        foreach ($this->read($file) as $i => $row) {
            if ($row['id'] === $id) {
                return $i + 1;
            }
        }
        $this->fail("no {$id} in {$file}");
    }

    public function test_round_trip_validates_with_no_issues_against_the_site(): void
    {
        $this->assertSame([], $this->strings($this->validate(true)));
        $this->assertSame([], $this->strings($this->validate(false)));
    }

    public function test_dangling_reference_is_one_summary_warning_without_the_site(): void
    {
        $ghost = (string) Str::uuid();
        $this->edit('relationships.jsonl', $this->rel, fn ($r) => [...$r, 'target_entity_id' => $ghost]);
        $this->append('relationships.jsonl', [...$this->read('relationships.jsonl')[0], 'id' => (string) Str::uuid(), 'start_year' => 1, 'target_entity_id' => (string) Str::uuid()]);

        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertSame(
            ['relationships.jsonl: /target_entity_id: 2 references in `target_entity_id` point outside the bundle (first on line 1); they must exist on the site at import (run with --against-site to check them)'],
            $this->strings($r),
        );
        $this->assertNull($r->issues()[0]->line);
        $this->assertSame(1, $r->warningCount());
    }

    public function test_dangling_reference_is_an_error_against_the_site_unless_the_record_exists_there(): void
    {
        $ghost = (string) Str::uuid();
        $this->edit('relationships.jsonl', $this->rel, fn ($r) => [...$r, 'target_entity_id' => $ghost]);

        $r = $this->validate(true);
        $this->assertSame(["relationships.jsonl:1: /target_entity_id: references entities {$ghost}, which is neither in the bundle nor on the site"], $this->strings($r));
        $this->assertSame($this->rel, $r->issues()[0]->id);

        $site = Entity::factory()->create(['entity_id' => $ghost, 'wikidata_id' => null]);
        $this->assertSame([], $this->strings($this->validate(true)));
        $this->assertSame($ghost, $site->entity_id);
    }

    public function test_reference_to_an_id_the_bundle_deletes_is_an_error(): void
    {
        $this->append('entities.jsonl', ['id' => $this->b, '_op' => 'delete']);
        $this->write('entities.jsonl', array_values(array_filter($this->read('entities.jsonl'), fn ($r) => $r['id'] !== $this->b || ($r['_op'] ?? null) === 'delete')));

        $r = $this->validate();
        $this->assertContains("relationships.jsonl:1: /target_entity_id: references entities {$this->b}, which this bundle deletes", $this->strings($r));
        $this->assertContains("geometry_periods.jsonl:1: /source_event_id: references entities {$this->b}, which this bundle deletes", $this->strings($r));
    }

    public function test_cross_file_issue_downgrades_only_when_every_involved_line_is_unchanged(): void
    {
        // The entity points at a geo ref owned by another entity; both lines are rebased so both are "unchanged".
        $this->edit('entities.jsonl', $this->a, fn ($r) => [...$r, 'primary_geo_ref_id' => $this->refB]);
        $this->rebase('entities.jsonl');
        $expected = 'entities.jsonl:'.$this->lineOf('entities.jsonl', $this->a).": /primary_geo_ref_id: references geo_refs {$this->refB}, which belongs to entity {$this->b}, not entity {$this->a}";

        $r = $this->validate();
        $this->assertSame([$expected.' (unchanged since export)'], $this->strings($r));
        $this->assertTrue($r->isValid());

        // Editing the geo ref line it points at makes the error real again.
        $this->edit('geo_refs.jsonl', $this->refB, fn ($x) => [...$x, 'match_score' => 0.5]);
        $this->assertSame([$expected], $this->strings($this->validate()));
    }

    public function test_geo_ref_geometry_period_must_belong_to_the_same_entity(): void
    {
        $this->edit('geo_refs.jsonl', $this->refB, fn ($r) => [...$r, 'geometry_period_id' => $this->period]);
        $this->assertSame(
            ['geo_refs.jsonl:'.$this->lineOf('geo_refs.jsonl', $this->refB).": /geometry_period_id: references geometry_periods {$this->period}, which belongs to entity {$this->a}, not entity {$this->b}"],
            $this->strings($this->validate()),
        );
    }

    public function test_same_owner_is_checked_against_the_site_row_when_the_bundle_line_does_not_say(): void
    {
        $this->write('entities.jsonl', [['id' => $this->b, 'primary_geo_ref_id' => $this->refA]]);
        $this->write('geo_refs.jsonl', [['id' => $this->refA, 'is_active' => true]]);
        $this->assertTrue($this->validate()->isValid());
        $r = $this->validate(true);
        $this->assertSame(["entities.jsonl:1: /primary_geo_ref_id: references geo_refs {$this->refA}, which belongs to entity {$this->a}, not entity {$this->b}"], array_map('strval', $r->errors()));
    }

    public function test_deleting_an_entity_that_a_site_relationship_still_references(): void
    {
        $z = Entity::factory()->create(['wikidata_id' => null])->entity_id;
        $rz = EntityRelationship::query()->create(['relationship_id' => (string) Str::uuid(), 'source_entity_id' => $this->a, 'target_entity_id' => $z, 'relationship_type' => 'allied_with'])->relationship_id;
        $this->append('entities.jsonl', ['id' => $z, '_op' => 'delete']);
        $line = count($this->read('entities.jsonl'));

        $this->assertSame([], $this->strings($this->validate()));
        $r = $this->validate(true);
        $this->assertSame(["entities.jsonl:{$line}: /id: 1 site records still reference it (e.g. relationships {$rz}); delete or re-point them in this bundle"], $this->strings($r));
        $this->assertSame($z, $r->issues()[0]->id);

        // Deleting the relationship in the bundle excuses it.
        $this->append('relationships.jsonl', ['id' => $rz, '_op' => 'delete']);
        $this->assertSame([], $this->strings($this->validate(true)));

        // So does re-pointing it.
        $this->write('relationships.jsonl', array_slice($this->read('relationships.jsonl'), 0, 1));
        $this->append('relationships.jsonl', ['id' => $rz, 'target_entity_id' => $this->b]);
        $this->assertSame([], $this->strings($this->validate(true)));

        // A merge line that leaves the field alone does not.
        $this->write('relationships.jsonl', array_slice($this->read('relationships.jsonl'), 0, 1));
        $this->append('relationships.jsonl', ['id' => $rz, 'description' => 'x']);
        $this->assertCount(1, $this->validate(true)->errors());
    }

    public function test_deleted_entity_in_a_chronicle_entry_is_excused_when_the_entry_drops_it(): void
    {
        $z = Entity::factory()->create(['wikidata_id' => null])->entity_id;
        DB::table('chronicle_entry_entities')->insert(['entry_id' => $this->entry, 'entity_id' => $z, 'role' => 'participant', 'sequence_in_entry' => 2]);
        $this->append('entities.jsonl', ['id' => $z, '_op' => 'delete']);
        $line = count($this->read('entities.jsonl'));

        // The entry line is unchanged from the export, whose entities list predates this site row, so it drops z.
        $this->assertSame([], $this->strings($this->validate(true)));

        $this->edit('chronicle_entries.jsonl', $this->entry, function ($e) {
            unset($e['entities']);

            return $e;
        });
        $r = $this->validate(true);
        $this->assertSame(["entities.jsonl:{$line}: /id: 1 site records still reference it (e.g. chronicle_entries {$this->entry}); delete or re-point them in this bundle"], $this->strings($r));

        $this->edit('chronicle_entries.jsonl', $this->entry, fn ($e) => [...$e, 'entities' => [['entity_id' => $this->a, 'role' => 'participant', 'sequence_in_entry' => 1]]]);
        $this->assertSame([], $this->strings($this->validate(true)));
    }

    public function test_site_lookups_are_batched(): void
    {
        $rows = $this->read('relationships.jsonl');
        $template = $rows[0];
        $lines = [];
        for ($i = 0; $i < 1500; $i++) {
            $lines[] = [...$template, 'id' => (string) Str::uuid(), 'target_entity_id' => (string) Str::uuid(), 'start_year' => $i, 'end_year' => $i + 1];
        }
        $this->write('relationships.jsonl', $lines);

        DB::enableQueryLog();
        $r = $this->validate(true);
        $lookups = array_filter(DB::getQueryLog(), fn ($q) => str_contains($q['query'], 'any(') && str_contains($q['query'], 'from "entities"'));
        DB::disableQueryLog();

        $this->assertCount(2, $lookups);
        $this->assertSame(1500, $r->errorCount());
    }

    public function test_invalid_geometry_reports_the_postgis_reason_only_against_the_site(): void
    {
        $this->edit('geometry_periods.jsonl', $this->period, fn ($r) => [...$r, 'territory_geom' => self::BOWTIE]);

        $this->assertSame([], $this->strings($this->validate()));
        $r = $this->validate(true);
        $this->assertCount(1, $r->errors());
        $this->assertStringStartsWith('geometry_periods.jsonl:1: /territory_geom: invalid geometry: Self-intersection', (string) $r->issues()[0]);
    }

    public function test_invalid_location_geometry_has_an_indexed_pointer(): void
    {
        $this->edit('entities.jsonl', $this->a, function ($r) {
            $r['locations'][0]['territory_geom'] = self::BOWTIE;

            return $r;
        });
        $this->assertStringStartsWith('entities.jsonl:'.$this->lineOf('entities.jsonl', $this->a).': /locations/0/territory_geom: invalid geometry: Self-intersection', (string) $this->validate(true)->issues()[0]);
    }

    public function test_unreadable_geojson_in_a_batch_is_found_without_poisoning_the_transaction(): void
    {
        $lines = [];
        for ($i = 0; $i < 10; $i++) {
            $lines[] = ['id' => (string) Str::uuid(), 'geom' => $i === 6 ? ['type' => 'Nope', 'coordinates' => []] : self::POINT];
        }
        $this->write('geometry_periods.jsonl', $lines);

        // Run the references layer alone so the structure schema does not reject the bad geometry first.
        $r = (new BundleValidator([new ReferenceChecks]))->validate(BundleReader::open($this->bundle), true);
        $this->assertCount(1, $r->errors());
        $this->assertStringStartsWith('geometry_periods.jsonl:7: /geom: unreadable GeoJSON: ', (string) $r->errors()[0]);
        $this->assertSame(1, DB::selectOne('select 1 as x')->x);
    }

    public function test_command_text_output_and_exit_codes(): void
    {
        $this->artisan('content:validate', ['path' => $this->bundle, '--against-site' => true])
            ->expectsOutput('0 errors, 0 warnings')
            ->assertExitCode(0);

        $ghost = (string) Str::uuid();
        $this->edit('relationships.jsonl', $this->rel, fn ($r) => [...$r, 'target_entity_id' => $ghost]);
        $this->artisan('content:validate', ['path' => $this->bundle, '--against-site' => true])
            ->expectsOutput("ERROR relationships.jsonl:1: /target_entity_id: references entities {$ghost}, which is neither in the bundle nor on the site")
            ->expectsOutput('1 errors, 0 warnings')
            ->assertExitCode(1);

        $this->artisan('content:validate', ['path' => $this->bundle])
            ->expectsOutputToContain('WARN relationships.jsonl: /target_entity_id: 1 references')
            ->expectsOutput('0 errors, 1 warnings')
            ->assertExitCode(0);
    }

    public function test_command_marks_unchanged_lines(): void
    {
        $this->edit('entities.jsonl', $this->a, fn ($r) => [...$r, 'primary_geo_ref_id' => $this->refB]);
        $this->rebase('entities.jsonl');
        $exit = Artisan::call('content:validate', ['path' => $this->bundle]);
        $this->assertSame(0, $exit);
        $this->assertMatchesRegularExpression('/^WARN entities\.jsonl:\d+: \/primary_geo_ref_id: .* \(unchanged since export\)$/m', Artisan::output());
    }

    public function test_command_on_a_missing_path_is_a_package_error(): void
    {
        $this->artisan('content:validate', ['path' => $this->dir.'/nope'])->assertExitCode(1);
    }

    public function test_command_json_is_the_report_and_nothing_else(): void
    {
        $this->edit('entities.jsonl', $this->a, fn ($r) => [...$r, 'primary_geo_ref_id' => (string) Str::uuid()]);
        $exit = Artisan::call('content:validate', ['path' => $this->bundle, '--json' => true, '--against-site' => true]);
        $json = json_decode(Artisan::output(), true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame(1, $exit);
        $this->assertSame(['valid', 'errors', 'warnings', 'issues'], array_keys($json));
        $this->assertFalse($json['valid']);
        $this->assertSame(1, $json['errors']);
        $this->assertSame('references', $json['issues'][0]['layer']);
    }
}
