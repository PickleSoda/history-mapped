<?php

declare(strict_types=1);

namespace App\Actions\Discover;

use App\Enums\ChronicleStatus;
use App\Http\Api\V1\Resources\ChronicleResource;
use App\Http\Api\V1\Resources\MapStorySummaryResource;
use App\Models\Chronicle;
use App\Models\MapStory;
use App\Services\RelationGraphSupport as G;
use App\Support\Discover\DiscoverEntities;
use App\Support\PgSettings;
use Illuminate\Support\Facades\DB;

/**
 * Suggestions from the entities a browser opened lately, most recent first
 * (GET /discover/for-you): related entities, chronicles and battle maps.
 *
 *   - `entities`: the other end of each seed's relationships, never a seed.
 *     Per seed the `per_seed` (3) with the highest impact, `entities` (8) in
 *     all, earlier seeds first.
 *   - `chronicles`: chronicles (not archived) with an entry that names a
 *     seed, as an entry entity or as an end of its primary relationship;
 *     `chronicles` (4) by impact, a more recent seed's first among equals.
 *   - `stories`: map stories whose entity is a seed or a suggested entity;
 *     `stories` (3), seeds first.
 *   - `via` is the seed a row comes from (the most recent, when several);
 *     `because` lists the seeds that produced a row.
 *   - An entity row says how it is related: `relation` is the relationship's
 *     type, `outgoing` its direction (a relationship reads "source, type,
 *     target"; true when the seed is the source, so "seed, type, row") and
 *     `year` the year the relationship starts, when it has one.
 *
 * Index lookups only, each bounded, so a hub seed stays cheap. World War I
 * has 17,000 relationships and London 15,000; ranking all of a hub's
 * neighbours by impact reads every one of their rows in the 1 GB `entities`
 * heap (60 ms locally for one seed, with parallel workers the droplet does
 * not have). So a seed's walk reads at most `discover.for_you.walk` (400)
 * relationships: 200 outgoing and 200 incoming, each in relationship-type
 * order, which the (entity, type) indexes give without a sort. All but 364
 * of the 390,000 entities with relationships have fewer than that in each
 * direction: for them the walk is every relationship and the result is
 * exact. For a hub it is the highest-impact neighbours among those walked.
 * The chronicle lookup by primary relationship uses the same walk. Seeds are
 * taken in order and a walk's neighbours are ranked only until there are
 * enough suggestions.
 *
 * Seeds the atlas does not know (or hides) are ignored. Nothing is cached:
 * the answer belongs to one browser.
 */
class GetForYouAction
{
    /** `confidence_level` in its own order: most confident first. */
    private const CONFIDENCE_RANK = ['high' => 0, 'medium' => 1, 'low' => 2, 'unresolved' => 3];

    /**
     * @param  list<string>  $ids  entity ids, most recently opened first
     * @return array{because: list<array{id: string, name: string}>, entities: list<array<string, mixed>>, chronicles: list<array<string, mixed>>, stories: list<array<string, mixed>>}
     */
    public function __invoke(array $ids): array
    {
        $seeds = $this->seeds($ids);
        if ($seeds === []) {
            return ['because' => [], 'entities' => [], 'chronicles' => [], 'stories' => []];
        }

        /** @var array<string, int> $position seed id => its place in the request */
        $position = array_flip(array_keys($seeds));
        $walk = $this->walk(array_keys($seeds));

        $entities = $this->entities($position, $walk);
        $chronicles = $this->chronicles($position, $walk);
        $stories = $this->stories($position, $entities);

        $used = [];
        foreach ([$entities, $chronicles, $stories] as $rows) {
            foreach ($rows as $row) {
                $used[$row['via']] = true;
            }
        }

        $because = [];
        foreach ($seeds as $id => $name) {
            if (isset($used[$id])) {
                $because[] = ['id' => $id, 'name' => $name];
            }
        }

        return ['because' => $because, 'entities' => $entities, 'chronicles' => $chronicles, 'stories' => $stories];
    }

    /**
     * The seeds the atlas shows, in the order given: id => name.
     *
     * @param  list<string>  $ids
     * @return array<string, string>
     */
    private function seeds(array $ids): array
    {
        $ids = array_values(array_unique(array_map(strtolower(...), $ids)));
        $statuses = DiscoverEntities::visibleStatusSql();

        $names = [];
        foreach (DB::select(
            "SELECT entity_id, name FROM entities WHERE entity_id = ANY(?::uuid[]) AND verification_status IN ({$statuses})",
            [G::pgArray($ids)],
        ) as $row) {
            $names[(string) $row->entity_id] = (string) $row->name;
        }

        $seeds = [];
        foreach ($ids as $id) {
            if (isset($names[$id])) {
                $seeds[$id] = $names[$id];
            }
        }

        return $seeds;
    }

    /**
     * Each seed's relationships, at most half of `discover.for_you.walk` in
     * each direction, from `relationships` alone.
     *
     * The planner cannot tell a hub from the seed's id and expects about 40
     * rows either way, so left alone it may fetch every relationship of the
     * seed and sort them (68 ms and 13,900 buffers locally for five seeds,
     * two of them hubs). With bitmap scans and sorts off it walks the
     * (entity, type) index in order and stops at the limit (3 ms, 600
     * buffers).
     *
     * @param  list<string>  $seedIds
     * @return list<object> rows of seed, relationship_id, relationship_type, other, confidence, incoming, start_year
     */
    private function walk(array $seedIds): array
    {
        $perDirection = max(1, intdiv((int) config('discover.for_you.walk'), 2));

        return PgSettings::with(['enable_bitmapscan' => 'off', 'enable_sort' => 'off'], fn (): array => DB::select(
            <<<'SQL'
            SELECT s.seed, w.relationship_id, w.relationship_type::text AS relationship_type, w.other, w.confidence::text AS confidence,
                   w.incoming, w.start_year
            FROM unnest(?::uuid[]) WITH ORDINALITY AS s(seed, ord)
            CROSS JOIN LATERAL (
                (SELECT r.relationship_id, r.relationship_type, r.target_entity_id AS other, r.confidence, 0 AS incoming, r.start_year
                 FROM relationships r
                 WHERE r.source_entity_id = s.seed
                 ORDER BY r.relationship_type
                 LIMIT ?)
                UNION ALL
                (SELECT r.relationship_id, r.relationship_type, r.source_entity_id AS other, r.confidence, 1 AS incoming, r.start_year
                 FROM relationships r
                 WHERE r.target_entity_id = s.seed
                 ORDER BY r.relationship_type
                 LIMIT ?)
            ) w
            ORDER BY s.ord, w.incoming, w.relationship_type, w.relationship_id
            SQL,
            [G::pgArray($seedIds), $perDirection, $perDirection],
        ));
    }

    /**
     * @param  array<string, int>  $position
     * @param  list<object>  $walk
     * @return list<array<string, mixed>>
     */
    private function entities(array $position, array $walk): array
    {
        $limit = (int) config('discover.for_you.entities');
        $perSeed = (int) config('discover.for_you.per_seed');

        // seed => other => its strongest link to that seed.
        $links = [];
        foreach ($walk as $row) {
            $seed = (string) $row->seed;
            $other = (string) $row->other;
            if (isset($position[$other])) {
                continue;
            }
            $known = $links[$seed][$other] ?? null;
            if ($known === null || self::confidenceRank($row) < self::confidenceRank($known)) {
                $links[$seed][$other] = $row;
            }
        }

        /** @var array<string, object> $chosen other id => its link */
        $chosen = [];
        $statuses = DiscoverEntities::visibleStatusSql();
        foreach (array_keys($position) as $seed) {
            if (count($chosen) >= $limit) {
                break;
            }
            $candidates = array_diff_key($links[$seed] ?? [], $chosen);
            if ($candidates === []) {
                continue;
            }

            $ranked = [];
            foreach (DB::select(
                "SELECT entity_id, impact_score FROM entities WHERE entity_id = ANY(?::uuid[]) AND verification_status IN ({$statuses})",
                [G::pgArray(array_keys($candidates))],
            ) as $entity) {
                $id = (string) $entity->entity_id;
                // Highest impact first (unknown last), then the surer link, then id.
                $ranked[$id] = [$entity->impact_score === null ? 1 : 0, -(int) $entity->impact_score, self::confidenceRank($candidates[$id]), $id];
            }
            asort($ranked);

            foreach (array_slice(array_keys($ranked), 0, min($perSeed, $limit - count($chosen))) as $id) {
                $chosen[$id] = $candidates[$id];
            }
        }

        // The chosen entities and the seeds they come from, in one read.
        $viaSeeds = array_map(fn (object $link): string => (string) $link->seed, array_values($chosen));
        $shapes = DiscoverEntities::byId([...array_keys($chosen), ...$viaSeeds]);
        $entities = [];
        foreach ($chosen as $id => $link) {
            if (isset($shapes[$id])) {
                $entities[] = [
                    ...$shapes[$id],
                    'via' => (string) $link->seed,
                    'relation' => (string) $link->relationship_type,
                    // A relationship reads "source, type, target": true when the seed is the source.
                    'outgoing' => (int) $link->incoming === 0,
                    'year' => self::yearToOpen(
                        $shapes[$id],
                        $shapes[(string) $link->seed] ?? null,
                        $link->start_year === null ? null : (int) $link->start_year,
                    ),
                ];
            }
        }

        return $entities;
    }

    /**
     * The year to open a suggested entity at, so that the map shows it beside
     * the seed it comes from: the year their relationship starts when it has
     * one (few do), else the first year both exist, else the entity's own
     * first year. Always inside the entity's own years; a missing end year
     * means no known end.
     *
     * @param  array<string, mixed>  $entity
     * @param  array<string, mixed>|null  $seed
     */
    private static function yearToOpen(array $entity, ?array $seed, ?int $linkYear): ?int
    {
        $start = $entity['start_year'];
        $end = $entity['end_year'];

        if ($linkYear !== null) {
            if ($start !== null && $linkYear < $start) {
                return $start;
            }

            return $end !== null && $linkYear > $end ? $end : $linkYear;
        }

        $seedStart = $seed['start_year'] ?? null;
        if ($seedStart !== null) {
            $seedEnd = $seed['end_year'] ?? null;
            $both = $start === null ? $seedStart : max($seedStart, $start);
            // Both exist in that year: neither has ended before it.
            if (($seedEnd === null || $both <= $seedEnd) && ($end === null || $both <= $end)) {
                return $both;
            }
        }

        return $start;
    }

    /**
     * @param  array<string, int>  $position
     * @param  list<object>  $walk
     * @return list<array<string, mixed>>
     */
    private function chronicles(array $position, array $walk): array
    {
        // A walked relationship => the seeds at its ends.
        $seedsOf = [];
        foreach ($walk as $row) {
            $seedsOf[(string) $row->relationship_id][(string) $row->seed] = true;
        }

        $named = DB::select(
            <<<'SQL'
            SELECT cee.entity_id AS seed, NULL::uuid AS relationship_id, ce.chronicle_id
            FROM chronicle_entry_entities cee
            JOIN chronicle_entries ce ON ce.entry_id = cee.entry_id
            WHERE cee.entity_id = ANY(?::uuid[])
            UNION
            SELECT NULL::uuid, ce.primary_relationship_id, ce.chronicle_id
            FROM chronicle_entries ce
            WHERE ce.primary_relationship_id = ANY(?::uuid[])
            SQL,
            [G::pgArray(array_keys($position)), G::pgArray(array_keys($seedsOf))],
        );

        // chronicle => the most recent seed it names.
        $via = [];
        foreach ($named as $row) {
            $seeds = $row->seed !== null ? [(string) $row->seed] : array_keys($seedsOf[(string) $row->relationship_id] ?? []);
            foreach ($seeds as $seed) {
                $chronicle = (string) $row->chronicle_id;
                if (! isset($via[$chronicle]) || $position[$seed] < $position[$via[$chronicle]]) {
                    $via[$chronicle] = $seed;
                }
            }
        }
        if ($via === []) {
            return [];
        }

        $ranked = [];
        foreach (DB::select(
            'SELECT chronicle_id, impact_score, title FROM chronicles WHERE chronicle_id = ANY(?::uuid[]) AND status <> ?',
            [G::pgArray(array_keys($via)), ChronicleStatus::Archived->value],
        ) as $row) {
            $id = (string) $row->chronicle_id;
            $ranked[$id] = [$row->impact_score === null ? 1 : 0, -(int) $row->impact_score, $position[$via[$id]], (string) $row->title, $id];
        }
        asort($ranked);
        $ids = array_slice(array_keys($ranked), 0, (int) config('discover.for_you.chronicles'));
        if ($ids === []) {
            return [];
        }

        // The rows of GET /chronicles (ListChroniclesAction + ChronicleResource).
        $chronicles = Chronicle::query()->withCount('entries')->with('tags')->whereIn('chronicle_id', $ids)->get()->keyBy('chronicle_id');
        $rows = ChronicleResource::collection(
            collect($ids)->map(fn (string $id) => $chronicles->get($id))->filter()->values(),
        )->resolve();

        return array_map(fn (array $row): array => [...$row, 'via' => $via[$row['chronicle_id']]], array_values($rows));
    }

    /**
     * @param  array<string, int>  $position
     * @param  list<array<string, mixed>>  $entities  the suggested entities
     * @return list<array<string, mixed>>
     */
    private function stories(array $position, array $entities): array
    {
        // entity => the seed it stands for, seeds first.
        $via = [];
        foreach (array_keys($position) as $seed) {
            $via[$seed] = $seed;
        }
        foreach ($entities as $entity) {
            $via[$entity['id']] ??= $entity['via'];
        }
        $order = array_flip(array_keys($via));

        // The rows of GET /map-stories (ListMapStoriesAction + MapStorySummaryResource).
        return MapStory::query()
            ->select(MapStory::SUMMARY_COLUMNS)
            ->with(MapStorySummaryResource::RELATIONS)
            ->whereIn('entity_id', array_keys($via))
            ->get()
            ->sortBy(fn (MapStory $story): array => [$order[$story->entity_id], $story->slug])
            ->take((int) config('discover.for_you.stories'))
            ->map(fn (MapStory $story): array => [...MapStorySummaryResource::row($story), 'via' => $via[$story->entity_id]])
            ->values()
            ->all();
    }

    private static function confidenceRank(object $link): int
    {
        return self::CONFIDENCE_RANK[$link->confidence ?? ''] ?? count(self::CONFIDENCE_RANK);
    }
}
