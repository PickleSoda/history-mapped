<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use App\Enums\EntityType;

/**
 * Small text helpers shared by the tools: trimming prose for a model's
 * context window, years as words, and readable names for enum values.
 */
final class Text
{
    /**
     * Cut at a word boundary within `$max` characters, with an ellipsis when cut.
     * Whitespace is collapsed first, so a summary never carries blank lines.
     */
    public static function limit(?string $text, int $max): ?string
    {
        if ($text === null) {
            return null;
        }
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        if ($text === '') {
            return null;
        }
        if (mb_strlen($text) <= $max) {
            return $text;
        }

        $cut = mb_substr($text, 0, $max - 1);
        $space = mb_strrpos($cut, ' ');
        if ($space !== false && $space > $max * 0.6) {
            $cut = mb_substr($cut, 0, $space);
        }

        return rtrim($cut, ' ,;:-–—').'…';
    }

    /** First sentence of a passage, for a heading; cut to `$max` characters. */
    public static function firstSentence(string $text, int $max = 80): string
    {
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        $sentence = preg_match('/^(.+?[.!?])(\s|$)/u', $text, $m) === 1 ? $m[1] : $text;

        return (string) self::limit(rtrim($sentence, '.'), $max);
    }

    /** `governed_by` becomes "governed by". */
    public static function humanize(string $value): string
    {
        return str_replace('_', ' ', $value);
    }

    /** `event_battle` becomes "Battle", `political_entity` "Political entity". */
    public static function typeLabel(EntityType|string|null $type): ?string
    {
        if ($type === null) {
            return null;
        }
        $value = $type instanceof EntityType ? $type->value : $type;

        return ucfirst(self::humanize(str_starts_with($value, 'event_') ? substr($value, 6) : $value));
    }

    /**
     * A signed year as words. `$withEra` adds "AD" to a positive year, for a
     * range that starts BC ("44 BC–AD 14").
     */
    public static function year(int $year, bool $withEra = false): string
    {
        if ($year < 0) {
            return (-$year).' BC';
        }

        return ($withEra ? 'AD ' : '').$year;
    }

    /**
     * "1769–1821", "44 BC", "c. 3000 BC–2686 BC"; null when both ends are unknown.
     * A start without an end reads "from 1066" (still going, or unrecorded).
     */
    public static function dateLabel(?int $start, ?int $end, bool $approximate = false): ?string
    {
        if ($start === null && $end === null) {
            return null;
        }
        $c = $approximate ? 'c. ' : '';

        if ($start === null) {
            return $c.'until '.self::year((int) $end);
        }
        if ($end === null) {
            return $c.'from '.self::year($start);
        }
        if ($start === $end) {
            return $c.self::year($start);
        }

        $era = $start < 0 && $end > 0;

        return $c.self::year($start).'–'.self::year($end, $era);
    }
}
