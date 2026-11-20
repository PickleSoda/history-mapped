<?php

declare(strict_types=1);

namespace App\Actions\Discover;

use App\Support\Discover\DiscoverEntities;
use Illuminate\Support\Facades\DB;

/**
 * Rebuild `discover_anniversaries`, the table GET /discover/on-this-day reads
 * (migration 2026_11_20_200000): delete and insert in one transaction, then
 * forget the cached days.
 *
 * Two sources; a row from the first wins.
 *
 *   1. Primary date ranges whose text has a real day (`1815-11-20`,
 *      `-0753-04-21`): a valid month and day, a start that is not 1 January
 *      and an end that is not 1 January or 31 December (those stand for
 *      "some time that year"). The kind follows the entity:
 *
 *        person         born (start), died (end)
 *        event          happened (starts and ends that day, or has no end),
 *                       began / ended (its first / last day when they differ)
 *        anything else  founded (start), dissolved (end, when it is not
 *                       the same day: a law enacted on a day did not also
 *                       end on it)
 *
 *   2. People's `attributes.birth_date` / `death_date` at or above
 *      `discover.anniversaries.people_min_impact`: Wikidata timestamps
 *      (`1925-11-20T00:00:00Z`), 1 January left out. Wikidata numbers years
 *      astronomically (`-0042` is 43 BCE), so the year is shifted to ours and
 *      `date` is written in the form of source 1 (`-0043-03-20`). A value
 *      that lists several dates is left out: the day is not known.
 *
 * A date on the 1st of a month is kept only when the entity's summary states
 * that day ("1 March 1810", "June 1, 1968"), in both sources. A date known
 * only to the month is stored as its 1st, the way a year is stored as
 * 1 January, and nothing tells the two apart: the 1st holds about twice the
 * rows of any other day in source 1 (three to four times for foundings and
 * dissolutions) and a fifth more in source 2 (Anne Frank "died 1 February
 * 1945": February or March, the day is not known). The summaries confirm
 * three in four of the people's dates and one in six of the others.
 * `discover.anniversaries.first_of_month` can keep them all (`all`) or drop
 * them all (`none`).
 *
 * Only people known to have died get a `born` row, in both sources: a
 * `death_date` attribute, or for source 1 an end year. The end year of a bulk
 * Wikidata person is not always a death (a living writer's last work), so
 * source 2 trusts the attribute alone.
 *
 * `impact` and `placed` (a primary point or a geometry period) are copied in
 * so a day is ordered from the index without a join. Rows are written in
 * calendar order, so a day's 200 rows sit on a few pages instead of 170.
 * Entities in a status the atlas hides are left out.
 *
 * This is the one place that reads every person's attributes (about 3 s
 * locally, tens of seconds on the droplet): run it weekly and after a
 * content load, never in a request.
 */
class BuildAnniversariesAction
{
    private const DAY_DATE = '^-?\d{1,6}-\d{2}-\d{2}$';

    /** A valid month and day, and not 1 January. */
    private const REAL_DAY = <<<'SQL'
        month BETWEEN 1 AND 12
        AND day BETWEEN 1 AND CASE WHEN month = 2 THEN 29 WHEN month IN (4, 6, 9, 11) THEN 30 ELSE 31 END
        AND NOT (month = 1 AND day = 1)
        SQL;

    /** The entity's summary gives row x's date as the 1st of that month and year. */
    private const SUMMARY_STATES_THE_FIRST = <<<'SQL'
        EXISTS (
            SELECT 1
            FROM entities s
            CROSS JOIN LATERAL (
                SELECT to_char(make_date(2000, x.month::integer, 1), 'FMMonth') AS month, abs(x.year)::text AS year
            ) d
            WHERE s.entity_id = x.entity_id
              AND (s.summary ~* ('(^|[^0-9])0?1(st)?\s+' || d.month || '(\s*\[[^]]*\])?,?\s+' || d.year || '([^0-9]|$)')
                   OR s.summary ~* (d.month || '\s+0?1(st)?(\s*\[[^]]*\])?,?\s+' || d.year || '([^0-9]|$)'))
        )
        SQL;

    private const PLACED = <<<'SQL'
        (EXISTS (SELECT 1 FROM entity_locations el WHERE el.entity_id = x.entity_id AND el.is_primary = true AND el.geom IS NOT NULL)
         OR EXISTS (SELECT 1 FROM geometry_periods gp WHERE gp.entity_id = x.entity_id))
        SQL;

    /**
     * @return array{rows: int, from_ranges: int, from_people: int, days: int, fewest: int, median: int}
     */
    public function __invoke(): array
    {
        [$fromRanges, $fromPeople] = DB::transaction(function (): array {
            DB::delete('DELETE FROM discover_anniversaries');

            return [$this->insertFromDateRanges(), $this->insertFromPeople()];
        });

        // Every row is new: give the planner its statistics now, not when autovacuum gets to it.
        DB::statement('ANALYZE discover_anniversaries');
        GetOnThisDayAction::forgetCachedDays();

        $coverage = DB::selectOne(
            <<<'SQL'
            SELECT count(*) AS days, COALESCE(min(n), 0) AS fewest,
                   COALESCE(percentile_disc(0.5) WITHIN GROUP (ORDER BY n), 0) AS median
            FROM (SELECT count(*) AS n FROM discover_anniversaries GROUP BY month, day) per_day
            SQL,
        );

        return [
            'rows' => $fromRanges + $fromPeople,
            'from_ranges' => $fromRanges,
            'from_people' => $fromPeople,
            'days' => (int) $coverage->days,
            'fewest' => (int) $coverage->fewest,
            'median' => (int) $coverage->median,
        ];
    }

    private function insertFromDateRanges(): int
    {
        $statuses = DiscoverEntities::visibleStatusSql();
        $dayDate = self::DAY_DATE;
        $realDay = self::REAL_DAY;
        $placed = self::PLACED;
        $firstOfMonth = self::firstOfMonth();

        return DB::affectingStatement(
            <<<SQL
            INSERT INTO discover_anniversaries (entity_id, kind, month, day, year, date, impact, placed)
            WITH dated AS (
                SELECT t.entity_id,
                       e.entity_type::text AS entity_type,
                       e.entity_group::text AS entity_group,
                       COALESCE(e.impact_score, 0) AS impact,
                       NULLIF(btrim(t.start_date), '') AS starts,
                       NULLIF(btrim(t.end_date), '') AS ends,
                       (t.end_year IS NOT NULL OR COALESCE(e.attributes->>'death_date', '') <> '') AS has_died
                FROM entity_temporal_ranges t
                JOIN entities e ON e.entity_id = t.entity_id
                WHERE t.is_primary = true
                  AND (btrim(t.start_date) ~ '{$dayDate}' OR btrim(t.end_date) ~ '{$dayDate}')
                  AND e.verification_status IN ({$statuses})
            ), edges AS (
                SELECT d.*, 'start' AS edge, d.starts AS date FROM dated d WHERE d.starts ~ '{$dayDate}'
                UNION ALL
                SELECT d.*, 'end' AS edge, d.ends AS date FROM dated d WHERE d.ends ~ '{$dayDate}'
            ), parsed AS (
                SELECT x.*,
                       substring(x.date from '^(-?\d+)-')::integer AS year,
                       substring(x.date from '-(\d{2})-\d{2}$')::smallint AS month,
                       right(x.date, 2)::smallint AS day
                FROM edges x
            ), kinds AS (
                SELECT x.*,
                       CASE
                           WHEN x.entity_type = 'person' THEN CASE WHEN x.edge = 'end' THEN 'died' WHEN x.has_died THEN 'born' END
                           WHEN x.entity_group = 'EVENT' THEN CASE
                               WHEN x.edge = 'start' AND (x.ends IS NULL OR x.ends = x.starts) THEN 'happened'
                               WHEN x.edge = 'start' THEN 'began'
                               WHEN x.starts IS DISTINCT FROM x.ends THEN 'ended'
                           END
                           WHEN x.edge = 'start' THEN 'founded'
                           WHEN x.starts IS DISTINCT FROM x.ends THEN 'dissolved'
                       END AS kind
                FROM parsed x
                WHERE {$realDay}
                  AND NOT (x.edge = 'end' AND x.month = 12 AND x.day = 31)
            )
            SELECT x.entity_id, x.kind, x.month, x.day, x.year, x.date, x.impact, {$placed}
            FROM kinds x
            WHERE x.kind IS NOT NULL {$firstOfMonth}
            ORDER BY x.month, x.day
            ON CONFLICT (entity_id, kind) DO NOTHING
            SQL,
        );
    }

    private function insertFromPeople(): int
    {
        $statuses = DiscoverEntities::visibleStatusSql();
        $realDay = self::REAL_DAY;
        $placed = self::PLACED;
        $firstOfMonth = self::firstOfMonth();

        return DB::affectingStatement(
            <<<SQL
            INSERT INTO discover_anniversaries (entity_id, kind, month, day, year, date, impact, placed)
            WITH people AS (
                SELECT e.entity_id,
                       COALESCE(e.impact_score, 0) AS impact,
                       e.attributes->>'birth_date' AS born,
                       e.attributes->>'death_date' AS died
                FROM entities e
                WHERE e.entity_type = 'person'
                  AND e.impact_score >= ?
                  AND COALESCE(e.attributes->>'death_date', '') <> ''
                  AND e.verification_status IN ({$statuses})
            ), edges AS MATERIALIZED (
                SELECT p.entity_id, p.impact, v.kind,
                       regexp_match(v.value, '^(-?\d{1,6})-(\d{2})-(\d{2})(T.*)?$') AS m
                FROM people p
                CROSS JOIN LATERAL (VALUES ('born', p.born), ('died', p.died)) AS v(kind, value)
            ), parsed AS (
                SELECT x.entity_id, x.impact, x.kind,
                       -- A timestamp numbers years astronomically: 0000 is 1 BCE, ours is -1.
                       CASE WHEN x.m[4] IS NOT NULL AND x.m[1]::integer <= 0 THEN x.m[1]::integer - 1 ELSE x.m[1]::integer END AS year,
                       x.m[2]::smallint AS month,
                       x.m[3]::smallint AS day
                FROM edges x
                WHERE x.m IS NOT NULL
            )
            SELECT x.entity_id, x.kind, x.month, x.day, x.year,
                   (CASE WHEN x.year < 0 THEN '-' ELSE '' END) || lpad(abs(x.year)::text, 4, '0')
                       || '-' || lpad(x.month::text, 2, '0') || '-' || lpad(x.day::text, 2, '0'),
                   x.impact, {$placed}
            FROM parsed x
            WHERE {$realDay} {$firstOfMonth}
            ORDER BY x.month, x.day
            ON CONFLICT (entity_id, kind) DO NOTHING
            SQL,
            [(int) config('discover.anniversaries.people_min_impact')],
        );
    }

    /** What to do with row x when its date is the 1st of a month, as a SQL condition. */
    private static function firstOfMonth(): string
    {
        return match ((string) config('discover.anniversaries.first_of_month')) {
            'all' => '',
            'none' => 'AND x.day <> 1',
            default => 'AND (x.day <> 1 OR '.self::SUMMARY_STATES_THE_FIRST.')',
        };
    }
}
