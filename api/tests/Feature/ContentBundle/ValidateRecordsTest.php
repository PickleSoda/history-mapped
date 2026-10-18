<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Actions\ContentBundle\ExportContentBundleAction;
use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use App\Models\EntityGeoRef;
use App\Models\EntityRelationship;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\Profile;
use App\Support\ContentBundle\Scope\ExportScope;
use App\Support\ContentBundle\Validation\BundleValidator;
use App\Support\ContentBundle\Validation\Issue;
use App\Support\ContentBundle\Validation\PackageChecks;
use App\Support\ContentBundle\Validation\RecordChecks;
use App\Support\ContentBundle\Validation\StructureChecks;
use App\Support\ContentBundle\Validation\ValidationReport;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

class ValidateRecordsTest extends TestCase
{
    use RefreshDatabase;

    private const GEOM = ['type' => 'Point', 'coordinates' => [1, 2]];

    private string $dir;

    private string $bundle;

    private string $a;

    private string $b;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = sys_get_temp_dir().'/cb-rec-'.bin2hex(random_bytes(6));
        mkdir($this->dir);

        $a = Entity::factory()->create(['wikidata_id' => null]);
        $b = Entity::factory()->create(['wikidata_id' => null]);
        $this->a = $a->entity_id;
        $this->b = $b->entity_id;
        DB::table('entity_aliases')->insert(['entity_id' => $a->entity_id, 'name' => 'Alias', 'language' => 'en', 'is_primary' => false]);
        $rel = EntityRelationship::query()->create(['relationship_id' => (string) Str::uuid(), 'source_entity_id' => $a->entity_id, 'target_entity_id' => $b->entity_id, 'relationship_type' => 'allied_with']);
        EntityGeoRef::factory()->create(['entity_id' => $a->entity_id]);
        $c = Chronicle::factory()->create(['slug' => 'rome', 'metadata' => ['k' => 'v']]);
        ChronicleEntry::factory()->create(['chronicle_id' => $c->chronicle_id, 'sequence_order' => 1, 'primary_relationship_id' => $rel->relationship_id]);

        $this->bundle = $this->dir.'/b';
        app(ExportContentBundleAction::class)($this->bundle, ExportScope::parse([]), Profile::Full);
    }

    protected function tearDown(): void
    {
        exec('rm -rf '.escapeshellarg($this->dir));
        parent::tearDown();
    }

    private function validate(): ValidationReport
    {
        return BundleValidator::validatePath($this->bundle);
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

    /** @param  list<array<string, mixed>|string>  $rows */
    private function write(string $file, array $rows): void
    {
        file_put_contents($this->bundle.'/'.$file, implode("\n", array_map(fn ($r) => is_string($r) ? $r : json_encode($r), $rows))."\n");
    }

    /** @param  callable(array<string, mixed>): array<int, array<string, mixed>|string>  $fn applied to the first row, returns rows replacing it */
    private function editFirst(string $file, callable $fn): void
    {
        $rows = $this->read($file);
        $this->write($file, [...$fn($rows[0]), ...array_slice($rows, 1)]);
    }

    private function restore(string $file): void
    {
        copy($this->bundle.'/_base/'.$file, $this->bundle.'/'.$file);
    }

    private function rebase(string $file): void
    {
        copy($this->bundle.'/'.$file, $this->bundle.'/_base/'.$file);
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/'.$file] = 'sha256:'.hash_file('sha256', $this->bundle.'/_base/'.$file);
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
    }

    public function test_real_export_has_no_record_issues(): void
    {
        $this->assertSame([], $this->strings($this->validate()));
    }

    public function test_duplicate_id_names_both_lines(): void
    {
        $this->editFirst('chronicles.jsonl', fn ($r) => [$r, [...$r, 'slug' => 'other']]);
        $r = $this->validate();
        $id = $this->read('chronicles.jsonl')[0]['id'];
        $this->assertSame(["chronicles.jsonl:2: /id: duplicate id `{$id}`: also on line 1"], $this->strings($r));
        $this->assertSame($id, $r->issues()[0]->id);
    }

    public function test_duplicate_id_counts_delete_lines_too(): void
    {
        $this->editFirst('chronicles.jsonl', fn ($r) => [$r, ['id' => $r['id'], '_op' => 'delete']]);
        $this->assertCount(1, $this->validate()->errors());
    }

    public function test_duplicate_relationship_considers_years_and_skips_deleted_lines(): void
    {
        $this->editFirst('relationships.jsonl', fn ($r) => [$r, [...$r, 'id' => (string) Str::uuid()]]);
        $this->assertSame(['relationships.jsonl:2: /relationship_type: duplicate relationship: also on line 1'], $this->strings($this->validate()));

        // Same triple with different years is a second reign, not a duplicate.
        $this->editFirst('relationships.jsonl', fn ($r) => [[...$r, 'start_year' => 100, 'end_year' => 200], [...$r, 'id' => (string) Str::uuid(), 'start_year' => 300, 'end_year' => 400]]);
        $this->assertSame([], $this->strings($this->validate()));

        // A delete line is not a duplicate.
        $this->editFirst('relationships.jsonl', fn ($r) => [$r, ['id' => (string) Str::uuid(), '_op' => 'delete']]);
        $this->assertSame([], $this->strings($this->validate()));
    }

    public function test_duplicate_chronicle_slug(): void
    {
        $this->editFirst('chronicles.jsonl', fn ($r) => [$r, [...$r, 'id' => (string) Str::uuid()]]);
        $this->assertSame(['chronicles.jsonl:2: /slug: duplicate chronicle slug "rome": also on line 1'], $this->strings($this->validate()));

        $this->restore('chronicles.jsonl');
        $this->editFirst('chronicles.jsonl', fn ($r) => [$r, ['id' => (string) Str::uuid(), '_op' => 'delete']]);
        $this->assertSame([], $this->strings($this->validate()));
    }

    public function test_duplicate_wikidata_id_is_a_warning(): void
    {
        $this->editFirst('entities.jsonl', fn ($r) => [[...$r, 'wikidata_id' => 'Q42'], [...$r, 'id' => (string) Str::uuid(), 'wikidata_id' => 'Q42']]);
        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertSame(['entities.jsonl:2: /wikidata_id: duplicate wikidata_id Q42: also on line 1'], $this->strings($r));
        $this->assertSame(Issue::WARNING, $r->issues()[0]->severity);
    }

    public function test_year_order_for_every_pair(): void
    {
        $cases = [
            ['relationships.jsonl', ['start_year' => 500, 'end_year' => 400], '/start_year'],
            ['geo_refs.jsonl', ['temporal_start_year' => 500, 'temporal_end_year' => 400], '/temporal_start_year'],
            ['chronicles.jsonl', ['start_year' => 500, 'end_year' => 400], '/start_year'],
            ['chronicle_entries.jsonl', ['start_year' => 500, 'end_year' => 400], '/start_year'],
        ];
        foreach ($cases as [$file, $patch, $field]) {
            $this->editFirst($file, fn ($r) => [[...$r, ...$patch]]);
            $this->assertSame(["{$file}:1: {$field}: `".array_key_first($patch).'` 500 is after `'.array_key_last($patch).'` 400'], $this->strings($this->validate()), $file);
            $this->restore($file);
        }
    }

    public function test_geometry_period_year_order(): void
    {
        $this->write('geometry_periods.jsonl', [['id' => (string) Str::uuid(), 'entity_id' => $this->a, 'period_type' => 'territory', 'start_year' => 500, 'end_year' => 400, 'provenance_mode' => 'manual', 'geom' => self::GEOM]]);
        $this->assertSame(['geometry_periods.jsonl:1: /start_year: `start_year` 500 is after `end_year` 400'], $this->strings($this->validate()));
    }

    public function test_nested_temporal_range_year_pair_has_an_indexed_pointer(): void
    {
        $this->editFirst('entities.jsonl', fn ($r) => [[...$r, 'temporal_ranges' => [
            ['range_type' => 'existence', 'start_year' => 1, 'end_year' => 2],
            ['range_type' => 'rule', 'start_year' => 20, 'end_year' => 10],
        ]]]);
        $this->assertSame(['entities.jsonl:1: /temporal_ranges/1/start_year: `start_year` 20 is after `end_year` 10'], $this->strings($this->validate()));
    }

    public function test_text_year_sign_slip_and_other_mismatch(): void
    {
        $this->editFirst('relationships.jsonl', fn ($r) => [[...$r, 'temporal_start' => '-0331', 'start_year' => 331, 'temporal_end' => '200 CE', 'end_year' => 400]]);
        $this->assertSame([
            'relationships.jsonl:1: /temporal_start: BCE/CE sign mismatch: `temporal_start` "-0331" reads as -331, but `start_year` is 331',
            'relationships.jsonl:1: /temporal_end: `temporal_end` "200 CE" reads as 200, but `end_year` is 400',
        ], $this->strings($this->validate()));
    }

    public function test_text_year_pairs_for_geo_refs_and_temporal_ranges(): void
    {
        $this->editFirst('geo_refs.jsonl', fn ($r) => [[...$r, 'temporal_start' => '-100', 'temporal_start_year' => -100, 'temporal_end' => '-12', 'temporal_end_year' => 12]]);
        $this->assertSame(['geo_refs.jsonl:1: /temporal_end: BCE/CE sign mismatch: `temporal_end` "-12" reads as -12, but `temporal_end_year` is 12'], $this->strings($this->validate()));
        $this->restore('geo_refs.jsonl');

        $this->editFirst('entities.jsonl', fn ($r) => [[...$r, 'temporal_ranges' => [['range_type' => 'existence', 'start_date' => '-0044-03-15', 'start_year' => 44]]]]);
        $this->assertSame(['entities.jsonl:1: /temporal_ranges/0/start_date: BCE/CE sign mismatch: `start_date` "-0044-03-15" reads as -44, but `start_year` is 44'], $this->strings($this->validate()));

        // Matching values, and text without a leading number, are fine.
        $this->editFirst('entities.jsonl', fn ($r) => [[...$r, 'temporal_ranges' => [['range_type' => 'existence', 'start_date' => '-0044-03-15', 'start_year' => -44, 'end_date' => 'c. 30 BCE', 'end_year' => -30]]]]);
        $this->assertSame([], $this->strings($this->validate()));
    }

    /** A new-record line: no `id`. */
    private function period(array $extra): array
    {
        return ['entity_id' => $this->a, 'period_type' => 'territory', 'start_year' => 1, 'provenance_mode' => 'manual', ...$extra];
    }

    public function test_check_constraints_on_new_and_replace_lines(): void
    {
        // gp_has_geometry
        $this->write('geometry_periods.jsonl', [$this->period([])]);
        $this->assertSame(['geometry_periods.jsonl:1: /geom: a geometry period needs `geom` or `territory_geom`'], $this->strings($this->validate()));

        $this->write('geometry_periods.jsonl', [['id' => (string) Str::uuid(), '_op' => 'replace', ...$this->period(['territory_geom' => self::GEOM])]]);
        $this->assertSame([], $this->strings($this->validate()));

        // gp_derived_requires_source
        $this->write('geometry_periods.jsonl', [$this->period(['geom' => self::GEOM, 'provenance_mode' => 'derived'])]);
        $this->assertSame(['geometry_periods.jsonl:1: /provenance_mode: a derived geometry period needs `relationship_id` or `source_event_id`'], $this->strings($this->validate()));
        $this->write('geometry_periods.jsonl', [$this->period(['geom' => self::GEOM, 'provenance_mode' => 'derived', 'source_event_id' => $this->b])]);
        $this->assertSame([], $this->strings($this->validate()));

        // gp_presence_requires_relationship
        $this->write('geometry_periods.jsonl', [$this->period(['geom' => self::GEOM, 'period_type' => 'presence'])]);
        $this->assertSame(['geometry_periods.jsonl:1: /relationship_id: a presence geometry period needs `relationship_id`'], $this->strings($this->validate()));
    }

    public function test_merge_line_is_checked_only_when_all_rule_keys_are_present(): void
    {
        $id = (string) Str::uuid();
        // Partial merges: nothing evaluated, even though merged values might violate the rules.
        $this->write('geometry_periods.jsonl', [
            ['id' => $id, 'description' => 'edit'],
            ['id' => (string) Str::uuid(), 'provenance_mode' => 'derived'],
            ['id' => (string) Str::uuid(), 'period_type' => 'presence'],
            ['id' => (string) Str::uuid(), 'geom' => self::GEOM],
        ]);
        $this->assertSame([], $this->strings($this->validate()));

        // All keys of a rule present: evaluated.
        $this->write('geometry_periods.jsonl', [['id' => $id, 'geom' => null, 'territory_geom' => null]]);
        $this->assertSame(['geometry_periods.jsonl:1: /geom: a geometry period needs `geom` or `territory_geom`'], $this->strings($this->validate()));
        $this->write('geometry_periods.jsonl', [['id' => $id, 'period_type' => 'presence', 'relationship_id' => null]]);
        $this->assertSame(['geometry_periods.jsonl:1: /relationship_id: a presence geometry period needs `relationship_id`'], $this->strings($this->validate()));
    }

    public function test_locations_always_need_a_locator(): void
    {
        $this->editFirst('entities.jsonl', fn ($r) => [[...$r, 'locations' => [
            ['location_name' => 'Rome'],
            ['is_primary' => false, 'geom' => null],
            ['territory_geom' => self::GEOM],
        ]]]);
        $this->assertSame(['entities.jsonl:1: /locations/1: a location needs `location_name`, `geom` or `territory_geom`'], $this->strings($this->validate()));
    }

    public function test_errors_on_unchanged_lines_become_warnings(): void
    {
        // The dev-data pattern: two relationship rows with identical keys, present in both the file and _base.
        $this->editFirst('relationships.jsonl', fn ($r) => [$r, [...$r, 'id' => (string) Str::uuid()]]);
        $this->rebase('relationships.jsonl');
        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertSame(['relationships.jsonl:2: /relationship_type: duplicate relationship: also on line 1 (unchanged since export)'], $this->strings($r));
        $this->assertTrue($r->issues()[0]->unchanged);

        // A start > end chronicle entry, also old data.
        $this->editFirst('chronicle_entries.jsonl', fn ($r) => [[...$r, 'start_year' => 1642, 'end_year' => 1400]]);
        $this->rebase('chronicle_entries.jsonl');
        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertContains('chronicle_entries.jsonl:1: /start_year: `start_year` 1642 is after `end_year` 1400 (unchanged since export)', $this->strings($r));

        // Editing one of the lines makes its error real again.
        $rows = $this->read('relationships.jsonl');
        $rows[1]['description'] = 'edited';
        $this->write('relationships.jsonl', $rows);
        $this->assertFalse($this->validate()->isValid());
    }

    public function test_new_duplicate_inserted_before_an_unchanged_line_stays_an_error(): void
    {
        // Existing line 1 is unchanged (it is in _base); the new line comes first, so the old line is the "later" one.
        $cases = [
            ['chronicles.jsonl', ['id' => (string) Str::uuid()], '/slug', 'duplicate chronicle slug "rome": also on line 1'],
            ['relationships.jsonl', ['id' => (string) Str::uuid()], '/relationship_type', 'duplicate relationship: also on line 1'],
            ['chronicles.jsonl', ['slug' => 'other'], '/id', 'duplicate id `%ID%`: also on line 1'],
        ];
        foreach ($cases as [$file, $patch, $field, $message]) {
            $rows = $this->read($file);
            $message = str_replace('%ID%', $rows[0]['id'], $message);
            $this->write($file, [[...$rows[0], ...$patch], ...$rows]);
            $r = $this->validate();
            $this->assertFalse($r->isValid(), $message);
            // The unchanged old line is now line 2; the issue is on it but the new line's hash is not in _base.
            $this->assertSame(["{$file}:2: {$field}: {$message}"], $this->strings($r));
            $this->restore($file);
        }
    }

    public function test_merge_relationship_line_without_all_keys_is_not_a_duplicate(): void
    {
        $this->editFirst('relationships.jsonl', fn ($r) => [$r, ['id' => (string) Str::uuid(), 'source_entity_id' => $r['source_entity_id'], 'target_entity_id' => $r['target_entity_id'], 'relationship_type' => $r['relationship_type']]]);
        $this->assertSame([], $this->strings($this->validate()));

        // The same line as a replace is complete (years read as null) and does collide.
        $rows = $this->read('relationships.jsonl');
        $rows[1]['_op'] = 'replace';
        $this->write('relationships.jsonl', $rows);
        $this->assertCount(1, $this->validate()->errors());
    }

    public function test_records_layer_does_not_run_when_structure_fails(): void
    {
        $this->editFirst('chronicles.jsonl', fn ($r) => [[...$r, 'start_year' => 9, 'end_year' => 1, 'nope' => 1]]);
        $r = $this->validate();
        $this->assertTrue($r->hasErrorsIn(Issue::STRUCTURE));
        $this->assertFalse($r->hasErrorsIn(Issue::RECORDS));
        $this->assertSame([], array_filter($r->issues(), fn ($i) => $i->layer === Issue::RECORDS));
    }

    public function test_record_layer_is_a_named_layer(): void
    {
        $this->assertSame(Issue::RECORDS, (new RecordChecks)->name());
        $v = new BundleValidator([new PackageChecks, new StructureChecks, new RecordChecks]);
        $this->assertTrue($v->validate(BundleReader::open($this->bundle))->isValid());
    }
}
