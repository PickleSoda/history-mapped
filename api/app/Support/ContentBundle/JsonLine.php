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
     * Decode a raw jsonb string keeping objects as stdClass, so a nested `{}` is not turned into `[]`.
     * Feed it `$model->getRawOriginal(col)`, never the model's `array` cast.
     */
    public static function decodeJsonb(?string $raw): mixed
    {
        return $raw === null ? null : json_decode($raw, false, 512, JSON_THROW_ON_ERROR);
    }

    /**
     * For object-typed jsonb columns: a top-level empty value (`[]` or an empty stdClass) is emitted as
     * `{}`. Nested values are left exactly as the DB holds them. Part 2's hashing must treat `[]` and
     * `{}` as equal for these columns, because the DB may hold either (e.g. `entity_geo_refs.external_tags`).
     */
    public static function object(mixed $value): mixed
    {
        return $value === [] ? (object) [] : $value;
    }
}
