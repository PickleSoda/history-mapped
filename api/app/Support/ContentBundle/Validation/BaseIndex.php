<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use App\Support\ContentBundle\BundleFormat;
use App\Support\ContentBundle\BundleLineTooLongException;
use App\Support\ContentBundle\BundleReader;
use App\Support\ContentBundle\RecordType;

/**
 * Per record file, record id => sha1 of the raw `_base/` line, built lazily (only when an error needs
 * the unchanged-line check) by streaming. A line is "unchanged since export" when its bytes equal the
 * base line with the same id. The index is bounded; ids past the bound are simply never unchanged.
 */
final class BaseIndex
{
    public const MAX_ENTRIES = 2_000_000;

    /** @var array<string, array<string, string>> */
    private array $index = [];

    private int $count = 0;

    public function __construct(private readonly BundleReader $bundle) {}

    public function isUnchanged(RecordType $type, string $id, string $rawLine): bool
    {
        $hash = ($this->load($type))[$id] ?? null;

        return $hash !== null && hash_equals($hash, sha1($rawLine, true));
    }

    /** @return array<string, string> */
    private function load(RecordType $type): array
    {
        if (isset($this->index[$type->value])) {
            return $this->index[$type->value];
        }
        $map = [];
        $file = BundleFormat::BASE_DIR.'/'.$type->file();
        if ($this->bundle->has($file)) {
            try {
                foreach ($this->bundle->lines($file) as $line) {
                    $id = self::idOf($line);
                    if ($id === null) {
                        continue;
                    }
                    if ($this->count >= self::MAX_ENTRIES) {
                        break;
                    }
                    $this->count++;
                    $map[$id] = sha1($line, true);
                }
            } catch (BundleLineTooLongException) {
                // The rest of an over-long base file stays unindexed.
            }
        }

        return $this->index[$type->value] = $map;
    }

    private static function idOf(string $line): ?string
    {
        if (preg_match('/\A\{"id":"([^"\\\\]{1,64})"/', $line, $m) === 1) {
            return $m[1];
        }
        $data = json_decode($line);

        return is_object($data) && isset($data->id) && is_string($data->id) ? $data->id : null;
    }
}
