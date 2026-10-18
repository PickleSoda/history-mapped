<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleFormat;
use App\Support\ContentBundle\BundleLineTooLongException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;

/**
 * Per record file, the set of sha1 hashes of the normalised `_base/` lines, built lazily (only when an error
 * needs the unchanged-line check) by streaming. A bundle line whose bytes hash into the set is "unchanged
 * since export": identical bytes imply an identical id, so no id is stored. Memory is bounded: past
 * $maxLines base lines the whole index is dropped and downgrading is switched off (see overflowed()).
 */
final class BaseIndex
{
    public const MAX_LINES = 500_000;

    /** @var array<string, array<string, true>> */
    private array $sets = [];

    private int $count = 0;

    private bool $overflowed = false;

    public function __construct(private readonly BundleReader $bundle, private readonly int $maxLines = self::MAX_LINES) {}

    /** @param string $file a root record file name such as `entities.jsonl`; $hash is `sha1($line, true)` */
    public function has(string $file, string $hash): bool
    {
        return isset($this->load($file)[$hash]);
    }

    public function overflowed(): bool
    {
        return $this->overflowed;
    }

    public function maxLines(): int
    {
        return $this->maxLines;
    }

    /** @return array<string, true> */
    private function load(string $file): array
    {
        if ($this->overflowed) {
            return [];
        }
        if (isset($this->sets[$file])) {
            return $this->sets[$file];
        }
        $set = [];
        $type = RecordType::fromFile($file);
        $base = BundleFormat::BASE_DIR.'/'.$file;
        if ($type !== null && $this->bundle->has($base)) {
            try {
                foreach ($this->bundle->lines($base) as $line) {
                    if (++$this->count > $this->maxLines) {
                        $this->overflowed = true;
                        $this->sets = [];

                        return [];
                    }
                    $set[sha1($line, true)] = true;
                }
            } catch (BundleLineTooLongException) {
                // The rest of an over-long base file stays unindexed.
            }
        }

        return $this->sets[$file] = $set;
    }
}
