<?php

declare(strict_types=1);

namespace App\Services\Site;

/**
 * Text helpers for the site pages. Years read as they do in the web app
 * (`web/src/lib/format.ts`): "216 BCE", "1066 CE".
 */
final class SiteText
{
    public static function year(int $year): string
    {
        return $year < 0 ? (-$year).' BCE' : $year.' CE';
    }

    /** "490 BCE – 479 BCE", or one year; null when both ends are unknown. */
    public static function span(?int $start, ?int $end): ?string
    {
        if ($start === null && $end === null) {
            return null;
        }
        if ($start !== null && $end !== null && $start !== $end) {
            return self::year($start).' – '.self::year($end);
        }

        return self::year((int) ($start ?? $end));
    }

    /**
     * Prose split on blank lines, as the web app shows it.
     *
     * @return list<string>
     */
    public static function paragraphs(?string $text): array
    {
        $parts = preg_split('/\R\s*\R/u', (string) $text) ?: [];

        return array_values(array_filter(array_map('trim', $parts), fn (string $p): bool => $p !== ''));
    }
}
