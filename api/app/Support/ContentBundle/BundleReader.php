<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use Generator;
use RuntimeException;
use ZipArchive;

/**
 * Reads a bundle from a zip or a directory without ever extracting to disk. Zip entries are read through
 * ZipArchive streams; entry names are only compared as strings, never resolved against the filesystem.
 * Hostile names (absolute, `..`, backslashes) are listed by files() unchanged so the validator can flag them,
 * but cannot be read from a directory bundle. A single wrapper directory holding manifest.json is the root.
 * Lines longer than the limit (default 8 MB) make lines() throw BundleLineTooLongException.
 */
final class BundleReader
{
    public const MAX_LINE_BYTES = 8 * 1024 * 1024;

    private ?string $manifestError = null;

    private function __construct(
        private readonly ?ZipArchive $zip,
        private readonly string $dir,
        private readonly string $prefix,
        private readonly int $maxLineBytes,
    ) {}

    public static function open(string $path, int $maxLineBytes = self::MAX_LINE_BYTES): self
    {
        if (is_dir($path)) {
            $names = self::listDir(rtrim($path, '/'));
            $dir = rtrim($path, '/');

            return new self(null, $dir, self::rootPrefix($names), $maxLineBytes);
        }
        if (! is_file($path)) {
            throw new RuntimeException("Bundle not found: {$path}");
        }
        $zip = new ZipArchive;
        if ($zip->open($path, ZipArchive::RDONLY) !== true) {
            throw new RuntimeException("Cannot open {$path} as a zip archive.");
        }
        $names = [];
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $names[] = (string) $zip->getNameIndex($i);
        }

        return new self($zip, '', self::rootPrefix(self::filter($names)), $maxLineBytes);
    }

    /** @return array<string, mixed>|null */
    public function manifest(): ?array
    {
        $this->manifestError = null;
        if (! $this->has(BundleFormat::MANIFEST)) {
            $this->manifestError = 'manifest.json is missing.';

            return null;
        }
        $raw = '';
        foreach ($this->lines(BundleFormat::MANIFEST, true) as $line) {
            $raw .= $line."\n";
        }
        $data = json_decode($raw, true);
        if (! is_array($data) || array_is_list($data) && $data !== []) {
            $this->manifestError = json_last_error() !== JSON_ERROR_NONE ? json_last_error_msg() : 'manifest.json is not a JSON object.';

            return null;
        }

        return $data;
    }

    public function manifestError(): ?string
    {
        return $this->manifestError;
    }

    /** @return list<string> relative paths below the bundle root, `/` separators, directories excluded */
    public function files(): array
    {
        $names = $this->zip !== null ? $this->zipNames() : self::listDir($this->dir);
        $out = [];
        foreach (self::filter($names) as $name) {
            if ($this->prefix !== '') {
                if (! str_starts_with($name, $this->prefix)) {
                    continue;
                }
                $name = substr($name, strlen($this->prefix));
            }
            if ($name !== '' && ! str_ends_with($name, '/')) {
                $out[] = $name;
            }
        }
        sort($out);

        return $out;
    }

    public function has(string $file): bool
    {
        return in_array($file, $this->files(), true);
    }

    /** @return string `sha256:<hex>` of the file's bytes, matching the manifest checksum format */
    public function sha256(string $file): string
    {
        $ctx = hash_init('sha256');
        $h = $this->stream($file);
        try {
            while (! feof($h)) {
                $chunk = fread($h, 65536);
                if ($chunk === false) {
                    throw new RuntimeException("Cannot read {$file}.");
                }
                hash_update($ctx, $chunk);
            }
        } finally {
            fclose($h);
        }

        return 'sha256:'.hash_final($ctx);
    }

    /** @return Generator<int, string> 1-based line number => line without "\n"; a final empty line is not yielded */
    public function lines(string $file, bool $unbounded = false): Generator
    {
        $h = $this->stream($file);
        $n = 0;
        try {
            while (($chunk = fgets($h, $this->maxLineBytes + 2)) !== false) {
                $n++;
                $terminated = str_ends_with($chunk, "\n");
                if (! $unbounded && strlen($chunk) > $this->maxLineBytes && ! ($terminated && strlen($chunk) === $this->maxLineBytes + 1)) {
                    throw new BundleLineTooLongException($file, $n, $this->maxLineBytes);
                }
                yield $n => $terminated ? substr($chunk, 0, -1) : $chunk;
            }
        } finally {
            fclose($h);
        }
    }

    public function close(): void
    {
        $this->zip?->close();
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

    /** @return list<string> */
    private function zipNames(): array
    {
        $names = [];
        for ($i = 0; $i < $this->zip->numFiles; $i++) {
            $names[] = (string) $this->zip->getNameIndex($i);
        }

        return $names;
    }

    /** @return list<string> */
    private static function listDir(string $dir): array
    {
        $out = [];
        $iter = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS));
        foreach ($iter as $info) {
            if ($info->isFile() && ! $info->isLink()) {
                $out[] = str_replace(DIRECTORY_SEPARATOR, '/', substr($info->getPathname(), strlen($dir) + 1));
            }
        }

        return $out;
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

    /** @param list<string> $names */
    private static function rootPrefix(array $names): string
    {
        $names = self::filter($names);
        if (in_array(BundleFormat::MANIFEST, $names, true)) {
            return '';
        }
        $roots = [];
        foreach ($names as $name) {
            if (preg_match('~^([^/]+)/'.preg_quote(BundleFormat::MANIFEST, '~').'$~', $name, $m)) {
                $roots[$m[1]] = true;
            }
        }

        return count($roots) === 1 ? array_key_first($roots).'/' : '';
    }
}
