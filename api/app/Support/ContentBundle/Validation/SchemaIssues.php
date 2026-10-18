<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use Opis\JsonSchema\Errors\ErrorFormatter;
use Opis\JsonSchema\Errors\ValidationError;

/**
 * Turns an opis error tree into one Issue per real problem. Wrapper nodes ("data must match schema", `$ref`,
 * `properties`, `items`) are skipped because a leaf always explains the problem. For `anyOf` (nullable
 * fields, geometry) the `null` branch is dropped when another branch explains the failure, and sibling
 * `required` branches are joined into one message. Common patterns get plain-language messages, unknown keys
 * are named, and enum failures list the allowed values.
 */
final class SchemaIssues
{
    private const MAX_ENUM_SHOWN = 12;

    /** @return list<Issue> */
    public static function map(ValidationError $error, string $layer, ?string $file, ?int $line, ?string $id): array
    {
        $formatter = new ErrorFormatter;
        $issues = [];
        $seen = [];
        foreach (self::collect($error, $formatter, false) as [$field, $message]) {
            if (! isset($seen[$field.'|'.$message])) {
                $seen[$field.'|'.$message] = true;
                $issues[] = Issue::error($layer, $message, $file, $line, $field, $id);
            }
        }

        return $issues;
    }

    /** @return list<array{0: ?string, 1: string, 2?: list<string>}> [field, message, missing keys when a `required` leaf] */
    private static function collect(ValidationError $error, ErrorFormatter $formatter, bool $inThen): array
    {
        $subs = $error->subErrors();
        $keyword = $error->keyword();
        if ($subs === []) {
            return self::leaf($error, $formatter, $inThen);
        }

        if ($keyword === 'anyOf' || $keyword === 'oneOf') {
            $branches = $subs;
            $others = array_values(array_filter($branches, fn (ValidationError $b) => ! self::isNullBranch($b)));
            if ($others !== []) {
                $branches = $others;
            }
            $found = [];
            foreach ($branches as $branch) {
                foreach (self::collect($branch, $formatter, $inThen) as $leaf) {
                    $found[] = $leaf;
                }
            }

            return self::joinRequired($found);
        }

        $found = [];
        foreach ($subs as $sub) {
            foreach (self::collect($sub, $formatter, $inThen || $keyword === 'then') as $leaf) {
                $found[] = $leaf;
            }
        }

        return $found;
    }

    private static function isNullBranch(ValidationError $branch): bool
    {
        return $branch->subErrors() === [] && $branch->keyword() === 'type' && ($branch->args()['expected'] ?? null) === 'null';
    }

    /**
     * Sibling `required` failures at one path (alternatives of an anyOf) become one "needs a or b" message.
     *
     * @param  list<array{0: ?string, 1: string, 2?: list<string>}>  $leaves
     * @return list<array{0: ?string, 1: string, 2?: list<string>}>
     */
    private static function joinRequired(array $leaves): array
    {
        $required = array_values(array_filter($leaves, fn (array $l) => isset($l[2])));
        if (count($required) < 2 || count(array_unique(array_column($required, 0))) !== 1) {
            return $leaves;
        }
        $names = array_unique(array_merge(...array_column($required, 2)));
        $joined = [$required[0][0], 'needs '.implode(' or ', array_map(fn (string $n) => "`{$n}`", $names))];

        return [...array_values(array_filter($leaves, fn (array $l) => ! isset($l[2]))), $joined];
    }

    /** @return list<array{0: ?string, 1: string, 2?: list<string>}> */
    private static function leaf(ValidationError $error, ErrorFormatter $formatter, bool $inThen): array
    {
        $path = $error->data()->fullPath();
        $field = self::pointer($path);
        $keyword = $error->keyword();
        $args = $error->args();
        $schema = $error->schema()->info()->data();

        switch ($keyword) {
            case 'additionalProperties':
                // opis lists every property of the object here whenever a sibling property failed, so work out
                // the genuinely unknown keys from the schema; if there are none this error is only an echo.
                $out = [];
                foreach (self::unknownKeys($error->data()->value(), $schema) as $key) {
                    $out[] = [self::pointer([...$path, $key]), 'unknown key `'.$key.'`'];
                }

                return $out;

            case 'required':
                $missing = array_values(array_map('strval', (array) ($args['missing'] ?? [])));
                $list = implode(', ', array_map(fn (string $n) => "`{$n}`", $missing));
                $message = match (true) {
                    $path === [] && $inThen && $missing === ['id'] => 'a delete (`_op`: "delete") needs `id`',
                    $path === [] && $inThen => "a new record (no id) needs {$list}",
                    default => "missing required key {$list}",
                };

                return [[$field, $message, $missing]];

            case 'enum':
                if (is_object($schema) && isset($schema->enum) && is_array($schema->enum)) {
                    $shown = array_map(fn ($v) => (string) json_encode($v, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), array_slice($schema->enum, 0, self::MAX_ENUM_SHOWN));
                    $more = count($schema->enum) > self::MAX_ENUM_SHOWN ? ', …' : '';
                    $got = mb_strimwidth((string) json_encode($error->data()->value(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE), 0, 60, '…');

                    return [[$field, "invalid value {$got}; allowed: ".implode(', ', $shown).$more]];
                }
                break;

            case 'const':
                if (is_object($schema) && isset($schema->const)) {
                    return [[$field, 'must be `'.(is_string($schema->const) ? $schema->const : json_encode($schema->const)).'`']];
                }
                break;

            case 'pattern':
                $pattern = (string) ($args['pattern'] ?? '');
                $plain = match (true) {
                    str_contains($pattern, '[0-9a-f]{8}-') => 'must be a lowercase UUID',
                    str_starts_with($pattern, '^Q[1-9]') => 'must be a Wikidata id like Q42',
                    $pattern === '^[^\\sA-Z/]+$' => 'must be a slug: lowercase, with no spaces or slashes',
                    default => null,
                };
                if ($plain !== null) {
                    return [[$field, $plain]];
                }
                break;

            case 'minimum':
            case 'maximum':
                $min = is_object($schema) ? ($schema->minimum ?? null) : null;
                $max = is_object($schema) ? ($schema->maximum ?? null) : null;
                if ($min === -20000 && $max === 3000) {
                    return [[$field, 'must be a year between -20000 and 3000']];
                }
                break;

            case 'type':
                if (isset($args['expected'], $args['type'])) {
                    $expected = implode(' or ', (array) $args['expected']);

                    return [[$field, "must be {$expected}, got {$args['type']}"]];
                }
                break;
        }

        return [[$field, $formatter->formatErrorMessage($error)]];
    }

    /** @return list<string> */
    private static function unknownKeys(mixed $value, mixed $schema): array
    {
        if (! is_object($value) || ! is_object($schema)) {
            return [];
        }
        $allowed = isset($schema->properties) && is_object($schema->properties) ? array_map('strval', array_keys((array) $schema->properties)) : [];
        $patterns = isset($schema->patternProperties) && is_object($schema->patternProperties) ? array_map('strval', array_keys((array) $schema->patternProperties)) : [];
        $unknown = [];
        foreach (array_keys((array) $value) as $key) {
            $key = (string) $key;
            if (in_array($key, $allowed, true)) {
                continue;
            }
            foreach ($patterns as $pattern) {
                if (@preg_match('~'.str_replace('~', '\\~', $pattern).'~u', $key) === 1) {
                    continue 2;
                }
            }
            $unknown[] = $key;
        }

        return $unknown;
    }

    /** @param array<int, int|string> $path */
    public static function pointer(array $path): ?string
    {
        if ($path === []) {
            return null;
        }

        return '/'.implode('/', array_map(fn ($s) => str_replace(['~', '/'], ['~0', '~1'], (string) $s), $path));
    }
}
