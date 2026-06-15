<?php

declare(strict_types=1);

namespace App\Casts;

use Illuminate\Contracts\Database\Eloquent\CastsAttributes;
use Illuminate\Database\Eloquent\Model;

/**
 * Cast a PostgreSQL integer[] column to/from a PHP int array.
 *
 * PostgreSQL stores integer arrays as `{1,2,3}` which is NOT JSON.
 * Laravel's built-in 'array' cast uses json_encode/json_decode, which fails
 * on PG array literal syntax.
 *
 * get(): `{1,2,3}` -> [1, 2, 3]
 * set(): [1, 2, 3] -> `{1,2,3}`
 */
class PgIntArray implements CastsAttributes
{
    /**
     * Parse a PostgreSQL integer[] literal into a PHP int array.
     *
     * @param  array<string, mixed>  $attributes
     * @return list<int>|null
     */
    public function get(Model $model, string $key, mixed $value, array $attributes): ?array
    {
        if ($value === null || $value === '{}') {
            return $value === '{}' ? [] : null;
        }

        // Strip outer braces: {1,2,3} -> 1,2,3
        $inner = substr($value, 1, -1);

        return array_map('intval', explode(',', $inner));
    }

    /**
     * Convert a PHP int array to a PostgreSQL integer[] literal.
     *
     * @param  array<string, mixed>  $attributes
     */
    public function set(Model $model, string $key, mixed $value, array $attributes): ?string
    {
        if ($value === null) {
            return null;
        }

        if (is_array($value) && count($value) === 0) {
            return '{}';
        }

        return '{'.implode(',', array_map('intval', $value)).'}';
    }
}
