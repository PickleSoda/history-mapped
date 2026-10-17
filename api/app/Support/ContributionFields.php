<?php

declare(strict_types=1);

namespace App\Support;

use App\Models\Entity;
use Illuminate\Database\Eloquent\Model;

/**
 * How a contribution reads and compares one editable field.
 *
 * Most fields are a column holding text. *List fields* (entity `aliases`) are
 * stored as rows and edited as one item per line; their text form is
 * normalised — trimmed, de-duplicated case-insensitively, sorted — so a diff
 * only ever shows real additions and removals, never reordering.
 */
final class ContributionFields
{
    /** @var list<string> */
    public const LIST_FIELDS = ['aliases'];

    /** @var list<string> One-line fields that must stay non-empty. */
    public const LINE_FIELDS = ['name', 'title'];

    public static function isList(string $field): bool
    {
        return in_array($field, self::LIST_FIELDS, true);
    }

    public static function isLine(string $field): bool
    {
        return in_array($field, self::LINE_FIELDS, true);
    }

    /** The field's live value on the target, in normalised text form. */
    public static function read(Model $target, string $field): string
    {
        if ($field === 'aliases' && $target instanceof Entity) {
            return self::listText($target->aliases()->pluck('name'));
        }

        return self::normalise($field, (string) ($target->getAttribute($field) ?? ''));
    }

    /** Canonical text form of a submitted or stored value. */
    public static function normalise(string $field, string $text): string
    {
        $text = TextDiff::normalise($text);

        return match (true) {
            self::isList($field) => self::listText(explode("\n", $text)),
            self::isLine($field) => trim($text),
            default => $text,
        };
    }

    /** True when the two values are the same once normalised. */
    public static function same(string $field, string $a, string $b): bool
    {
        return self::normalise($field, $a) === self::normalise($field, $b);
    }

    /** Diff of two normalised values — line by line for list fields. */
    public static function diff(string $field, string $from, string $to): array
    {
        return TextDiff::compute($from, $to, byLine: self::isList($field));
    }

    /** True when a submitted value changes nothing (surrounding whitespace aside). */
    public static function unchanged(string $field, string $current, string $proposed): bool
    {
        return trim(self::normalise($field, $current)) === trim(self::normalise($field, $proposed));
    }

    /**
     * The items of a list field's text form.
     *
     * @return list<string>
     */
    public static function listItems(string $text): array
    {
        return $text === '' ? [] : explode("\n", $text);
    }

    /**
     * Trim, drop blanks, keep the first spelling of case-insensitive
     * duplicates, sort case-insensitively, one item per line.
     *
     * @param  iterable<mixed>  $items
     */
    public static function listText(iterable $items): string
    {
        $trimmed = [];
        foreach ($items as $item) {
            $item = trim((string) $item);
            if ($item !== '') {
                $trimmed[] = $item;
            }
        }
        // Byte order (not the DB collation) before de-duplicating, so "first
        // spelling wins" is deterministic and matches the SPA's code-unit sort.
        sort($trimmed, SORT_STRING);

        $unique = [];
        foreach ($trimmed as $item) {
            $unique[mb_strtolower($item)] ??= $item;
        }
        ksort($unique, SORT_STRING);

        return implode("\n", $unique);
    }
}
