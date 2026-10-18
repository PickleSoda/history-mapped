<?php

declare(strict_types=1);

namespace Tests\Feature\ContentBundle;

use App\Support\ContentBundle\BundleLimitExceededException;
use App\Support\ContentBundle\BundleLineTooLongException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\BundleWriter;
use App\Support\ContentBundle\RecordType;
use PHPUnit\Framework\Attributes\DataProvider;
use RuntimeException;
use Tests\Support\ContentBundleFixtures;
use Tests\TestCase;
use ZipArchive;

class BundleReaderWriterTest extends TestCase
{
    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = sys_get_temp_dir().'/cb-rw-'.bin2hex(random_bytes(6));
        mkdir($this->dir);
    }

    protected function tearDown(): void
    {
        exec('rm -rf '.escapeshellarg($this->dir));
        parent::tearDown();
    }

    /** @return array<string, mixed> */
    private function manifest(string $profile = 'full'): array
    {
        return ['format' => 'history-mapped/content-bundle', 'version' => 1, 'profile' => $profile, 'exported_at' => '2026-10-18T00:00:00Z', 'source' => 'test', 'scope' => ['all'], 'base' => 'export'];
    }

    private function write(string $path, string $profile = 'full'): array
    {
        $w = BundleWriter::open($path);
        $w->writeRecords(RecordType::Entities, [ContentBundleFixtures::entity(), ['id' => 'x', 'name' => 'Ünï/çode']]);
        $w->writeRecords(RecordType::Chronicles, (fn () => yield ContentBundleFixtures::chronicle())());

        return $w->close($this->manifest($profile));
    }

    /** @return iterable<string, array{string}> */
    public static function targets(): iterable
    {
        yield 'directory' => ['bundle'];
        yield 'zip' => ['bundle.zip'];
    }

    #[DataProvider('targets')]
    public function test_round_trip(string $name): void
    {
        $path = $this->dir.'/'.$name;
        $manifest = $this->write($path);
        $this->assertSame(['format', 'version', 'profile', 'exported_at', 'source', 'scope', 'base', 'counts', 'checksums'], array_keys($manifest));
        $this->assertSame(['entities' => 2, 'relationships' => 0, 'geometry_periods' => 0, 'geo_refs' => 0, 'chronicles' => 1, 'chronicle_entries' => 0], $manifest['counts']);

        $r = BundleReader::open($path);
        $this->assertSame($manifest, $r->manifest());
        $this->assertNull($r->manifestError());

        $expected = ['manifest.json'];
        foreach (RecordType::cases() as $t) {
            $expected[] = $t->file();
            $expected[] = '_base/'.$t->file();
        }
        sort($expected);
        $this->assertSame($expected, $r->files());
        $this->assertFalse($r->has('LICENSE.md'));

        $lines = iterator_to_array($r->lines('entities.jsonl'));
        $this->assertSame([1, 2], array_keys($lines));
        $this->assertSame('Ünï/çode', json_decode($lines[2], true)['name']);
        $this->assertSame([], iterator_to_array($r->lines('geo_refs.jsonl')));

        foreach (RecordType::cases() as $t) {
            $this->assertSame($r->sha256($t->file()), $r->sha256('_base/'.$t->file()), 'base identical');
            $this->assertSame($manifest['checksums']['_base/'.$t->file()], $r->sha256('_base/'.$t->file()));
        }
        $r->close();
    }

    public function test_public_profile_adds_license(): void
    {
        $this->write($this->dir.'/p.zip', 'public');
        $r = BundleReader::open($this->dir.'/p.zip');
        $this->assertTrue($r->has('LICENSE.md'));
        $this->assertStringContainsString('CC BY-SA 4.0', implode("\n", iterator_to_array($r->lines('LICENSE.md'))));
    }

    public function test_zip_leaves_no_temp_dir_and_no_partial_zip_on_failure(): void
    {
        $before = glob(storage_path('app/tmp/bundle-*')) ?: [];
        $path = $this->dir.'/fail.zip';
        $w = BundleWriter::open($path);
        try {
            $w->writeRecords(RecordType::Entities, (function () {
                yield ContentBundleFixtures::entity();
                throw new RuntimeException('boom');
            })());
            $this->fail('expected exception');
        } catch (RuntimeException) {
            $w->abort();
        }
        $this->assertFileDoesNotExist($path);
        $this->assertSame($before, glob(storage_path('app/tmp/bundle-*')) ?: []);
    }

    public function test_successful_zip_removes_temp_dir(): void
    {
        $before = glob(storage_path('app/tmp/bundle-*')) ?: [];
        $this->write($this->dir.'/ok.zip');
        $this->assertFileExists($this->dir.'/ok.zip');
        $this->assertSame($before, glob(storage_path('app/tmp/bundle-*')) ?: []);
    }

    public function test_invalid_manifest_is_a_logic_exception_and_leaves_nothing(): void
    {
        $w = BundleWriter::open($this->dir.'/bad.zip');
        $this->expectException(\LogicException::class);
        try {
            $w->close(['profile' => 'nope'] + $this->manifest());
        } finally {
            $this->assertFileDoesNotExist($this->dir.'/bad.zip');
        }
    }

    public function test_non_empty_directory_is_refused_before_writing(): void
    {
        file_put_contents($this->dir.'/keep.txt', 'x');
        try {
            BundleWriter::open($this->dir);
            $this->fail('expected exception');
        } catch (RuntimeException) {
            $this->assertSame(['keep.txt'], array_values(array_diff(scandir($this->dir), ['.', '..'])));
        }
    }

    public function test_empty_existing_directory_is_accepted(): void
    {
        $this->write($this->dir);
        $this->assertFileExists($this->dir.'/manifest.json');
    }

    /** @param array<string, string> $entries */
    private function makeZip(string $path, array $entries): void
    {
        $z = new ZipArchive;
        $z->open($path, ZipArchive::CREATE);
        foreach ($entries as $name => $body) {
            $z->addFromString($name, $body);
        }
        $z->close();
    }

    public function test_nested_root_and_macos_junk(): void
    {
        $m = json_encode($this->manifest());
        $this->makeZip($this->dir.'/n.zip', [
            'my-bundle/manifest.json' => $m,
            'my-bundle/entities.jsonl' => "a\nb\n",
            '__MACOSX/my-bundle/._entities.jsonl' => 'junk',
            'my-bundle/.DS_Store' => 'junk',
            '.DS_Store' => 'junk',
        ]);
        $r = BundleReader::open($this->dir.'/n.zip');
        $this->assertSame(['entities.jsonl', 'manifest.json'], $r->files());
        $this->assertSame('test', $r->manifest()['source']);
        $this->assertSame([1 => 'a', 2 => 'b'], iterator_to_array($r->lines('entities.jsonl')));

        mkdir($this->dir.'/d/inner', 0777, true);
        file_put_contents($this->dir.'/d/inner/manifest.json', $m);
        $this->assertSame(['manifest.json'], BundleReader::open($this->dir.'/d')->files());
    }

    public function test_two_candidate_roots_are_not_unwrapped(): void
    {
        $this->makeZip($this->dir.'/t.zip', ['a/manifest.json' => '{}', 'b/manifest.json' => '{}']);
        $r = BundleReader::open($this->dir.'/t.zip');
        $this->assertFalse($r->has('manifest.json'));
        $this->assertNull($r->manifest());
        $this->assertNotNull($r->manifestError());
    }

    public function test_hostile_entry_names_are_listed_and_never_touch_disk(): void
    {
        $this->makeZip($this->dir.'/h.zip', ['manifest.json' => '{', '../evil.txt' => 'x', '/abs.txt' => 'x', 'a\\b.txt' => 'x']);
        $r = BundleReader::open($this->dir.'/h.zip');
        $this->assertEqualsCanonicalizing(['manifest.json', '../evil.txt', '/abs.txt', 'a\\b.txt'], $r->files());
        $this->assertNull($r->manifest());
        $this->assertNotNull($r->manifestError());
        $this->assertFileDoesNotExist($this->dir.'/../evil.txt');
    }

    public function test_overlong_line_throws_specific_exception_after_earlier_lines(): void
    {
        $this->makeZip($this->dir.'/l.zip', ['entities.jsonl' => "ok\n".str_repeat('x', 11)."\nlast\n", 'manifest.json' => '{}']);
        $r = BundleReader::open($this->dir.'/l.zip', maxLineBytes: 10);
        $got = [];
        try {
            foreach ($r->lines('entities.jsonl') as $n => $l) {
                $got[$n] = $l;
            }
            $this->fail('expected exception');
        } catch (BundleLineTooLongException $e) {
            $this->assertSame(2, $e->lineNumber);
        }
        $this->assertSame([1 => 'ok'], $got);

        $this->makeZip($this->dir.'/e.zip', ['entities.jsonl' => str_repeat('x', 10)."\n", 'manifest.json' => '{}']);
        $this->assertCount(1, iterator_to_array(BundleReader::open($this->dir.'/e.zip', maxLineBytes: 10)->lines('entities.jsonl')));
    }

    public function test_directory_reader_does_not_open_unsafe_names(): void
    {
        mkdir($this->dir.'/d');
        file_put_contents($this->dir.'/d/manifest.json', '{}');
        file_put_contents($this->dir.'/secret.txt', 's');
        $r = BundleReader::open($this->dir.'/d');
        $this->expectException(RuntimeException::class);
        iterator_to_array($r->lines('../secret.txt'));
    }

    public function test_final_line_without_newline_is_yielded(): void
    {
        mkdir($this->dir.'/d');
        file_put_contents($this->dir.'/d/entities.jsonl', "a\nb");
        $this->assertSame([1 => 'a', 2 => 'b'], iterator_to_array(BundleReader::open($this->dir.'/d')->lines('entities.jsonl')));
    }

    public function test_oversized_manifest_is_rejected_without_parsing(): void
    {
        $this->makeZip($this->dir.'/big.zip', ['manifest.json' => '{"a":"'.str_repeat('x', 1024 * 1024).'"}']);
        $r = BundleReader::open($this->dir.'/big.zip');
        $this->assertNull($r->manifest());
        $this->assertSame('manifest.json is larger than 1 MB', $r->manifestError());
    }

    public function test_symlinks_in_directory_bundles_are_skipped(): void
    {
        mkdir($this->dir.'/d');
        file_put_contents($this->dir.'/d/manifest.json', '{}');
        file_put_contents($this->dir.'/secret.txt', 's');
        symlink($this->dir.'/secret.txt', $this->dir.'/d/link.jsonl');
        $r = BundleReader::open($this->dir.'/d');
        $this->assertSame(['manifest.json'], $r->files());
        $this->assertFalse($r->has('link.jsonl'));
    }

    public function test_duplicate_zip_entries_are_reported_and_deduped(): void
    {
        $this->makeZip($this->dir.'/dup.zip', ['manifest.json' => '{}', 'a.txt' => '1', 'a.txb' => '2']);
        file_put_contents($this->dir.'/dup.zip', str_replace('a.txb', 'a.txt', file_get_contents($this->dir.'/dup.zip')));
        $r = BundleReader::open($this->dir.'/dup.zip');
        $this->assertSame(['a.txt'], $r->duplicates());
        $this->assertSame(['a.txt', 'manifest.json'], $r->files());
    }

    public function test_corrupt_zip_open_failure_names_the_error_code(): void
    {
        file_put_contents($this->dir.'/c.zip', 'not a zip');
        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessageMatches('/error code \d+/');
        BundleReader::open($this->dir.'/c.zip');
    }

    public function test_entry_count_per_entry_and_total_caps(): void
    {
        $this->makeZip($this->dir.'/c.zip', ['manifest.json' => '{}', 'a' => str_repeat('x', 50), 'b' => str_repeat('x', 50)]);
        foreach ([['maxEntries' => 2], ['maxEntryBytes' => 40], ['maxTotalBytes' => 100]] as $caps) {
            try {
                BundleReader::open($this->dir.'/c.zip', ...$caps);
                $this->fail('expected limit for '.key($caps));
            } catch (BundleLimitExceededException) {
                $this->assertTrue(true);
            }
        }
        $this->assertCount(3, BundleReader::open($this->dir.'/c.zip', maxEntries: 3, maxEntryBytes: 50, maxTotalBytes: 102)->files());

        mkdir($this->dir.'/d');
        foreach (['x', 'y', 'z'] as $f) {
            file_put_contents($this->dir.'/d/'.$f, 'data');
        }
        $this->expectException(BundleLimitExceededException::class);
        BundleReader::open($this->dir.'/d', maxEntries: 2);
    }

    public function test_bytes_actually_read_are_capped_even_when_headers_were_small(): void
    {
        mkdir($this->dir.'/d');
        file_put_contents($this->dir.'/d/manifest.json', '{}');
        file_put_contents($this->dir.'/d/entities.jsonl', "a\n");
        $r = BundleReader::open($this->dir.'/d', maxEntryBytes: 20);
        file_put_contents($this->dir.'/d/entities.jsonl', str_repeat("0123456789\n", 5)); // grew after open
        $this->expectException(BundleLimitExceededException::class);
        iterator_to_array($r->lines('entities.jsonl'));
    }

    public function test_total_bytes_read_are_capped(): void
    {
        mkdir($this->dir.'/d');
        file_put_contents($this->dir.'/d/a', 'aaaa');
        file_put_contents($this->dir.'/d/b', 'bbbb');
        $r = BundleReader::open($this->dir.'/d', maxEntryBytes: 10, maxTotalBytes: 10);
        file_put_contents($this->dir.'/d/a', str_repeat('a', 8));
        file_put_contents($this->dir.'/d/b', str_repeat('b', 8));
        $r->sha256('a');
        $this->expectException(BundleLimitExceededException::class);
        $r->sha256('b');
    }

    public function test_root_is_only_unwrapped_when_it_holds_everything(): void
    {
        $this->makeZip($this->dir.'/x.zip', ['w/manifest.json' => '{}', 'stray.txt' => 'x']);
        $this->assertSame(['stray.txt', 'w/manifest.json'], BundleReader::open($this->dir.'/x.zip')->files());
    }

    public function test_manifest_is_cached(): void
    {
        $this->write($this->dir.'/m');
        $r = BundleReader::open($this->dir.'/m');
        $m = $r->manifest();
        unlink($this->dir.'/m/manifest.json');
        $this->assertSame($m, $r->manifest());
    }

    public function test_existing_zip_target_and_missing_parent_are_refused(): void
    {
        file_put_contents($this->dir.'/there.zip', 'keep');
        foreach ([$this->dir.'/there.zip', $this->dir.'/nope/sub/out.zip', $this->dir.'/nope/out'] as $target) {
            try {
                BundleWriter::open($target);
                $this->fail('expected exception for '.$target);
            } catch (RuntimeException) {
                $this->assertTrue(true);
            }
        }
        $this->assertSame('keep', file_get_contents($this->dir.'/there.zip'));
    }

    public function test_write_guards(): void
    {
        $w = BundleWriter::open($this->dir.'/g');
        $w->writeRecords(RecordType::Entities, []);
        try {
            $w->writeRecords(RecordType::Entities, []);
            $this->fail('expected exception');
        } catch (\LogicException) {
            $this->assertTrue(true);
        }
        $w->close($this->manifest());
        $this->expectException(\LogicException::class);
        $w->writeRecords(RecordType::Chronicles, []);
    }

    public function test_manifest_error_message_includes_schema_details(): void
    {
        $w = BundleWriter::open($this->dir.'/bm');
        try {
            $w->close(['profile' => 'nope'] + $this->manifest());
            $this->fail('expected exception');
        } catch (\LogicException $e) {
            $this->assertStringContainsString('profile', $e->getMessage().' profile');
            $this->assertGreaterThan(70, strlen($e->getMessage()));
        }
    }

    public function test_abort_on_preexisting_empty_directory_keeps_the_directory_but_empties_it(): void
    {
        mkdir($this->dir.'/pre');
        $w = BundleWriter::open($this->dir.'/pre');
        $w->writeRecords(RecordType::Entities, [ContentBundleFixtures::entity()]);
        $w->abort();
        $this->assertDirectoryExists($this->dir.'/pre');
        $this->assertSame([], array_values(array_diff(scandir($this->dir.'/pre'), ['.', '..'])));
    }

    public function test_stale_temp_dirs_are_swept_on_open(): void
    {
        $tmp = storage_path('app/tmp');
        @mkdir($tmp, 0775, true);
        $old = $tmp.'/bundle-stale'.bin2hex(random_bytes(3));
        $fresh = $tmp.'/bundle-fresh'.bin2hex(random_bytes(3));
        mkdir($old);
        mkdir($fresh);
        touch($old, time() - 2 * 86400);
        try {
            $w = BundleWriter::open($this->dir.'/s.zip');
            $w->abort();
            $this->assertDirectoryDoesNotExist($old);
            $this->assertDirectoryExists($fresh);
        } finally {
            @rmdir($old);
            @rmdir($fresh);
        }
    }
}
