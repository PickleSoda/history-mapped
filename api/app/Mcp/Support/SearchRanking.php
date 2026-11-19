<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use Illuminate\Support\Str;

/**
 * How the MCP name search orders its candidates: the most historically
 * important close match first, not the closest spelling.
 *
 *   score = 100 * match quality + impact score (0-100)
 *
 * Match quality is a tier, so a weak match cannot buy its way up with impact
 * (the range of impact among real hits is about 45-98):
 *
 *   1.00  the whole name equals the query ("Hastings")
 *   0.90  the name starts with the query as whole words ("Napoleon III")
 *   0.80  the query is whole words inside the name ("Battle of Hastings")
 *   0.45  the name starts with the query as part of a word ("Napoleonic Wars")
 *   0.40  a later word starts with it ("Kingdom of Italy (Napoleonic)")
 *   0.20  it appears inside a word ("Wyoming" for "ming")
 *   else  trigram similarity x 1.5, at most 0.75, for typos ("napolean" finds Napoleon)
 *
 * A whole-word match inside a name of four or more words that is at least
 * four times as long as the query is a sentence, not a name ("Caesar releases
 * Aristobulus II"): it loses 0.3, so "Julius Caesar" outranks it.
 *
 * A name shared by several candidates is a namesake name, not the one famous
 * thing: an exact match loses 0.05 per extra entity with that exact name, to
 * at most 0.2. Ten people called "Alexander" thus rank below "Alexander the
 * Great", while a name carried by one or two entities keeps its exact bonus.
 *
 * Pure: no database; the candidates come from EntitySearch.
 */
final class SearchRanking
{
    public const QUALITY_WEIGHT = 100;

    /** Impact for a row that has none, a little under the median (49). */
    public const DEFAULT_IMPACT = 40;

    private const SENTENCE_PENALTY = 0.3;

    private const NAMESAKE_PENALTY = 0.05;

    private const NAMESAKE_PENALTY_MAX = 0.2;

    /** Lowercase, accents and punctuation folded away, single spaces. */
    public static function normalize(string $text): string
    {
        $ascii = Str::lower(Str::ascii($text));

        return trim((string) preg_replace('/[^a-z0-9]+/', ' ', $ascii));
    }

    /** Match quality of one name for a query, 0 to 1 (see the class docblock). */
    public static function quality(string $name, string $query): float
    {
        $n = self::normalize($name);
        $q = self::normalize($query);
        if ($q === '' || $n === '') {
            return 0.0;
        }
        if ($n === $q) {
            return 1.0;
        }
        $wholeWords = str_starts_with($n, $q.' ') ? 0.9 : (str_contains(' '.$n.' ', ' '.$q.' ') ? 0.8 : null);
        if ($wholeWords !== null) {
            $words = substr_count($n, ' ') + 1;
            $queryWords = substr_count($q, ' ') + 1;

            return $words >= 4 && $words >= 4 * $queryWords ? $wholeWords - self::SENTENCE_PENALTY : $wholeWords;
        }
        if (str_starts_with($n, $q)) {
            return 0.45;
        }
        if (str_contains(' '.$n, ' '.$q)) {
            return 0.4;
        }
        if (str_contains($n, $q)) {
            return 0.2;
        }

        return round(min(0.75, self::similarity($n, $q) * 1.5), 4);
    }

    /** pg_trgm's similarity(): Jaccard of the two trigram sets, words padded. */
    public static function similarity(string $a, string $b): float
    {
        $ta = self::trigrams($a);
        $tb = self::trigrams($b);
        if ($ta === [] || $tb === []) {
            return 0.0;
        }
        $shared = count(array_intersect_key($ta, $tb));

        return $shared / (count($ta) + count($tb) - $shared);
    }

    /**
     * Candidates best first. Ties keep the order they came in (the stable
     * sort), which is the database's similarity order.
     *
     * @template T
     *
     * @param  list<T>  $candidates
     * @param  callable(T): string  $name
     * @param  callable(T): (int|float|null)  $impact
     * @return list<T>
     */
    public static function rank(array $candidates, string $query, callable $name, callable $impact): array
    {
        $exact = [];
        foreach ($candidates as $c) {
            $key = self::normalize($name($c));
            $exact[$key] = ($exact[$key] ?? 0) + 1;
        }
        $q = self::normalize($query);

        $scored = [];
        foreach ($candidates as $i => $c) {
            $quality = self::quality($name($c), $query);
            if ($quality === 1.0) {
                $quality -= min(self::NAMESAKE_PENALTY_MAX, self::NAMESAKE_PENALTY * (($exact[$q] ?? 1) - 1));
            }
            $scored[] = [self::QUALITY_WEIGHT * $quality + ($impact($c) ?? self::DEFAULT_IMPACT), -$i, $c];
        }
        usort($scored, fn (array $x, array $y): int => [$y[0], $y[1]] <=> [$x[0], $x[1]]);

        return array_map(fn (array $s) => $s[2], $scored);
    }

    /** @return array<string, true> */
    private static function trigrams(string $text): array
    {
        $set = [];
        foreach (explode(' ', $text) as $word) {
            if ($word === '') {
                continue;
            }
            $padded = '  '.$word.' ';
            for ($i = 0, $n = strlen($padded) - 2; $i < $n; $i++) {
                $set[substr($padded, $i, 3)] = true;
            }
        }

        return $set;
    }
}
