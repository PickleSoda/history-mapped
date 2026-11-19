<?php

declare(strict_types=1);

namespace App\Support\Persona;

/**
 * Free text from the atlas ("... which led to the fall of the empire in
 * 1815") can mention a year after the speaker's death. The briefing keeps
 * only text whose every explicit year is at or before the knowledge year.
 */
final class AnachronismGuard
{
    /** @return list<int> Years named in the text (BCE as negative). */
    public static function yearsIn(string $text): array
    {
        $years = [];
        if (preg_match_all('/\b(\d{1,4})\s*(BCE|BC|B\.C\.E?\.?)/i', $text, $m)) {
            foreach ($m[1] as $y) {
                $years[] = -(int) $y;
            }
        }
        // Bare 3-4 digit numbers, not already a BCE year: CE years.
        $stripped = preg_replace('/\b\d{1,4}\s*(BCE|BC|B\.C\.E?\.?)/i', ' ', $text) ?? $text;
        if (preg_match_all('/(?<![\d.\-])(?<!\d,)(\d{3,4})(?!\d)(?!,\d{3})/', $stripped, $m)) {
            foreach ($m[1] as $y) {
                $years[] = (int) $y;
            }
        }

        return $years;
    }

    public static function isSafe(string $text, int $knowledgeYear): bool
    {
        foreach (self::yearsIn($text) as $year) {
            if ($year > $knowledgeYear) {
                return false;
            }
        }

        return true;
    }

    /** The text cut to its first sentence(s) within `$max` characters, or null when unsafe. */
    public static function snippet(?string $text, int $knowledgeYear, int $max = 140): ?string
    {
        $text = trim((string) $text);
        if ($text === '' || ! self::isSafe($text, $knowledgeYear)) {
            return null;
        }
        $text = preg_replace('/\s+/', ' ', $text) ?? $text;
        if (mb_strlen($text) <= $max) {
            return $text;
        }
        $cut = mb_substr($text, 0, $max);
        $dot = mb_strrpos($cut, '. ');
        if ($dot !== false && $dot > 40) {
            return mb_substr($cut, 0, $dot + 1);
        }

        return rtrim(mb_substr($cut, 0, mb_strrpos($cut, ' ') ?: $max), ',;: ').'…';
    }
}
