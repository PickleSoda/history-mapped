<?php

declare(strict_types=1);

namespace App\Actions\Discover;

use App\Support\Discover\DiscoverEntities;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * What the atlas has for a month and day: an event, a founding, a birth, a
 * death (GET /discover/on-this-day).
 *
 * Read from `discover_anniversaries` by its day index, never from the date
 * ranges or the entities themselves (BuildAnniversariesAction fills it).
 *
 *   - Order: entities on the map first, then by impact.
 *   - Size: `discover.on_this_day.size` (8). People (born / died) take at
 *     most `max_people` (4) of them, and leave room for `min_others` (2) of
 *     the other kinds when the day has them.
 *   - A thin day (fewer than `min_items`, 4) borrows from its neighbours: the
 *     day before and after, then two days away, up to `max_widen` (3), only
 *     until it has `min_items`. `widened` is how far it went.
 *
 * The answer is cached per month and day (an empty one only briefly); the
 * build command forgets them all.
 */
class GetOnThisDayAction
{
    private const PEOPLE_KINDS = ['born', 'died'];

    /** A leap year, so that 29 February has neighbours and is one. */
    private const LEAP_YEAR = 2000;

    /**
     * @return array{month: int, day: int, widened: int, items: list<array<string, mixed>>}
     */
    public function __invoke(int $month, int $day): array
    {
        return Cache::remember(
            self::cacheKey($month, $day),
            // An empty answer means the table is not built yet: do not hold on to it.
            fn (array $answer): int => (int) config($answer['items'] === [] ? 'discover.cache.empty' : 'discover.cache.on_this_day'),
            fn (): array => $this->build($month, $day),
        );
    }

    public static function cacheKey(int $month, int $day): string
    {
        return sprintf('discover:on-this-day:%02d-%02d', $month, $day);
    }

    /** Drop every cached day (the table was rebuilt). */
    public static function forgetCachedDays(): void
    {
        $day = new \DateTimeImmutable(self::LEAP_YEAR.'-01-01');
        for ($i = 0; $i < 366; $i++) {
            Cache::forget(self::cacheKey((int) $day->format('n'), (int) $day->format('j')));
            $day = $day->modify('+1 day');
        }
    }

    /**
     * @return array{month: int, day: int, widened: int, items: list<array<string, mixed>>}
     */
    private function build(int $month, int $day): array
    {
        $size = (int) config('discover.on_this_day.size');
        $maxPeople = (int) config('discover.on_this_day.max_people');
        $minItems = min($size, (int) config('discover.on_this_day.min_items'));

        $own = $this->rowsOf($month, $day, $size, $maxPeople);
        $others = count(array_filter($own, fn (object $row): bool => ! self::isPerson($row)));
        // People leave room for the other kinds the day has.
        $peopleCap = min($maxPeople, max(0, $size - min((int) config('discover.on_this_day.min_others'), $others)));

        $picked = [];
        $this->take($picked, $own, $size, $peopleCap);

        $widened = 0;
        while (count($picked) < $minItems && $widened < (int) config('discover.on_this_day.max_widen')) {
            $widened++;
            $neighbours = [];
            foreach ([-$widened, $widened] as $offset) {
                [$m, $d] = self::shift($month, $day, $offset);
                array_push($neighbours, ...$this->rowsOf($m, $d, $size, $maxPeople));
            }
            $this->take($picked, self::sorted($neighbours), $minItems, $peopleCap);
        }

        $entities = DiscoverEntities::byId(array_keys($picked));
        $items = [];
        foreach ($picked as $id => $row) {
            // Hidden or deleted since the table was built: leave it out.
            if (isset($entities[$id])) {
                $items[] = [...$entities[$id], 'kind' => $row->kind, 'year' => (int) $row->year, 'date' => $row->date];
            }
        }

        return ['month' => $month, 'day' => $day, 'widened' => $widened, 'items' => $items];
    }

    /**
     * Add rows to `$picked` (keyed by entity id) in their order until it holds
     * `$limit`, one row per entity, people only up to `$peopleCap`.
     *
     * @param  array<string, object>  $picked
     * @param  list<object>  $rows
     */
    private function take(array &$picked, array $rows, int $limit, int $peopleCap): void
    {
        $people = count(array_filter($picked, self::isPerson(...)));

        foreach ($rows as $row) {
            if (count($picked) >= $limit) {
                return;
            }
            if (isset($picked[$row->entity_id])) {
                continue;
            }
            if (self::isPerson($row)) {
                if ($people >= $peopleCap) {
                    continue;
                }
                $people++;
            }
            $picked[$row->entity_id] = $row;
        }
    }

    /**
     * The best rows of one day in order: enough people and enough of the
     * other kinds to fill an answer, each read from the day index.
     *
     * @return list<object>
     */
    private function rowsOf(int $month, int $day, int $size, int $maxPeople): array
    {
        $rows = DB::select(
            <<<'SQL'
            (SELECT entity_id, kind, year, date, impact, placed
             FROM discover_anniversaries
             WHERE month = ? AND day = ? AND kind IN ('born', 'died')
             ORDER BY placed DESC, impact DESC, entity_id, year, kind
             LIMIT ?)
            UNION ALL
            (SELECT entity_id, kind, year, date, impact, placed
             FROM discover_anniversaries
             WHERE month = ? AND day = ? AND kind NOT IN ('born', 'died')
             ORDER BY placed DESC, impact DESC, entity_id, year, kind
             LIMIT ?)
            SQL,
            // Twice what is needed: an entity can hold two rows on one day
            // (begun and ended on the same date, years apart).
            [$month, $day, 2 * $maxPeople, $month, $day, 2 * $size],
        );

        return self::sorted($rows);
    }

    /**
     * Placed first, then by impact; the entity id, the year and the kind make
     * it stable (an entity's earlier date first: begun before ended).
     *
     * @param  list<object>  $rows
     * @return list<object>
     */
    private static function sorted(array $rows): array
    {
        usort($rows, fn (object $a, object $b): int => [(bool) $b->placed, (int) $b->impact, (string) $a->entity_id, (int) $a->year, (string) $a->kind]
            <=> [(bool) $a->placed, (int) $a->impact, (string) $b->entity_id, (int) $b->year, (string) $b->kind]);

        return $rows;
    }

    private static function isPerson(object $row): bool
    {
        return in_array($row->kind, self::PEOPLE_KINDS, true);
    }

    /**
     * The month and day `$offset` days away, in a year that has a 29 February.
     *
     * @return array{0: int, 1: int}
     */
    private static function shift(int $month, int $day, int $offset): array
    {
        $date = (new \DateTimeImmutable)->setDate(self::LEAP_YEAR, $month, $day)->modify(sprintf('%+d days', $offset));

        return [(int) $date->format('n'), (int) $date->format('j')];
    }
}
