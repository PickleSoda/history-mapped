<?php

declare(strict_types=1);

namespace App\Casts;

use Illuminate\Contracts\Database\Eloquent\CastsAttributes;
use Illuminate\Database\Eloquent\Model;

/**
 * Cast a PostgreSQL text[] column to/from a PHP string array.
 *
 * PostgreSQL stores text arrays as `{"val1","val2","val3"}` which is NOT JSON.
 * Laravel's built-in 'array' cast uses json_encode/json_decode, which fails
 * on PG array literal syntax.
 *
 * get(): `{"foo","bar"}` -> ['foo', 'bar']
 * set(): ['foo', 'bar'] -> `{"foo","bar"}`
 */
class PgTextArray implements CastsAttributes
{
    /**
     * Parse a PostgreSQL text[] literal into a PHP string array.
     *
     * @param  array<string, mixed>  $attributes
     * @return list<string>|null
     */
    public function get(Model $model, string $key, mixed $value, array $attributes): ?array
    {
        if ($value === null || $value === '{}') {
            return $value === '{}' ? [] : null;
        }

        // Strip outer braces: {"foo","bar"} -> "foo","bar"
        $inner = substr($value, 1, -1);

        return self::parsePgArray($inner);
    }

    /**
     * Convert a PHP string array to a PostgreSQL text[] literal.
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

        $escaped = array_map(static function (string $item): string {
            // Escape backslashes and double-quotes, then wrap in double-quotes.
            $item = str_replace('\\', '\\\\', $item);
            $item = str_replace('"', '\\"', $item);

            return '"'.$item.'"';
        }, $value);

        return '{'.implode(',', $escaped).'}';
    }

    /**
     * Parse the inner content of a PG text[] literal into a PHP array.
     *
     * Handles quoted strings with escaped characters: "foo","bar \"baz\""
     *
     * @return list<string>
     */
    private static function parsePgArray(string $inner): array
    {
        $result = [];
        $len = strlen($inner);
        $i = 0;

        while ($i < $len) {
            if ($inner[$i] === '"') {
                // Quoted element — scan to closing unescaped quote
                $i++; // skip opening quote
                $element = '';
                while ($i < $len) {
                    if ($inner[$i] === '\\' && $i + 1 < $len) {
                        $element .= $inner[$i + 1];
                        $i += 2;
                    } elseif ($inner[$i] === '"') {
                        $i++; // skip closing quote
                        break;
                    } else {
                        $element .= $inner[$i];
                        $i++;
                    }
                }
                $result[] = $element;
            } elseif ($inner[$i] === ',') {
                $i++; // skip comma separator
            } else {
                // Unquoted element (NULL or bare string) — scan to comma or end
                $end = strpos($inner, ',', $i);
                $element = $end === false ? substr($inner, $i) : substr($inner, $i, $end - $i);
                $i = $end === false ? $len : $end;

                $result[] = $element === 'NULL' ? '' : $element;
            }
        }

        return $result;
    }
}
