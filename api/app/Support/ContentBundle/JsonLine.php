<?php

declare(strict_types=1);

namespace App\Support\ContentBundle;

use Illuminate\Database\Eloquent\Model;

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

    /**
     * Raw stored value of a column, bypassing casts (so an unknown enum string is exported as-is).
     * Throws if the column was not selected, so a dropped column cannot silently export null.
     */
    public static function raw(Model $model, string $column): mixed
    {
        if (! array_key_exists($column, $model->getAttributes())) {
            throw new \LogicException(sprintf('Column %s.%s was not selected.', $model->getTable(), $column));
        }

        return $model->getRawOriginal($column);
    }

    /** A non-object jsonb column (list or scalar), decoded from the raw string. */
    public static function jsonb(Model $model, string $column): mixed
    {
        $raw = self::raw($model, $column);

        return self::decodeJsonb(is_string($raw) ? $raw : null);
    }

    /** An object-typed jsonb column: decoded from the raw string, top-level empty becomes `{}`. */
    public static function jsonbObject(Model $model, string $column): mixed
    {
        return self::object(self::jsonb($model, $column));
    }

    /**
     * Deterministic order for nested lists. `$key` returns a list of bool|int|string parts (map nulls
     * yourself, e.g. `[$v === null, $v ?? '']` for nulls-last). Strings compare with strcmp, never `<=>`;
     * remaining ties break on the encoded item, so physical row order never matters.
     *
     * @template T of array<string, mixed>
     *
     * @param  list<T>  $items
     * @param  callable(T): list<bool|int|string>  $key
     * @return list<T>
     */
    public static function sortList(array $items, callable $key): array
    {
        usort($items, function (array $a, array $b) use ($key): int {
            foreach (array_map(null, $key($a), $key($b)) as [$x, $y]) {
                $c = is_string($x) ? strcmp($x, (string) $y) : $x <=> $y;
                if ($c !== 0) {
                    return $c;
                }
            }

            return strcmp(self::encode($a), self::encode($b));
        });

        return $items;
    }
}
