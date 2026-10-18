<?php

declare(strict_types=1);

namespace App\Support\ContentBundle\Validation;

use Opis\JsonSchema\Errors\ErrorFormatter;
use Opis\JsonSchema\Errors\ValidationError;

/**
 * Turns an opis error tree into one Issue per leaf. Parent "data must match schema" wrappers are skipped
 * because a leaf always explains the problem; unknown keys are named; enum failures list the allowed values.
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
        self::walk($error, $formatter, function (?string $field, string $message) use (&$issues, &$seen, $layer, $file, $line, $id) {
            if (! isset($seen[$field.'|'.$message])) {
                $seen[$field.'|'.$message] = true;
                $issues[] = Issue::error($layer, $message, $file, $line, $field, $id);
            }
        });

        return $issues;
    }

    /** @param callable(?string, string): void $emit */
    private static function walk(ValidationError $error, ErrorFormatter $formatter, callable $emit): void
    {
        $subs = $error->subErrors();
        if ($subs !== []) {
            foreach ($subs as $sub) {
                self::walk($sub, $formatter, $emit);
            }

            return;
        }

        $path = $error->data()->fullPath();
        $info = $error->schema()->info()->data();

        if ($error->keyword() === 'additionalProperties') {
            // opis lists every property of the object here whenever a sibling property failed, so work out
            // the genuinely unknown keys from the schema; if there are none this error is only an echo.
            foreach (self::unknownKeys($error->data()->value(), $info) as $key) {
                $emit(self::pointer([...$path, $key]), 'unknown key `'.$key.'`');
            }

            return;
        }

        $message = $formatter->formatErrorMessage($error);
        if ($error->keyword() === 'enum' && is_object($info) && isset($info->enum) && is_array($info->enum)) {
            $shown = array_map(fn ($v) => (string) json_encode($v, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), array_slice($info->enum, 0, self::MAX_ENUM_SHOWN));
            $more = count($info->enum) > self::MAX_ENUM_SHOWN ? ', …' : '';
            $got = mb_strimwidth((string) json_encode($error->data()->value(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE), 0, 60, '…');
            $message = "invalid value {$got}; allowed: ".implode(', ', $shown).$more;
        }
        $emit(self::pointer($path), $message);
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
