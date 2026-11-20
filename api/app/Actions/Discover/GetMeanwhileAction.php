<?php

declare(strict_types=1);

namespace App\Actions\Discover;

use App\Support\Discover\DiscoverEntities;
use App\Support\Discover\WorldRegion;
use App\Support\PgSettings;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * One year across the map: for each world region the most notable event
 * around then and the most notable state standing (GET /discover/meanwhile).
 *
 * Everything is chosen from `tiles.atlas_features` (57k rows, 16 MB) in one
 * scan, 4 to 9 ms locally, so each result is on the map at that year. Only
 * the chosen few are then read from `entities`, by primary key.
 *
 *   - Events: `EVENT` features within `discover.meanwhile.window` (10) years
 *     of the year, the span the tiles keep an event visible.
 *   - States: `POLITY` features, people excluded, standing in the year.
 *   - Region: WorldRegion, from the feature's point. A feature in no region
 *     still counts in `totals`.
 *   - The event of a region: the highest importance (the greater of display
 *     priority and impact), then the start year nearest the year, then id.
 *   - The state: the most often mentioned in chronicles for the time it
 *     stood (mentions divided by one plus its centuries, to this year when it
 *     still stands), then the highest importance, then the longest standing,
 *     then id. Importance cannot choose: it is 98 for every state with an end
 *     year and 96 for one without (708 of the 2,969 on the map share 98), so
 *     it put Tamna in East Asia in 1066 and Fairchild Semiconductor in North
 *     America in 1979. Mentions alone (an index-only count in
 *     `chronicle_entry_entities`) favour the long-lived: Japan, entered from
 *     660 BCE, in every year of East Asia. Per century they give the Shang,
 *     Rome, the Tang, Song China, the Ming, the Ottomans, the United States.
 *     Not every `political_entity` is a state (peoples, provinces, parties,
 *     a few companies and ships), and nothing in the data tells them apart.
 *   - Regions run west to east; one with neither is left out.
 *
 * An entity with several geometry periods counts once (an event by the period
 * nearest the year, a state by its earliest period covering the year). The
 * runner-up of each slot is read too, and stands in when the first choice was
 * hidden or deleted after the tile table was last refreshed.
 *
 * The answer is cached per year (an empty one only briefly).
 */
class GetMeanwhileAction
{
    /**
     * @return array{year: int, window: int, totals: array{events: int, polities: int}, regions: list<array<string, mixed>>}
     */
    public function __invoke(int $year): array
    {
        return Cache::remember(
            "discover:meanwhile:{$year}",
            fn (array $answer): int => (int) config($answer['regions'] === [] ? 'discover.cache.empty' : 'discover.cache.meanwhile'),
            fn (): array => $this->build($year),
        );
    }

    /**
     * @return array{year: int, window: int, totals: array{events: int, polities: int}, regions: list<array<string, mixed>>}
     */
    private function build(int $year): array
    {
        $window = (int) config('discover.meanwhile.window');
        $regionOf = WorldRegion::sqlCase('o.lng', 'o.lat');

        // The planner's estimate for this query is past the JIT threshold, and
        // compiling it costs more than running it (1914 locally: 30 ms with
        // JIT, 9 without). Production runs with jit off; this makes every
        // database agree.
        $rows = PgSettings::with(['jit' => 'off'], fn (): array => DB::select(
            <<<SQL
            WITH features AS (
                SELECT f.id, f.entity_group, f.start_year, f.end_year, f.geometry_period_id,
                       GREATEST(f.display_priority, f.impact_score) AS importance,
                       ST_PointOnSurface(f.bbox_geom) AS point
                FROM tiles.atlas_features f
                WHERE (f.entity_group = 'EVENT' AND f.start_year <= ? AND COALESCE(f.end_year, f.start_year) >= ?)
                   OR (f.entity_group = 'POLITY' AND f.entity_type <> 'person' AND f.start_year <= ? AND COALESCE(f.end_year, 9999) >= ?)
            ), one AS (
                SELECT DISTINCT ON (f.id) f.id, f.entity_group, f.importance,
                       -- What breaks a tie last: an event's distance from the year, a state's first year.
                       CASE WHEN f.entity_group = 'EVENT' THEN abs(f.start_year - ?) ELSE f.start_year END AS tie,
                       -- How long it has stood, to this year when it has no end.
                       GREATEST(COALESCE(f.end_year, ?) - f.start_year, 0) / 100.0 AS centuries,
                       ST_X(f.point) AS lng, ST_Y(f.point) AS lat
                FROM features f
                ORDER BY f.id, CASE WHEN f.entity_group = 'EVENT' THEN abs(f.start_year - ?) ELSE f.start_year END, f.geometry_period_id
            ), ranked AS (
                SELECT o.id, o.entity_group, r.region,
                       row_number() OVER (
                           PARTITION BY r.region, o.entity_group
                           -- An event has no mentions counted: importance decides it.
                           ORDER BY m.mentions / (1 + o.centuries) DESC, o.importance DESC NULLS LAST, o.tie, o.id
                       ) AS rank,
                       count(*) OVER (PARTITION BY r.region, o.entity_group) AS in_region,
                       count(*) OVER (PARTITION BY o.entity_group) AS in_all
                FROM one o
                CROSS JOIN LATERAL (SELECT {$regionOf} AS region) r
                CROSS JOIN LATERAL (
                    SELECT CASE WHEN o.entity_group = 'POLITY'
                        THEN (SELECT count(*) FROM chronicle_entry_entities c WHERE c.entity_id = o.id::uuid)
                        ELSE 0 END AS mentions
                ) m
            )
            SELECT id, entity_group, region, rank, in_region, in_all
            FROM ranked
            WHERE rank <= 2
            ORDER BY region, entity_group, rank
            SQL,
            [$year + $window, $year - $window, $year, $year, $year, (int) now()->year, $year],
        ));

        $entities = DiscoverEntities::byId(array_map(
            fn (object $row): string => (string) $row->id,
            array_filter($rows, fn (object $row): bool => $row->region !== null),
        ));

        $totals = ['events' => 0, 'polities' => 0];
        $regions = [];
        foreach ($rows as $row) {
            [$slot, $count] = $row->entity_group === 'EVENT' ? ['event', 'events'] : ['polity', 'polities'];
            $totals[$count] = (int) $row->in_all;
            if ($row->region === null) {
                continue;
            }

            $regions[$row->region] ??= ['event' => null, 'polity' => null, 'counts' => ['events' => 0, 'polities' => 0]];
            $regions[$row->region]['counts'][$count] = (int) $row->in_region;
            // Rows come best first: the runner-up fills the slot only when the best is gone.
            $regions[$row->region][$slot] ??= $entities[(string) $row->id] ?? null;
        }

        $answer = [];
        foreach (WorldRegion::NAMES as $key => $name) {
            $region = $regions[$key] ?? null;
            if ($region !== null && ($region['event'] !== null || $region['polity'] !== null)) {
                $answer[] = ['key' => $key, 'name' => $name, ...$region];
            }
        }

        return ['year' => $year, 'window' => $window, 'totals' => $totals, 'regions' => $answer];
    }
}
