<?php

declare(strict_types=1);

namespace App\Actions\Discover;

use App\Services\RelationGraphSupport;
use App\Support\Discover\DiscoverEntities;
use App\Support\Discover\WorldRegion;
use App\Support\PgSettings;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * The day's expedition: three battles to find on the map and the timeline,
 * one easy, one medium, one hard (GET /discover/quest). The same three for
 * everyone on a date.
 *
 * The pool is the battles the tiles show from zoom `discover.quest.max_zoom`
 * (3) or lower, with a point inside a world region and a summary of at least
 * `min_summary` (40) characters to serve as the clue. One row per entity.
 *
 * Difficulty is how well trodden a battle is: how many chronicle entries
 * mention it (`chronicle_entry_entities`) and whether it has a battle map.
 *
 *   easy    a battle map, or at least `easy_min_mentions` (2) mentions
 *   hard    never mentioned (and no battle map)
 *   medium  the rest: mentioned exactly once
 *
 * Measured on the local database, 2026-11-20 (1,959 battles in the pool):
 * 309 easy, 1,271 medium, 379 hard. The spec asked for "the most-mentioned
 * third" as easy with at least 150 in every tier, but mentions are 0, 1, 2…
 * and 65% of the pool has exactly one, so no cut gives a third: two or more
 * is the top 16%, three or more would leave 85 easy battles, and one or more
 * would be 81% and leave nothing for medium.
 *
 * Within a tier the day's target is the first by `md5(id || date)`.
 *
 * `place` is the second "where" hint, a nearer name than the region: the
 * primary location's name, else the name of what the battle is `located_at`
 * (a city before a country). Either counts only when it says something the
 * battle's own name does not: 98% of the pool's location names repeat the
 * battle's name, and "Mantua" is no hint for the Siege of Mantua.
 *
 * Candidates are ranked from `tiles.atlas_features` and the mention index
 * alone; only the first few of each tier are then read from `entities`, where
 * the clue is checked. If none of a tier's first few qualifies (a database
 * with few summaries), a second query checks the clue in SQL for the whole
 * tier. The answer is cached per date; one with fewer than three targets only
 * briefly, since it means the tile table is not ready.
 */
class GetDailyQuestAction
{
    private const TIERS = ['easy', 'medium', 'hard'];

    /** Candidates read per tier before falling back to the exact query. */
    private const FIRST_FEW = 5;

    /**
     * @param  string  $date  YYYY-MM-DD
     * @return array{date: string, number: int, targets: list<array<string, mixed>>}
     */
    public function __invoke(string $date): array
    {
        return Cache::remember(
            "discover:quest:{$date}",
            fn (array $answer): int => (int) config(count($answer['targets']) < count(self::TIERS) ? 'discover.cache.empty' : 'discover.cache.quest'),
            fn (): array => $this->build($date),
        );
    }

    /** Days since the first expedition (`discover.quest_epoch`), plus one. */
    public static function number(string $date): int
    {
        $epoch = CarbonImmutable::createFromFormat('!Y-m-d', (string) config('discover.quest_epoch'), 'UTC');
        $day = CarbonImmutable::createFromFormat('!Y-m-d', $date, 'UTC');

        return intdiv($day->getTimestamp() - $epoch->getTimestamp(), 86400) + 1;
    }

    /**
     * @return array{date: string, number: int, targets: list<array<string, mixed>>}
     */
    private function build(string $date): array
    {
        $targets = $this->choose($this->candidates($date, self::FIRST_FEW, false));

        $missing = array_values(array_diff(self::TIERS, array_keys($targets)));
        if ($missing !== []) {
            $targets += $this->choose(array_filter(
                $this->candidates($date, 1, true),
                fn (object $candidate): bool => in_array($candidate->difficulty, $missing, true),
            ));
        }

        return [
            'date' => $date,
            'number' => self::number($date),
            'targets' => $this->withPlaces(array_values(array_filter(array_map(
                fn (string $tier): ?array => $targets[$tier] ?? null,
                self::TIERS,
            )))),
        ];
    }

    /**
     * The first candidate of each tier that is still visible, placed and has a
     * clue, as a target keyed by tier.
     *
     * @param  array<int, object>  $candidates  best first within a tier
     * @return array<string, array<string, mixed>>
     */
    private function choose(array $candidates): array
    {
        $rows = DiscoverEntities::rows(array_map(fn (object $c): string => (string) $c->id, array_values($candidates)));
        $minSummary = (int) config('discover.quest.min_summary');

        $targets = [];
        foreach ($candidates as $candidate) {
            $row = $rows[(string) $candidate->id] ?? null;
            if (isset($targets[$candidate->difficulty]) || $row === null || $row->lng === null
                || mb_strlen(trim((string) $row->summary)) < $minSummary) {
                continue;
            }

            $entity = DiscoverEntities::shape($row);
            if ($entity['start_year'] === null) {
                // Dated by its place on the map alone.
                $entity['start_year'] = (int) $candidate->start_year;
                $entity['end_year'] = $candidate->end_year !== null ? (int) $candidate->end_year : null;
            }

            $targets[$candidate->difficulty] = [
                ...$entity,
                'difficulty' => $candidate->difficulty,
                // The year the tiles show it from: being there puts it on the map.
                'year' => (int) $candidate->start_year,
                'region' => WorldRegion::name($candidate->region),
                'place' => self::saysMore((string) $row->location_name, (string) $row->name) ? trim((string) $row->location_name) : null,
            ];
        }

        return $targets;
    }

    /**
     * The first `$perTier` battles of each tier for the date. `$withClue`
     * also checks the summary and the status here, which reads every pool
     * battle's row in `entities`: only for the fallback.
     *
     * @return list<object>
     */
    private function candidates(string $date, int $perTier, bool $withClue): array
    {
        $regionOf = WorldRegion::sqlCase('ST_X(p.point)', 'ST_Y(p.point)');
        $statuses = DiscoverEntities::visibleStatusSql();
        $clue = $withClue
            ? "JOIN entities e ON e.entity_id = p.id::uuid AND e.verification_status IN ({$statuses})
                   AND char_length(btrim(COALESCE(e.summary, ''))) >= ".(int) config('discover.quest.min_summary')
            : '';

        // jit off: compiling this query costs more than running it (see GetMeanwhileAction).
        return PgSettings::with(['jit' => 'off'], fn (): array => DB::select(
            <<<SQL
            WITH pool AS (
                SELECT DISTINCT ON (f.id) f.id, f.start_year, f.end_year, f.has_map_story,
                       ST_PointOnSurface(f.bbox_geom) AS point
                FROM tiles.atlas_features f
                WHERE f.entity_group = 'EVENT' AND f.entity_type = 'event_battle' AND f.min_zoom <= ?
                ORDER BY f.id, f.start_year, f.geometry_period_id
            ), tiered AS (
                SELECT p.id, p.start_year, p.end_year, r.region,
                       CASE WHEN p.has_map_story OR m.mentions >= ? THEN 'easy'
                            WHEN m.mentions = 0 THEN 'hard'
                            ELSE 'medium' END AS difficulty
                FROM pool p
                CROSS JOIN LATERAL (SELECT {$regionOf} AS region) r
                CROSS JOIN LATERAL (
                    SELECT count(*) AS mentions FROM chronicle_entry_entities c WHERE c.entity_id = p.id::uuid
                ) m
                {$clue}
                WHERE r.region IS NOT NULL
            ), ranked AS (
                -- "C": the day's order must not depend on the database's locale.
                SELECT t.*, row_number() OVER (PARTITION BY t.difficulty ORDER BY md5(t.id || ?) COLLATE "C", t.id) AS rank
                FROM tiered t
            )
            SELECT id, difficulty, start_year, end_year, region
            FROM ranked
            WHERE rank <= ?
            ORDER BY difficulty, rank
            SQL,
            [(int) config('discover.quest.max_zoom'), (int) config('discover.quest.easy_min_mentions'), $date, $perTier],
        ));
    }

    /**
     * Give the targets still without a `place` the name of what they are
     * `located_at`: a place (a city, a fort) before a country, then the more
     * important. One indexed lookup for the day's three.
     *
     * @param  list<array<string, mixed>>  $targets
     * @return list<array<string, mixed>>
     */
    private function withPlaces(array $targets): array
    {
        $unnamed = array_filter($targets, fn (array $target): bool => $target['place'] === null);
        if ($unnamed === []) {
            return $targets;
        }

        $statuses = DiscoverEntities::visibleStatusSql();
        $places = DB::select(
            <<<SQL
            SELECT r.source_entity_id AS id, t.name
            FROM relationships r
            JOIN entities t ON t.entity_id = r.target_entity_id
            WHERE r.source_entity_id = ANY(?::uuid[]) AND r.relationship_type = 'located_at'
              AND t.verification_status IN ({$statuses})
            ORDER BY (t.entity_group = 'PLACE') DESC, t.impact_score DESC NULLS LAST, t.name
            SQL,
            [RelationGraphSupport::pgArray(array_column($unnamed, 'id'))],
        );

        foreach ($targets as $i => $target) {
            foreach ($places as $place) {
                if ($target['place'] === null && $place->id === $target['id'] && self::saysMore((string) $place->name, $target['name'])) {
                    $targets[$i]['place'] = trim((string) $place->name);
                    break;
                }
            }
        }

        return $targets;
    }

    /**
     * Whether a place name tells the reader something the battle's name does
     * not: false when it is empty, or one holds the other ("Battle of
     * Mantinea" for "Battle of Mantinea (362 BCE)", "Mantua" for "Siege of
     * Mantua").
     */
    private static function saysMore(string $place, string $name): bool
    {
        $place = mb_strtolower(trim($place));
        $name = mb_strtolower(trim($name));

        return $place !== '' && ! str_contains($name, $place) && ! str_contains($place, $name);
    }
}
