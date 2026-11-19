<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Builders\EntityBuilder;
use App\DTOs\EntityFilterData;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Pagination\CappedLengthAwarePaginator;
use Closure;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Pagination\Paginator;
use Illuminate\Support\Facades\DB;

/**
 * List entities with filtering, spatial/temporal queries, and pagination.
 *
 * Delegates all query building to EntityBuilder for type-safe, composable queries.
 *
 * With `$totalCap` the total is counted only up to that many rows (a
 * CappedLengthAwarePaginator, `meta.total_capped`). An exact count of a broad
 * filter (a continent at a year, a common search word) walks tens of
 * thousands of rows; on the 1-vCPU droplet that took 5-40 s per request. The
 * public API caps; the admin keeps exact totals for its pager.
 */
class ListEntitiesAction
{
    /**
     * Similarity thresholds a fuzzy search page tries, in turn, before the
     * full query (whose `name % term` uses pg_trgm's default of 0.3).
     */
    public const SIMILARITY_STEPS = [0.6, 0.45];

    /**
     * @return LengthAwarePaginator<Entity>
     */
    public function __invoke(EntityFilterData $filters, ?int $totalCap = null): LengthAwarePaginator
    {
        $query = Entity::query()->withGeoJson();

        // ── Text search ──────────────────────────────────────
        if ($filters->search !== null && $filters->search !== '') {
            $query->search($filters->search);
        }

        // ── Type / Group filters ─────────────────────────────
        if ($filters->type !== null) {
            $query->ofType($filters->type);
        }

        if ($filters->types !== null && $filters->types !== []) {
            $query->ofTypes($filters->types);
        }

        if ($filters->groups !== null && $filters->groups !== []) {
            $query->ofGroups($filters->groups);
        } elseif ($filters->group !== null) {
            $query->ofGroup($filters->group);
        }

        // ── Verification / Confidence ────────────────────────
        if ($filters->status !== null) {
            $query->withStatus($filters->status);
        }

        if ($filters->minConfidence !== null) {
            $query->withMinConfidence($filters->minConfidence);
        }

        // ── Tags ─────────────────────────────────────────────
        if ($filters->tag !== null && $filters->tag !== '') {
            $query->hasTag($filters->tag);
        }

        if ($filters->tags !== null && $filters->tags !== []) {
            $query->withTags($filters->tags);
        }

        if ($filters->hasImage !== null) {
            $query->withImage($filters->hasImage);
        }

        // ── Spatial filters ──────────────────────────────────
        if ($filters->hasBbox()) {
            $query->inBbox(
                $filters->bboxMinLng,
                $filters->bboxMinLat,
                $filters->bboxMaxLng,
                $filters->bboxMaxLat,
            );
        }

        if ($filters->hasNearPoint()) {
            $query->nearPoint(
                $filters->nearLng,
                $filters->nearLat,
                $filters->nearRadius,
            );
        }

        // ── Temporal filters ─────────────────────────────────
        if ($filters->hasTimeRange()) {
            $query->inTimeRange($filters->temporalStart, $filters->temporalEnd);
        }

        if ($filters->existsAt !== null) {
            $query->existsAt($filters->existsAt);
        }

        // ── Eager loading ────────────────────────────────────
        if ($filters->includeRelationships) {
            $query->with([
                'outgoingRelationships' => fn ($q) => $q->with(EntityRelationship::withSummaryEnds()),
                'incomingRelationships' => fn ($q) => $q->with(EntityRelationship::withSummaryEnds()),
            ]);
        }

        // ── Sorting ──────────────────────────────────────────
        $bySimilarity = false;
        match ($filters->sort) {
            'impact' => $query->orderByImpact(),
            'recent' => $query->orderByRecent(),
            'chronological' => $query->orderByChronological(),
            'name' => $query->orderBy('name'),
            'distance' => $filters->hasNearPoint()
                ? $query->orderByDistanceFrom($filters->nearLng, $filters->nearLat)
                : $query->orderByImpact(),
            default => ($bySimilarity = $filters->search !== null)
                ? $query->orderBySimilarity($filters->search) // fuzzy: best matches first
                : $query->orderByImpact(),
        };

        if ($totalCap === null) {
            return $query->paginate(
                perPage: $filters->perPage,
                page: $filters->page,
            );
        }

        $count = $query->toBase()
            ->cloneWithout(['columns', 'orders', 'limit', 'offset'])
            ->cloneWithoutBindings(['select', 'order'])
            ->selectRaw('1')
            ->limit($totalCap + 1);
        // A semi-join merge walks every entity in id order. Postgres picked it
        // for a year with few entities (the world at 50 BC: 1.5 s on the
        // droplet); without it the count starts from the date-range index
        // (0.18 s) and dense years stay as fast.
        $counted = self::withSettings(
            ['enable_mergejoin' => 'off'],
            fn (): int => DB::query()->fromSub($count, 'capped')->count(),
        );

        $paginator = new CappedLengthAwarePaginator(
            $bySimilarity
                ? $this->mostSimilarPage($query, (string) $filters->search, $filters)
                : $query->forPage($filters->page, $filters->perPage)->get(),
            min($counted, $totalCap),
            $filters->perPage,
            $filters->page,
            ['path' => Paginator::resolveCurrentPath(), 'pageName' => 'page'],
        );
        $paginator->totalCapped = $counted > $totalCap;

        return $paginator;
    }

    /**
     * One page of a fuzzy search, best matches first. The full query fetches
     * and scores every match to keep a page: a common word matches ~10k names
     * ("battle of": 1.9 s on the droplet). Every name at least as similar as
     * a threshold ranks above every name below it, so when those names fill
     * the page they are the page. Raising pg_trgm's threshold lets the
     * trigram index skip the weaker matches: 0.07-0.25 s for the same words.
     * Rare names don't fill the page and fall through to the full query,
     * which is fast for them.
     *
     * @return Collection<int, Entity>
     */
    private function mostSimilarPage(EntityBuilder $query, string $term, EntityFilterData $filters): Collection
    {
        $term = trim($term);
        if (mb_strlen($term) >= EntityBuilder::SEARCH_FUZZY_FROM) {
            foreach (self::SIMILARITY_STEPS as $threshold) {
                $rows = self::withSettings(
                    ['pg_trgm.similarity_threshold' => (string) $threshold],
                    fn (): Collection => (clone $query)
                        ->whereRaw('name % ?', [$term])
                        ->forPage($filters->page, $filters->perPage)
                        ->get(),
                );
                if ($rows->count() === $filters->perPage) {
                    return $rows;
                }
            }
        }

        return $query->forPage($filters->page, $filters->perPage)->get();
    }

    /**
     * Run $query with Postgres settings changed for it alone. set_config(…,
     * true) lasts to the end of the transaction; the RESET puts the default
     * back at once for a caller already inside one (a test, say), where this
     * transaction is only a savepoint.
     *
     * @template T
     *
     * @param  array<string, string>  $settings
     * @param  Closure(): T  $query
     * @return T
     */
    private static function withSettings(array $settings, Closure $query): mixed
    {
        return DB::transaction(function () use ($settings, $query): mixed {
            foreach ($settings as $name => $value) {
                DB::select('SELECT set_config(?, ?, true)', [$name, $value]);
            }
            $result = $query();
            foreach (array_keys($settings) as $name) {
                DB::statement("RESET {$name}");
            }

            return $result;
        });
    }
}
