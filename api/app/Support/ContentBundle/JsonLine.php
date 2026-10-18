<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

/**
 * The single JSON encoding used for bundle lines, so identical records always produce identical bytes.
 */
final class JsonLine
{
    private const FLAGS = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR;

    /**
     * Encode one record as a single line, without a trailing newline. Key order is preserved.
     *
     * @param  array<string, mixed>  $record
     */
    public static function encode(array $record): string
    {
        return json_encode($record, self::FLAGS);
    }

    /**
     * For object-typed jsonb columns: PHP decodes `{}` to `[]`, so an empty value is cast back to an
     * object. Part 2's hashing must treat `[]` and `{}` as equal for these columns, because the DB may
     * hold either (e.g. `entity_geo_refs.external_tags`).
     *
     * @param  array<array-key, mixed>|null  $value
     * @return array<array-key, mixed>|object|null
     */
    public static function object(?array $value): array|object|null
    {
        return $value === [] ? (object) [] : $value;
    }
}
