<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use LogicException;
use Opis\JsonSchema\Errors\ErrorFormatter;
use RuntimeException;
use ZipArchive;

/**
 * Writes a content bundle to a directory or, for a `.zip` path, to a temp directory that is zipped by package().
 * Records stream straight to the record file and its byte-identical `_base/` copy, never held in memory.
 * A failed zip build removes the temp directory and leaves nothing at the target path; call abort() on failure.
 */
final class BundleWriter
{
    /** @var array<string, int> */
    private array $counts = [];

    /** @var array<string, true> */
    private array $written = [];

    private bool $finalized = false;

    private bool $finished = false;

    private function __construct(
        private readonly string $target,
        private readonly string $workDir,
        private readonly bool $zip,
        private readonly bool $createdDir,
    ) {}

    public static function open(string $path): self
    {
        $parent = dirname(rtrim($path, '/'));
        if (! is_dir($parent) || ! is_writable($parent)) {
            throw new RuntimeException("Cannot write bundle: directory {$parent} does not exist or is not writable.");
        }
        $zip = strtolower(pathinfo($path, PATHINFO_EXTENSION)) === 'zip';

        if ($zip) {
            if (file_exists($path) || is_link($path)) {
                throw new RuntimeException("Cannot write bundle: {$path} already exists.");
            }
            $tmpRoot = storage_path('app/tmp');
            if (! is_dir($tmpRoot) && ! @mkdir($tmpRoot, 0775, true) && ! is_dir($tmpRoot)) {
                throw new RuntimeException("Cannot create temp directory {$tmpRoot}.");
            }
            self::sweepStale($tmpRoot);
            $work = $tmpRoot.'/bundle-'.bin2hex(random_bytes(8));
            $created = true;
        } else {
            $work = rtrim($path, '/');
            if (file_exists($work)) {
                if (! is_dir($work) || count(array_diff(scandir($work) ?: [], ['.', '..'])) > 0) {
                    throw new RuntimeException("Cannot write bundle: {$path} exists and is not an empty directory.");
                }
                $created = false;
            } else {
                $created = true;
            }
        }

        if (! is_dir($work) && ! @mkdir($work, 0775, true) && ! is_dir($work)) {
            throw new RuntimeException("Cannot create directory {$work}.");
        }
        if (! @mkdir($work.'/'.BundleFormat::BASE_DIR, 0775, true) && ! is_dir($work.'/'.BundleFormat::BASE_DIR)) {
            throw new RuntimeException("Cannot create directory {$work}/".BundleFormat::BASE_DIR.'.');
        }

        return new self($path, $work, $zip, $created);
    }

    /** @param iterable<array<string, mixed>> $records already-serialized lines (arrays), encoded with JsonLine */
    public function writeRecords(RecordType $type, iterable $records): int
    {
        if ($this->finalized) {
            throw new LogicException('Cannot write records after the bundle was closed.');
        }
        if (isset($this->written[$type->value])) {
            throw new LogicException("Records for {$type->value} were already written.");
        }
        $this->written[$type->value] = true;
        $record = $this->handle($this->workDir.'/'.$type->file());
        $base = $this->handle($this->workDir.'/'.BundleFormat::BASE_DIR.'/'.$type->file());
        $count = 0;
        try {
            foreach ($records as $line) {
                $bytes = JsonLine::encode($line)."\n";
                if (fwrite($record, $bytes) !== strlen($bytes) || fwrite($base, $bytes) !== strlen($bytes)) {
                    throw new RuntimeException("Short write to {$type->file()}.");
                }
                $count++;
            }
        } finally {
            fclose($record);
            fclose($base);
        }

        return $this->counts[$type->value] = $count;
    }

    /**
     * Finalize the bundle contents then package it: finalize() followed by package().
     *
     * @param  array<string, mixed>  $manifest  format, version, profile, exported_at, source, scope, base
     * @return array<string, mixed>
     */
    public function close(array $manifest): array
    {
        $written = $this->finalize($manifest);
        $this->package();

        return $written;
    }

    /**
     * Fill counts and checksums, validate and write manifest.json, and add the licence for the public
     * profile. No records can be written afterwards. Returns the manifest as written.
     *
     * @param  array<string, mixed>  $manifest  format, version, profile, exported_at, source, scope, base
     * @return array<string, mixed>
     */
    public function finalize(array $manifest): array
    {
        if ($this->finalized) {
            throw new LogicException('Bundle was already finalized.');
        }
        $this->finalized = true;

        try {
            $counts = $checksums = [];
            foreach (RecordType::cases() as $type) {
                foreach ([$type->file(), BundleFormat::BASE_DIR.'/'.$type->file()] as $rel) {
                    if (! is_file($this->workDir.'/'.$rel) && ! touch($this->workDir.'/'.$rel)) {
                        throw new RuntimeException("Cannot create {$rel}.");
                    }
                }
                $counts[$type->value] = $this->counts[$type->value] ?? 0;
                $rel = BundleFormat::BASE_DIR.'/'.$type->file();
                $hash = hash_file('sha256', $this->workDir.'/'.$rel);
                if ($hash === false) {
                    throw new RuntimeException("Cannot checksum {$rel}.");
                }
                $checksums[$rel] = 'sha256:'.$hash;
            }

            $ordered = [];
            foreach (['format', 'version', 'profile', 'exported_at', 'source', 'scope', 'base'] as $key) {
                $ordered[$key] = $manifest[$key] ?? null;
            }
            $ordered['counts'] = $counts;
            $ordered['checksums'] = $checksums;

            $json = json_encode($ordered, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)."\n";
            $result = Schemas::validator()->validate(json_decode($json), Schemas::manifestSchemaId());
            if (! $result->isValid()) {
                $messages = (new ErrorFormatter)->formatFlat($result->error());
                throw new LogicException('Generated manifest does not match manifest.schema.json: '.implode('; ', array_map('strval', $messages)));
            }
            if (file_put_contents($this->workDir.'/'.BundleFormat::MANIFEST, $json) !== strlen($json)) {
                throw new RuntimeException('Cannot write manifest.json.');
            }

            if (($ordered['profile'] ?? null) === Profile::Public->value
                && ! copy(resource_path('content-bundle/LICENSE.public.txt'), $this->workDir.'/'.BundleFormat::LICENSE)) {
                throw new RuntimeException('Cannot write LICENSE.md.');
            }
        } catch (\Throwable $e) {
            $this->abort();
            throw $e;
        }

        return $ordered;
    }

    /** Zip the finalized bundle (when the target is a zip) and remove the temp directory. */
    public function package(): void
    {
        if (! $this->finalized) {
            throw new LogicException('Bundle must be finalized before packaging.');
        }

        try {
            if ($this->zip) {
                $this->buildZip();
            }
            $this->finished = true;
        } catch (\Throwable $e) {
            $this->abort();
            throw $e;
        } finally {
            if ($this->zip && is_dir($this->workDir)) {
                self::rmTree($this->workDir);
            }
        }
    }

    /** Remove everything this writer created. Safe to call more than once. */
    public function abort(): void
    {
        if ($this->finished) {
            return;
        }
        if ($this->zip) {
            self::rmTree($this->workDir);
        } elseif ($this->createdDir) {
            self::rmTree($this->workDir);
        } else {
            foreach (array_diff(scandir($this->workDir) ?: [], ['.', '..']) as $child) {
                self::rmTree($this->workDir.'/'.$child);
            }
        }
    }

    private static function sweepStale(string $tmpRoot): void
    {
        foreach (glob($tmpRoot.'/bundle-*') ?: [] as $stale) {
            $mtime = @filemtime($stale);
            if ($mtime !== false && $mtime < time() - 86400) {
                self::rmTree($stale);
            }
        }
    }

    private static function rmTree(string $path): void
    {
        if (is_link($path) || is_file($path)) {
            @unlink($path);

            return;
        }
        if (is_dir($path)) {
            foreach (array_diff(scandir($path) ?: [], ['.', '..']) as $child) {
                self::rmTree($path.'/'.$child);
            }
            @rmdir($path);
        }
    }

    private function buildZip(): void
    {
        $tmpZip = $this->workDir.'.zip';
        $zip = new ZipArchive;
        $code = $zip->open($tmpZip, ZipArchive::CREATE | ZipArchive::OVERWRITE);
        if ($code !== true) {
            throw new RuntimeException("Cannot create zip {$tmpZip} (ZipArchive error code {$code}).");
        }
        $names = [BundleFormat::MANIFEST];
        if (is_file($this->workDir.'/'.BundleFormat::LICENSE)) {
            $names[] = BundleFormat::LICENSE;
        }
        foreach ([false, true] as $base) {
            foreach (RecordType::cases() as $type) {
                $names[] = ($base ? BundleFormat::BASE_DIR.'/' : '').$type->file();
            }
        }
        foreach ($names as $name) {
            if (! $zip->addFile($this->workDir.'/'.$name, $name) || ! $zip->setCompressionName($name, ZipArchive::CM_DEFLATE, 6)) {
                $zip->unchangeAll();
                $zip->close();
                @unlink($tmpZip);
                throw new RuntimeException("Cannot add {$name} to the zip.");
            }
        }
        if (! $zip->close()) {
            @unlink($tmpZip);
            throw new RuntimeException("Cannot finalise zip {$tmpZip}.");
        }
        if (! @rename($tmpZip, $this->target)) {
            @unlink($tmpZip);
            throw new RuntimeException("Cannot move zip to {$this->target}.");
        }
    }

    /** @return resource */
    private function handle(string $file)
    {
        $h = fopen($file, 'ab');
        if ($h === false) {
            throw new RuntimeException("Cannot open {$file} for writing.");
        }

        return $h;
    }
}
