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
use App\Support\ContentBundle\Validation\BaseIndex;
use App\Support\ContentBundle\Validation\BundleValidator;
use App\Support\ContentBundle\Validation\Issue;
use App\Support\ContentBundle\Validation\IssueSink;
use App\Support\ContentBundle\Validation\ValidationReport;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;
use ZipArchive;

class ValidatePackageAndStructureTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    private string $bundle;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = sys_get_temp_dir().'/cb-val-'.bin2hex(random_bytes(6));
        mkdir($this->dir);

        $a = Entity::factory()->create(['wikidata_id' => null]);
        $b = Entity::factory()->create(['wikidata_id' => null]);
        DB::table('entity_aliases')->insert(['entity_id' => $a->entity_id, 'name' => 'Alias', 'language' => 'en', 'is_primary' => false]);
        $rel = EntityRelationship::query()->create(['relationship_id' => (string) Str::uuid(), 'source_entity_id' => $a->entity_id, 'target_entity_id' => $b->entity_id, 'relationship_type' => 'allied_with']);
        EntityGeoRef::factory()->create(['entity_id' => $a->entity_id]);
        $c = Chronicle::factory()->create(['slug' => 'rome']);
        ChronicleEntry::factory()->create(['chronicle_id' => $c->chronicle_id, 'sequence_order' => 1, 'primary_relationship_id' => $rel->relationship_id]);

        $this->bundle = $this->dir.'/b';
        app(ExportContentBundleAction::class)($this->bundle, ExportScope::parse([]), Profile::Full);
    }

    protected function tearDown(): void
    {
        exec('rm -rf '.escapeshellarg($this->dir));
        parent::tearDown();
    }

    private function validate(?string $path = null, array $limits = []): ValidationReport
    {
        return BundleValidator::validatePath($path ?? $this->bundle, false, $limits);
    }

    private function edit(string $file, callable $fn): void
    {
        $lines = explode("\n", rtrim((string) file_get_contents($this->bundle.'/'.$file), "\n"));
        $lines = $fn($lines);
        file_put_contents($this->bundle.'/'.$file, implode("\n", $lines)."\n");
    }

    /** @return list<string> */
    private function strings(ValidationReport $r): array
    {
        return array_map('strval', $r->issues());
    }

    private function makeZip(string $path, array $entries): void
    {
        $z = new ZipArchive;
        $z->open($path, ZipArchive::CREATE);
        foreach ($entries as $name => $body) {
            $z->addFromString($name, $body);
        }
        $z->close();
    }

    public function test_valid_bundle_has_no_issues(): void
    {
        $r = $this->validate();
        $this->assertSame([], $this->strings($r));
        $this->assertTrue($r->isValid());
        $this->assertSame(['valid' => true, 'errors' => 0, 'warnings' => 0, 'issues' => []], $r->toArray());
    }

    public function test_valid_zip_bundle_has_no_issues(): void
    {
        $zip = $this->dir.'/b.zip';
        $this->makeZip($zip, array_combine(
            $files = array_map(fn ($p) => substr($p, strlen($this->bundle) + 1), array_filter(glob($this->bundle.'/{,_base/}*', GLOB_BRACE), 'is_file')),
            array_map(fn ($f) => (string) file_get_contents($this->bundle.'/'.$f), $files),
        ));
        $this->assertSame([], $this->strings($this->validate($zip)));
    }

    public function test_missing_manifest_is_an_error(): void
    {
        unlink($this->bundle.'/manifest.json');
        $r = $this->validate();
        $this->assertSame(['manifest.json: manifest.json is missing'], $this->strings($r));
        $this->assertFalse($r->isValid());
    }

    public function test_unreadable_manifest_is_an_error(): void
    {
        file_put_contents($this->bundle.'/manifest.json', '{nope');
        $this->assertSame(['manifest.json: cannot read manifest: Syntax error'], $this->strings($this->validate()));
    }

    public function test_wrong_version_is_an_error(): void
    {
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['version'] = 2;
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        $this->assertSame(['manifest.json: /version: unsupported bundle version 2; this site reads version 1'], $this->strings($this->validate()));
    }

    public function test_manifest_schema_errors_carry_field_pointers(): void
    {
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['profile'] = 'secret';
        $m['extra'] = 1;
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        $out = implode("\n", $this->strings($this->validate()));
        $this->assertStringContainsString('manifest.json: /profile: invalid value "secret"; allowed: "full", "public"', $out);
        $this->assertStringContainsString('manifest.json: /extra: unknown key `extra`', $out);
    }

    public function test_edited_base_fails_checksum(): void
    {
        file_put_contents($this->bundle.'/_base/entities.jsonl', "tampered\n", FILE_APPEND);
        $this->assertSame(['_base/entities.jsonl: _base snapshot was modified; re-export instead of editing _base/'], $this->strings($this->validate()));
    }

    public function test_base_file_missing_from_checksums_is_an_error(): void
    {
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        unset($m['checksums']['_base/geo_refs.jsonl']);
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        $this->assertSame(['_base/geo_refs.jsonl: file is not listed in the manifest checksums'], $this->strings($this->validate()));
    }

    public function test_stray_file_is_an_unknown_file_error(): void
    {
        file_put_contents($this->bundle.'/notes.txt', 'hi');
        $out = $this->strings($this->validate());
        $this->assertCount(1, $out);
        $this->assertStringStartsWith('notes.txt: unknown file', $out[0]);
    }

    public function test_deleted_record_file_produces_no_issue(): void
    {
        unlink($this->bundle.'/geo_refs.jsonl');
        $this->assertSame([], $this->strings($this->validate()));
    }

    public function test_unsafe_file_names_are_errors(): void
    {
        $zip = $this->dir.'/h.zip';
        $this->makeZip($zip, ['manifest.json' => '{}', '../evil.txt' => 'x', '/abs.txt' => 'x', 'a\\b.txt' => 'x']);
        $out = implode("\n", $this->strings($this->validate($zip)));
        $this->assertStringContainsString('../evil.txt: unsafe file name', $out);
        $this->assertStringContainsString('/abs.txt: unsafe file name', $out);
        $this->assertStringContainsString('a\\b.txt: unsafe file name', $out);
        $this->assertStringNotContainsString('unknown file', $out);
    }

    public function test_duplicate_zip_entry_is_a_package_error(): void
    {
        $zip = $this->dir.'/dup.zip';
        $this->makeZip($zip, ['manifest.json' => '{}', 'a.txt' => '1', 'a.txb' => '2']);
        file_put_contents($zip, str_replace('a.txb', 'a.txt', (string) file_get_contents($zip)));
        $out = implode("\n", $this->strings($this->validate($zip)));
        $this->assertStringContainsString('duplicate zip entry a.txt: tools disagree on which copy is read', $out);
    }

    public function test_limit_exceeded_at_open_gives_exactly_one_package_error(): void
    {
        $zip = $this->dir.'/many.zip';
        $this->makeZip($zip, array_combine(array_map(fn ($i) => "f{$i}.txt", range(1, 70)), array_fill(0, 70, 'x')));
        $r = $this->validate($zip);
        $this->assertCount(1, $r->issues());
        $this->assertSame(Issue::PACKAGE, $r->issues()[0]->layer);
        $this->assertStringContainsString('limit is 64', $r->issues()[0]->message);

        $r = $this->validate($this->bundle, ['maxEntries' => 3]);
        $this->assertCount(1, $r->issues());
    }

    public function test_missing_path_is_a_package_error(): void
    {
        $r = $this->validate($this->dir.'/nope.zip');
        $this->assertCount(1, $r->issues());
        $this->assertStringContainsString('Bundle not found', $r->issues()[0]->message);
    }

    public function test_entry_size_limit_is_a_single_package_error(): void
    {
        $r = $this->validate($this->bundle, ['maxEntryBytes' => 100]);
        $this->assertCount(1, $r->issues());
        $this->assertTrue($r->hasErrorsIn(Issue::PACKAGE));
    }

    public function test_broken_json_line_has_the_right_line_number(): void
    {
        $this->edit('entities.jsonl', function (array $l) {
            $l[1] = '{"id": nope';

            return $l;
        });
        $r = $this->validate();
        $this->assertSame(['entities.jsonl:2: invalid JSON: Syntax error'], $this->strings($r));
        $this->assertSame(Issue::STRUCTURE, $r->issues()[0]->layer);
    }

    public function test_non_object_lines_are_errors_and_blank_lines_a_warning(): void
    {
        $this->edit('chronicles.jsonl', fn (array $l) => [...$l, '[1,2]', '', '"x"']);
        $r = $this->validate();
        $this->assertSame([
            'chronicles.jsonl:2: line must be a JSON object',
            'chronicles.jsonl:4: line must be a JSON object',
            'chronicles.jsonl: 1 blank line ignored',
        ], $this->strings($r));
        $this->assertSame(2, $r->errorCount());
        $this->assertSame(1, $r->warningCount());
    }

    public function test_unknown_key_is_named(): void
    {
        $this->edit('entities.jsonl', function (array $l) {
            $o = json_decode($l[0], true);
            $o['sumary'] = 'typo';
            $l[0] = json_encode($o);

            return $l;
        });
        $out = $this->strings($this->validate());
        $this->assertSame(['entities.jsonl:1: /sumary: unknown key `sumary`'], $out);
    }

    public function test_nested_error_has_nested_pointer_and_no_wrapper_noise(): void
    {
        $this->edit('entities.jsonl', function (array $l) {
            $o = json_decode($l[0], true);
            $o['aliases'][0]['name'] = 5;
            $l[0] = json_encode($o);

            return $l;
        });
        $out = $this->strings($this->validate());
        $this->assertCount(1, $out);
        $this->assertStringStartsWith('entities.jsonl:1: /aliases/0/name: ', $out[0]);
    }

    public function test_missing_required_keys_are_reported(): void
    {
        $this->edit('entities.jsonl', function (array $l) {
            $o = json_decode($l[0], true);
            unset($o['id'], $o['name']);
            $l[0] = json_encode($o);

            return $l;
        });
        $r = $this->validate();
        $this->assertFalse($r->isValid());
        $this->assertStringContainsString('name', implode("\n", $this->strings($r)));
    }

    public function test_wrong_enum_value_has_field_pointer(): void
    {
        $this->edit('entities.jsonl', function (array $l) {
            $o = json_decode($l[0], true);
            $o['entity_type'] = 'bogus';
            $l[0] = json_encode($o);

            return $l;
        });
        $r = $this->validate();
        $this->assertCount(1, $r->issues());
        $this->assertSame('/entity_type', $r->issues()[0]->field);
        $this->assertStringContainsString('"bogus"', $r->issues()[0]->message);
        $this->assertSame(1, $r->issues()[0]->line);
    }

    public function test_later_layers_do_not_run_when_structure_fails(): void
    {
        $ran = [];
        $validator = new BundleValidator(
            records: function () use (&$ran) {
                $ran[] = 'records';
            },
            references: function () use (&$ran) {
                $ran[] = 'references';
            },
        );
        $this->edit('chronicles.jsonl', fn (array $l) => [...$l, 'nope']);
        $r = $validator->validate(BundleReader::open($this->bundle));
        $this->assertTrue($r->hasErrorsIn(Issue::STRUCTURE));
        $this->assertSame([], $ran);
    }

    public function test_later_layers_run_in_order_and_records_errors_stop_references(): void
    {
        $ran = [];
        $validator = new BundleValidator(
            records: function ($b, IssueSink $sink) use (&$ran) {
                $ran[] = 'records';
                $sink->add(Issue::error(Issue::RECORDS, 'bad record', 'entities.jsonl', 1));
            },
            references: function () use (&$ran) {
                $ran[] = 'references';
            },
        );
        $r = $validator->validate(BundleReader::open($this->bundle));
        $this->assertSame(['records'], $ran);
        $this->assertSame(['entities.jsonl:1: bad record'], $this->strings($r));

        $ran = [];
        $validator = new BundleValidator(records: function () use (&$ran) {
            $ran[] = 'records';
        }, references: function () use (&$ran) {
            $ran[] = 'references';
        });
        $this->assertTrue($validator->validate(BundleReader::open($this->bundle))->isValid());
        $this->assertSame(['records', 'references'], $ran);
    }

    public function test_unexpected_exceptions_propagate(): void
    {
        $validator = new BundleValidator(records: function () {
            throw new \RuntimeException('database is down');
        });
        $this->expectExceptionMessage('database is down');
        $validator->validate(BundleReader::open($this->bundle));
    }

    public function test_package_errors_stop_before_structure(): void
    {
        file_put_contents($this->bundle.'/notes.txt', 'hi');
        $this->edit('chronicles.jsonl', fn (array $l) => [...$l, 'nope']);
        $r = $this->validate();
        $this->assertTrue($r->hasErrorsIn(Issue::PACKAGE));
        $this->assertFalse($r->hasErrorsIn(Issue::STRUCTURE));
    }

    public function test_over_long_line_is_a_structure_error_at_its_line(): void
    {
        $this->edit('chronicles.jsonl', function (array $l) {
            $o = json_decode($l[0], true);
            $o['title'] = str_repeat('x', 5000);
            $l[0] = json_encode($o);

            return $l;
        });
        $r = $this->validate($this->bundle, ['maxLineBytes' => 4096]);
        $this->assertSame(['chronicles.jsonl:1: line is longer than 4096 bytes'], $this->strings($r));
    }

    public function test_unchanged_line_errors_are_warnings_but_edited_lines_stay_errors(): void
    {
        // Pre-existing problem in the export: a chronicle entry with start_year > end_year is fine for the
        // schema, so use an unknown key that survives into _base too.
        $mutate = function (string $dir, string $file): void {
            $lines = explode("\n", rtrim((string) file_get_contents("{$dir}/{$file}"), "\n"));
            $o = json_decode($lines[0], true);
            $o['sumary'] = 'old data problem';
            $lines[0] = json_encode($o);
            file_put_contents("{$dir}/{$file}", implode("\n", $lines)."\n");
        };
        $mutate($this->bundle, 'entities.jsonl');
        $mutate($this->bundle, '_base/entities.jsonl');
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/entities.jsonl'] = 'sha256:'.hash_file('sha256', $this->bundle.'/_base/entities.jsonl');
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));

        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertSame(['entities.jsonl:1: /sumary: unknown key `sumary` (unchanged since export)'], $this->strings($r));
        $this->assertSame(Issue::WARNING, $r->issues()[0]->severity);
        $this->assertTrue($r->issues()[0]->unchanged);
        $this->assertTrue($r->toArray()['issues'][0]['unchanged']);

        // Editing the line (a changed byte) turns it back into an error.
        $this->edit('entities.jsonl', fn (array $l) => [str_replace('old data problem', 'edited', $l[0]), ...array_slice($l, 1)]);
        $r = $this->validate();
        $this->assertFalse($r->isValid());
        $this->assertSame(['entities.jsonl:1: /sumary: unknown key `sumary`'], $this->strings($r));
    }

    public function test_per_file_cap_summarises_overflow_and_totals_stay_true(): void
    {
        $this->edit('chronicles.jsonl', fn (array $l) => [...$l, ...array_fill(0, 250, 'nope')]);
        $r = $this->validate();
        $this->assertCount(200, $r->errors());
        $this->assertCount(1, $r->warnings());
        $this->assertSame('chronicles.jsonl: …and 50 more errors in this file', (string) $r->warnings()[0]);
        $this->assertSame(250, $r->errorCount());
        $this->assertSame(250, $r->toArray()['errors']);
        $this->assertSame(0, $r->toArray()['warnings']);
        $this->assertCount(201, $r->toArray()['issues']);
    }

    public function test_dropped_warnings_are_counted_separately(): void
    {
        $report = new ValidationReport;
        $sink = new IssueSink($report, new BaseIndex(BundleReader::open($this->bundle)));
        for ($i = 0; $i < 1250; $i++) {
            $sink->add(Issue::warning(Issue::STRUCTURE, 'w', 'entities.jsonl', $i + 1));
        }
        $sink->add(Issue::error(Issue::STRUCTURE, 'e', 'entities.jsonl', 1));
        $sink->finish();
        $this->assertSame(1250, $report->warningCount());
        $this->assertSame(1, $report->errorCount());
        $this->assertSame('entities.jsonl: …and 1,050 more warnings in this file', (string) $report->issues()[array_key_last($report->issues())]);
    }

    public function test_issue_formatting_omits_missing_parts(): void
    {
        $this->assertSame('boom', (string) Issue::error('package', 'boom'));
        $this->assertSame('a.jsonl:3: boom', (string) Issue::error('structure', 'boom', 'a.jsonl', 3));
        $this->assertSame('a.jsonl: /x: boom', (string) Issue::error('structure', 'boom', 'a.jsonl', null, '/x'));
    }

    public function test_reader_can_be_passed_in_directly(): void
    {
        $reader = BundleReader::open($this->bundle);
        $this->assertSame([], $this->strings((new BundleValidator)->validate($reader)));
    }

    private function corruptZip(string $victim, string $marker): string
    {
        $zip = $this->dir.'/corrupt.zip';
        $z = new ZipArchive;
        $z->open($zip, ZipArchive::CREATE);
        foreach (array_filter(glob($this->bundle.'/{,_base/}*', GLOB_BRACE), 'is_file') as $f) {
            $name = substr($f, strlen($this->bundle) + 1);
            $z->addFile($f, $name);
            $z->setCompressionName($name, ZipArchive::CM_STORE);
        }
        $z->close();
        $bytes = (string) file_get_contents($zip);
        // The _base copy is byte-identical to the root file and stored after it, so take the last occurrence.
        $pos = str_starts_with($victim, '_base/') ? strrpos($bytes, $marker) : strpos($bytes, $marker);
        $this->assertNotFalse($pos);
        $bytes[$pos] = $bytes[$pos] === 'x' ? 'y' : 'x';
        file_put_contents($zip, $bytes);

        return $zip;
    }

    public function test_corrupt_zip_entries_become_package_errors(): void
    {
        foreach (['chronicles.jsonl' => '"slug":"rome"', 'manifest.json' => '"profile"', '_base/entities.jsonl' => '"entity_type"'] as $victim => $marker) {
            $r = $this->validate($this->corruptZip($victim, $marker));
            $this->assertFalse($r->isValid(), $victim);
            // Lines read before the CRC failure surfaces (it is only detected at the end of the entry) may add noise.
            $last = $r->issues()[array_key_last($r->issues())];
            $this->assertSame("{$victim} is corrupt or truncated", $last->message, $victim);
            $this->assertSame(Issue::PACKAGE, $last->layer);
        }
    }

    public function test_limit_hit_while_reading_is_a_package_error(): void
    {
        $size = (int) max(array_map('filesize', array_filter(glob($this->bundle.'/*'), 'is_file')));
        $reader = BundleReader::open($this->bundle, maxEntryBytes: $size + 10);
        file_put_contents($this->bundle.'/chronicles.jsonl', str_repeat(' ', $size + 50), FILE_APPEND); // grew after open
        $r = (new BundleValidator)->validate($reader);
        $this->assertCount(1, $r->issues());
        $this->assertSame(Issue::PACKAGE, $r->issues()[0]->layer);
        $this->assertStringContainsString('exceeds', $r->issues()[0]->message);
    }

    public function test_not_a_zip_has_a_plain_message(): void
    {
        file_put_contents($this->dir.'/junk.zip', 'not a zip');
        $r = $this->validate($this->dir.'/junk.zip');
        $this->assertCount(1, $r->issues());
        $this->assertStringContainsString('not a zip file', $r->issues()[0]->message);
    }

    /** @return array<string, mixed> */
    private function mutateLine(string $file, callable $fn): void
    {
        $this->edit($file, function (array $l) use ($fn) {
            $o = json_decode($l[0], true);
            $l[0] = json_encode($fn($o));

            return $l;
        });
    }

    public function test_bad_nullable_enum_gives_one_issue(): void
    {
        $this->mutateLine('entities.jsonl', fn ($o) => [...$o, 'confidence' => 'bogus']);
        $r = $this->validate();
        $this->assertCount(1, $r->issues());
        $this->assertSame('/confidence', $r->issues()[0]->field);
        $this->assertStringContainsString('invalid value "bogus"', $r->issues()[0]->message);
    }

    public function test_bad_nested_year_gives_one_plain_issue(): void
    {
        $this->mutateLine('entities.jsonl', function ($o) {
            $o['temporal_ranges'] = [['range_type' => 'primary', 'start_year' => 99999, 'is_primary' => true]];

            return $o;
        });
        $this->assertSame(['entities.jsonl:1: /temporal_ranges/0/start_year: must be a year between -20000 and 3000'], $this->strings($this->validate()));
    }

    public function test_bad_geometry_gives_one_joined_issue(): void
    {
        $this->mutateLine('entities.jsonl', function ($o) {
            $o['locations'] = [['location_name' => 'Rome', 'is_primary' => true, 'geom' => ['type' => 'Point']]];

            return $o;
        });
        $this->assertSame(['entities.jsonl:1: /locations/0/geom: needs `coordinates` or `geometries`'], $this->strings($this->validate()));
    }

    public function test_plain_language_messages_for_ids(): void
    {
        $this->mutateLine('entities.jsonl', fn ($o) => [...$o, 'id' => 'ABC', 'wikidata_id' => '42']);
        $out = implode("\n", $this->strings($this->validate()));
        $this->assertStringContainsString('/id: must be a lowercase UUID', $out);
        $this->assertStringContainsString('/wikidata_id: must be a Wikidata id like Q42', $out);
    }

    public function test_new_record_without_id_names_its_required_keys(): void
    {
        $this->mutateLine('entities.jsonl', function ($o) {
            unset($o['id'], $o['name']);

            return $o;
        });
        $this->assertSame(['entities.jsonl:1: a new record (no id) needs `name`'], $this->strings($this->validate()));
    }

    public function test_wrong_manifest_format_is_named(): void
    {
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['format'] = 'other/thing';
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        $this->assertSame(['manifest.json: /format: must be `history-mapped/content-bundle`'], $this->strings($this->validate()));
    }

    public function test_malformed_checksum_value_only_gets_the_schema_error(): void
    {
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/entities.jsonl'] = 'nothex';
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        $out = $this->strings($this->validate());
        $this->assertCount(1, $out);
        $this->assertStringNotContainsString('modified', $out[0]);
    }

    public function test_empty_manifest_object_and_empty_objects_are_handled(): void
    {
        file_put_contents($this->bundle.'/manifest.json', '{}');
        $out = $this->strings($this->validate());
        $this->assertStringStartsWith('manifest.json: missing required key `format`, `version`', $out[0]);
        $this->assertStringContainsString('`checksums`', $out[0]);

        $dir = $this->dir.'/empty';
        mkdir($dir);
        file_put_contents($dir.'/manifest.json', '{"format":"history-mapped/content-bundle","version":1,"profile":"full","exported_at":"2026-10-18T00:00:00Z","source":"t","scope":[],"base":"export","counts":{},"checksums":{}}');
        $this->assertSame([], $this->strings($this->validate($dir)));
    }

    public function test_crlf_bom_and_trailing_blank_lines_are_normalised(): void
    {
        $crlf = (string) preg_replace("/\n/", "\r\n", (string) file_get_contents($this->bundle.'/entities.jsonl'));
        file_put_contents($this->bundle.'/entities.jsonl', $crlf);
        $this->assertSame([], $this->strings($this->validate()));

        file_put_contents($this->bundle.'/chronicles.jsonl', "\xEF\xBB\xBF".file_get_contents($this->bundle.'/chronicles.jsonl'));
        $this->assertSame(['chronicles.jsonl: file starts with a byte-order mark; it was ignored'], $this->strings($this->validate()));

        file_put_contents($this->bundle.'/chronicles.jsonl', "\n", FILE_APPEND);
        $this->assertSame([
            'chronicles.jsonl: file starts with a byte-order mark; it was ignored',
            'chronicles.jsonl: 1 blank line ignored',
        ], $this->strings($this->validate()));
        $this->assertTrue($this->validate()->isValid());
    }

    public function test_crlf_saved_unchanged_lines_still_downgrade(): void
    {
        $this->mutateLine('entities.jsonl', fn ($o) => [...$o, 'sumary' => 'old']);
        $this->mutateLine('_base/entities.jsonl', fn ($o) => [...$o, 'sumary' => 'old']);
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/entities.jsonl'] = 'sha256:'.hash_file('sha256', $this->bundle.'/_base/entities.jsonl');
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));
        file_put_contents($this->bundle.'/entities.jsonl', str_replace("\n", "\r\n", (string) file_get_contents($this->bundle.'/entities.jsonl')));
        $r = $this->validate();
        $this->assertTrue($r->isValid());
        $this->assertCount(1, $r->warnings());
    }

    public function test_sink_downgrades_deferred_issues_by_line_hash(): void
    {
        $line = (string) strtok((string) file_get_contents($this->bundle.'/entities.jsonl'), "\n");
        $report = new ValidationReport;
        $sink = new IssueSink($report, new BaseIndex(BundleReader::open($this->bundle)));
        $this->assertSame(Issue::WARNING, $sink->add(Issue::error(Issue::REFERENCES, 'dangling', 'entities.jsonl', 1), sha1($line, true)));
        $this->assertSame(Issue::ERROR, $sink->add(Issue::error(Issue::REFERENCES, 'dangling', 'entities.jsonl', 1), sha1($line.' ', true)));
        $this->assertSame(Issue::ERROR, $sink->add(Issue::error(Issue::REFERENCES, 'dangling', 'entities.jsonl', 1)));
    }

    public function test_oversized_base_switches_downgrading_off_with_one_warning(): void
    {
        $this->mutateLine('entities.jsonl', fn ($o) => [...$o, 'sumary' => 'old']);
        $this->mutateLine('_base/entities.jsonl', fn ($o) => [...$o, 'sumary' => 'old']);
        $m = json_decode((string) file_get_contents($this->bundle.'/manifest.json'), true);
        $m['checksums']['_base/entities.jsonl'] = 'sha256:'.hash_file('sha256', $this->bundle.'/_base/entities.jsonl');
        file_put_contents($this->bundle.'/manifest.json', json_encode($m));

        $r = (new BundleValidator(baseIndexMaxLines: 1))->validate(BundleReader::open($this->bundle));
        $this->assertFalse($r->isValid());
        $this->assertCount(1, array_filter($r->warnings(), fn ($w) => str_contains($w->message, 'not downgraded')));

        $r = (new BundleValidator)->validate(BundleReader::open($this->bundle));
        $this->assertTrue($r->isValid());
    }

    public function test_file_is_abandoned_after_the_error_line_limit(): void
    {
        $this->edit('chronicles.jsonl', fn (array $l) => [...$l, ...array_fill(0, 20, 'nope')]);
        $r = (new BundleValidator(maxErrorLines: 5))->validate(BundleReader::open($this->bundle));
        $this->assertSame(5, $r->errorCount());
        $this->assertSame(['chronicles.jsonl: validation of this file stopped after 5 lines with errors'], array_map('strval', $r->warnings()));
    }
}
