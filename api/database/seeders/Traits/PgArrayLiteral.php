<?php

declare(strict_types=1);

namespace Database\Seeders\Traits;

/**
 * Converts PHP arrays to PostgreSQL array literal syntax.
 *
 * PG text[] columns expect values like: {"val1","val2","val3"}
 * This trait provides helpers for seeders that insert into tables
 * with native PG array columns.
 */
trait PgArrayLiteral
{
    /**
     * Convert a PHP array of strings to a PG text[] literal.
     *
     * @param  string[]|null  $values
     */
    protected function textArray(?array $values): ?string
    {
        if ($values === null || $values === []) {
            return null;
        }

        $escaped = array_map(function (string $value): string {
            // Escape backslashes and double quotes within the value
            $value = str_replace('\\', '\\\\', $value);
            $value = str_replace('"', '\\"', $value);

            return '"'.$value.'"';
        }, $values);

        return '{'.implode(',', $escaped).'}';
    }

    /**
     * Convert a PHP array of integers to a PG integer[] literal.
     *
     * @param  int[]|null  $values
     */
    protected function intArray(?array $values): ?string
    {
        if ($values === null || $values === []) {
            return null;
        }

        return '{'.implode(',', array_map('intval', $values)).'}';
    }
}
