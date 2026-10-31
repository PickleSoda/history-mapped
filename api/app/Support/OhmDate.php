<?php

declare(strict_types=1);

namespace App\Support;

/**
 * OpenHistoricalMap date and identity rules (spec D2, D3).
 *
 * Years stay integers in our data; OHM tiles compare by decimal date, where a
 * year-only start is noon of 1 January (`YYYY + 0.00137`) and a year-only end
 * noon of 31 December (`YYYY + 0.99863`), negative years included. OHM tiles
 * identify features by a signed OSM id: negative for a relation, positive for
 * a node or way. The SQL `tiles.year_to_decdate` and the SPA's
 * `lib/ohm-date.ts` implement the same decimal-date rule.
 */
final class OhmDate
{
    public const START_OFFSET = 0.00137;

    public const END_OFFSET = 0.99863;

    public static function yearToDecdate(int $year, string $bound): float
    {
        return match ($bound) {
            'start' => $year + self::START_OFFSET,
            'end' => $year + self::END_OFFSET,
            default => throw new \InvalidArgumentException("bound must be 'start' or 'end', got '{$bound}'"),
        };
    }

    /** Signed year part of an OHM ISO-8601 date ('-0027-01-16' → -27). Null when absent or unparseable. */
    public static function yearFromDate(?string $date): ?int
    {
        if ($date === null || preg_match('/^\s*(-?\d{1,6})(?:-\d{2}(?:-\d{2})?)?\s*$/', $date, $m) !== 1) {
            return null;
        }

        return (int) $m[1];
    }

    /** @return array{0: ?int, 1: ?int} [start_year, end_year] (inclusive end; see spec D2) */
    public static function yearsFrom(?string $start, ?string $end): array
    {
        return [self::yearFromDate($start), self::yearFromDate($end)];
    }

    public static function signedOsmId(string $externalType, string $externalId): ?int
    {
        if (preg_match('/^\d{1,18}$/', $externalId) !== 1) {
            return null;
        }

        return match ($externalType) {
            'relation' => -(int) $externalId,
            'node', 'way' => (int) $externalId,
            default => null,
        };
    }

    /** @return array{types: list<string>, id: string} */
    public static function externalTypesForSignedId(int $osmId): array
    {
        if ($osmId === 0) {
            throw new \InvalidArgumentException('osm_id must be non-zero');
        }

        return $osmId < 0
            ? ['types' => ['relation'], 'id' => (string) -$osmId]
            : ['types' => ['node', 'way'], 'id' => (string) $osmId];
    }
}
