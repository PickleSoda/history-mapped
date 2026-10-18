<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Serializers;

use App\Support\ContentBundle\JsonLine;
use Illuminate\Database\Eloquent\Model;

/**
 * Reads values off Eloquent models for bundle lines, bypassing casts so what is exported is what the
 * DB holds. Every reader throws if its column was not selected, so a dropped column cannot silently
 * export null.
 */
final class Values
{
    /**
     * Raw stored value of a column, bypassing casts (so an unknown enum string is exported as-is).
     * Throws if the column was not selected.
     *
     * Types are whatever PDO returns for the column: int, float8 and bool come back native, but
     * `numeric` (e.g. `match_score`) comes back as a string, so cast it where a JSON number is wanted.
     */
    public static function raw(Model $model, string $column): mixed
    {
        $original = $model->getRawOriginal();
        if (! array_key_exists($column, $original)) {
            throw new \LogicException(sprintf('Column %s.%s was not selected.', $model->getTable(), $column));
        }

        return $original[$column];
    }

    /** A non-object jsonb column (list, scalar or any JSON value), decoded from the raw string. */
    public static function jsonb(Model $model, string $column): mixed
    {
        $raw = self::raw($model, $column);
        if ($raw !== null && ! is_string($raw)) {
            throw new \LogicException(sprintf('Column %s.%s is not a raw jsonb string.', $model->getTable(), $column));
        }

        return self::decodeJsonb($raw);
    }

    /** An object-typed jsonb column: decoded from the raw string, top-level empty becomes `{}`. */
    public static function jsonbObject(Model $model, string $column): mixed
    {
        return self::object(self::jsonb($model, $column));
    }

    /**
     * GeoJSON of a geometry column, from the pre-selected `<col>_geojson` alias. Requiring the alias
     * (rather than the GeoJson cast) means a mistyped select throws instead of exporting null geometry.
     *
     * @return array<string, mixed>|null
     */
    public static function geojson(Model $model, string $column): ?array
    {
        $raw = self::raw($model, $column.'_geojson');

        return $raw === null ? null : json_decode((string) $raw, true, 512, JSON_THROW_ON_ERROR);
    }

    /**
     * Decode a raw jsonb string keeping objects as stdClass, so a nested `{}` is not turned into `[]`.
     * Feed it a raw column value, never the model's `array` cast.
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

            return strcmp(JsonLine::encode($a), JsonLine::encode($b));
        });

        return $items;
    }
}
