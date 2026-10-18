<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use Generator;
use RuntimeException;
use ZipArchive;

/**
 * Reads a bundle from a zip or a directory without ever extracting to disk; treat every package as hostile.
 * Zip entries are read through ZipArchive streams; entry names are only compared as strings, never resolved
 * against the filesystem. Hostile names (absolute, `..`, backslashes) are listed by files() unchanged so the
 * validator can flag them, but cannot be read from a directory bundle. Symlinks in directories are not listed.
 * A single wrapper directory holding everything (manifest.json inside) is the root.
 *
 * Limits: at most MAX_ENTRIES entries, MAX_ENTRY_BYTES per entry and MAX_TOTAL_BYTES in total, checked from
 * headers at open() and again against the bytes actually read (headers can lie); breaches throw
 * BundleLimitExceededException. Lines longer than the line limit make lines() throw BundleLineTooLongException;
 * manifest() reads at most 1 MB and reports problems through manifestError(). Duplicate zip entry names are
 * collected in duplicates() (the zip is reopened without CHECKCONS only for that one error). The file listing is computed once per reader.
 */
final class BundleReader
{
    public const MAX_LINE_BYTES = 8 * 1024 * 1024;

    public const MAX_MANIFEST_BYTES = 1024 * 1024;

    public const MAX_ENTRIES = 64;

    public const MAX_ENTRY_BYTES = 2 * 1024 * 1024 * 1024;

    public const MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024;

    private bool $manifestLoaded = false;

    /** @var array<string, mixed>|null */
    private ?array $manifest = null;

    private ?string $manifestError = null;

    /** @var array<string, int> bytes actually read, max per file, for the total cap */
    private array $seen = [];

    /**
     * @param  array<string, int>  $files  path below the root => 1, a lookup set
     * @param  list<string>  $duplicates
     */
    private function __construct(
        private readonly ?ZipArchive $zip,
        private readonly string $dir,
        private readonly string $prefix,
        private readonly array $files,
        private readonly array $duplicates,
        private readonly int $maxLineBytes,
        private readonly int $maxEntryBytes,
        private readonly int $maxTotalBytes,
    ) {}

    public static function open(
        string $path,
        int $maxLineBytes = self::MAX_LINE_BYTES,
        int $maxEntries = self::MAX_ENTRIES,
        int $maxEntryBytes = self::MAX_ENTRY_BYTES,
        int $maxTotalBytes = self::MAX_TOTAL_BYTES,
    ): self {
        $zip = null;
        $dir = '';
        /** @var array<string, int> $sizes raw name => declared size */
        $sizes = [];
        $raw = [];

        if (is_dir($path)) {
            $dir = rtrim($path, '/');
            $iter = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS));
            foreach ($iter as $info) {
                if ($info->isFile() && ! $info->isLink()) {
                    $name = str_replace(DIRECTORY_SEPARATOR, '/', substr($info->getPathname(), strlen($dir) + 1));
                    $raw[] = $name;
                    $sizes[$name] = (int) $info->getSize();
                }
                if (count($raw) > $maxEntries) {
                    throw new BundleLimitExceededException("Bundle has more than {$maxEntries} entries.");
                }
            }
        } else {
            if (! is_file($path)) {
                throw new RuntimeException("Bundle not found: {$path}");
            }
            $zip = new ZipArchive;
            $code = $zip->open($path, ZipArchive::RDONLY | ZipArchive::CHECKCONS);
            if ($code === ZipArchive::ER_EXISTS) {
                // CHECKCONS rejects duplicate names; reopen leniently so duplicates() can report them.
                $zip = new ZipArchive;
                $code = $zip->open($path, ZipArchive::RDONLY);
            }
            if ($code !== true) {
                throw new RuntimeException("Cannot open {$path} as a zip archive (ZipArchive error code {$code}).");
            }
            if ($zip->numFiles > $maxEntries) {
                $zip->close();
                throw new BundleLimitExceededException("Bundle has {$zip->numFiles} entries; the limit is {$maxEntries}.");
            }
            for ($i = 0; $i < $zip->numFiles; $i++) {
                $stat = $zip->statIndex($i);
                $name = (string) ($stat['name'] ?? '');
                $raw[] = $name;
                $sizes[$name] = max($sizes[$name] ?? 0, (int) ($stat['size'] ?? 0));
                if (($stat['size'] ?? 0) > $maxEntryBytes) {
                    $zip->close();
                    throw new BundleLimitExceededException("Entry {$name} is larger than {$maxEntryBytes} bytes uncompressed.");
                }
            }
        }

        foreach ($sizes as $name => $size) {
            if ($size > $maxEntryBytes) {
                throw new BundleLimitExceededException("Entry {$name} is larger than {$maxEntryBytes} bytes.");
            }
        }
        if (array_sum($sizes) > $maxTotalBytes) {
            $zip?->close();
            throw new BundleLimitExceededException("Bundle is larger than {$maxTotalBytes} bytes uncompressed.");
        }

        $names = self::filter($raw);
        $prefix = self::rootPrefix($names);
        $files = $dupes = [];
        foreach ($names as $name) {
            if ($prefix !== '') {
                if (! str_starts_with($name, $prefix)) {
                    continue;
                }
                $name = substr($name, strlen($prefix));
            }
            if ($name === '' || str_ends_with($name, '/')) {
                continue;
            }
            if (isset($files[$name])) {
                $dupes[$name] = true;
            }
            $files[$name] = 1;
        }
        ksort($files);

        return new self($zip, $dir, $prefix, $files, array_keys($dupes), $maxLineBytes, $maxEntryBytes, $maxTotalBytes);
    }

    /** @return array<string, mixed>|null */
    public function manifest(): ?array
    {
        if ($this->manifestLoaded) {
            return $this->manifest;
        }
        $this->manifestLoaded = true;
        if (! $this->has(BundleFormat::MANIFEST)) {
            $this->manifestError = 'manifest.json is missing.';

            return null;
        }
        $h = $this->stream(BundleFormat::MANIFEST);
        try {
            $raw = (string) stream_get_contents($h, self::MAX_MANIFEST_BYTES + 1);
        } finally {
            fclose($h);
        }
        if (strlen($raw) > self::MAX_MANIFEST_BYTES) {
            $this->manifestError = 'manifest.json is larger than 1 MB';

            return null;
        }
        $data = json_decode($raw, true);
        if (! is_array($data) || ($data !== [] && array_is_list($data))) {
            $this->manifestError = json_last_error() !== JSON_ERROR_NONE ? json_last_error_msg() : 'manifest.json is not a JSON object.';

            return null;
        }

        return $this->manifest = $data;
    }

    public function manifestError(): ?string
    {
        $this->manifest();

        return $this->manifestError;
    }

    /** @return list<string> relative paths below the bundle root, `/` separators, directories excluded, sorted */
    public function files(): array
    {
        return array_map('strval', array_keys($this->files));
    }

    /** @return list<string> entry names that occur more than once in the zip */
    public function duplicates(): array
    {
        return $this->duplicates;
    }

    public function has(string $file): bool
    {
        return isset($this->files[$file]);
    }

    /** @return string `sha256:<hex>` of the file's bytes, matching the manifest checksum format */
    public function sha256(string $file): string
    {
        $ctx = hash_init('sha256');
        $h = $this->stream($file);
        $read = 0;
        try {
            while (! feof($h)) {
                $chunk = fread($h, 65536);
                if ($chunk === false) {
                    throw new RuntimeException("Cannot read {$file}.");
                }
                $read += strlen($chunk);
                $this->account($file, $read);
                hash_update($ctx, $chunk);
            }
        } finally {
            fclose($h);
        }

        return 'sha256:'.hash_final($ctx);
    }

    /** @return Generator<int, string> 1-based line number => line without "\n"; a final empty line is not yielded */
    public function lines(string $file): Generator
    {
        $h = $this->stream($file);
        $n = 0;
        $read = 0;
        try {
            while (($line = stream_get_line($h, $this->maxLineBytes + 1, "\n")) !== false) {
                $n++;
                if (strlen($line) > $this->maxLineBytes) {
                    throw new BundleLineTooLongException($file, $n, $this->maxLineBytes);
                }
                $read += strlen($line) + 1;
                $this->account($file, $read);
                yield $n => $line;
            }
        } finally {
            fclose($h);
        }
    }

    public function close(): void
    {
        $this->zip?->close();
    }

    private function account(string $file, int $read): void
    {
        if ($read > $this->maxEntryBytes) {
            throw new BundleLimitExceededException("{$file} exceeds {$this->maxEntryBytes} bytes when read.");
        }
        $this->seen[$file] = max($this->seen[$file] ?? 0, $read);
        if (array_sum($this->seen) > $this->maxTotalBytes) {
            throw new BundleLimitExceededException("Bundle exceeds {$this->maxTotalBytes} bytes when read.");
        }
    }

    /** @return resource */
    private function stream(string $file)
    {
        if (! $this->has($file)) {
            throw new RuntimeException("File not in bundle: {$file}");
        }
        if ($this->zip !== null) {
            $h = $this->zip->getStream($this->prefix.$file);
        } else {
            // Names with `..`, a leading `/` or backslashes are listed but never opened.
            if (preg_match('~(^|/)\.\.(/|$)|^/|\\\\~', $file) === 1) {
                throw new RuntimeException("Refusing to open unsafe path: {$file}");
            }
            $h = fopen($this->dir.'/'.$this->prefix.$file, 'rb');
        }
        if ($h === false) {
            throw new RuntimeException("Cannot open {$file}.");
        }

        return $h;
    }

    /**
     * @param  list<string>  $names
     * @return list<string>
     */
    private static function filter(array $names): array
    {
        return array_values(array_filter($names, fn (string $n) => ! str_starts_with($n, '__MACOSX/')
            && basename(rtrim($n, '/')) !== '.DS_Store'));
    }

    /** Unwrap only when everything lives under one directory that holds manifest.json. */
    private static function rootPrefix(array $names): string
    {
        if ($names === [] || in_array(BundleFormat::MANIFEST, $names, true)) {
            return '';
        }
        $roots = [];
        foreach ($names as $name) {
            $pos = strpos($name, '/');
            if ($pos === false || $pos === 0) {
                return '';
            }
            $roots[substr($name, 0, $pos)] = true;
        }
        if (count($roots) !== 1) {
            return '';
        }
        $prefix = array_key_first($roots).'/';

        return in_array($prefix.BundleFormat::MANIFEST, $names, true) ? $prefix : '';
    }
}
