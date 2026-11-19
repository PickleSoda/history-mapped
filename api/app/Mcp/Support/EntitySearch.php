<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use App\Actions\Entity\ListEntitiesAction;
use App\DTOs\EntityFilterData;
use App\Enums\EntityType;
use App\Models\Entity;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * Name search for the MCP tools, ranked by SearchRanking.
 *
 * The public list ranks purely by trigram similarity, so the towns called
 * "Hastings" come before the Battle of Hastings. Here the candidates are the
 * list action's best 60 by similarity (typos, and the page total), plus the
 * 40 most important entities with the query at the start of a word, plus the
 * 20 most important entities named exactly that, all in the same type and
 * year filter, plus the 20 word-start matches the curated chronicles mention
 * most. SearchRanking orders the lot and the tool keeps its page.
 *
 * Impact alone is a poor fame signal: the hand-curated core (Julius Caesar,
 * Alexander the Great, Napoleon) sits at 70 while bulk-imported writers reach
 * 80. Chronicle mentions say who the atlas's own narratives are about, so
 * they add up to PROMINENCE_MAX points: 8 x ln(1 + mentions).
 */
final class EntitySearch
{
    public const CANDIDATES = 60;

    private const WORD_START = 40;

    private const EXACT = 20;

    private const NARRATED = 20;

    public const PROMINENCE_MAX = 30;

    public function __construct(private readonly ListEntitiesAction $list) {}

    /**
     * @param  list<string>|null  $types  EntityType values
     * @return array{items: list<Entity>, total: int, capped: bool}
     */
    public function __invoke(string $query, ?array $types, ?int $year, int $limit, ?int $totalCap = null): array
    {
        $query = trim($query);
        $page = ($this->list)(EntityFilterData::fromArray([
            'search' => $query,
            'types' => $types,
            'exists_at' => $year,
            'per_page' => self::CANDIDATES,
        ]), totalCap: $totalCap);

        /** @var Collection<string, Entity> $candidates */
        $candidates = collect($page->items())->keyBy('entity_id');
        foreach ($this->important($query, $types, $year) as $entity) {
            if (! $candidates->has($entity->entity_id)) {
                $candidates->put($entity->entity_id, $entity);
            }
        }

        $mentions = DB::table('chronicle_entry_entities')
            ->whereIn('entity_id', $candidates->keys()->all())
            ->groupBy('entity_id')
            ->selectRaw('entity_id, count(*) AS n')
            ->pluck('n', 'entity_id');

        $ranked = SearchRanking::rank(
            $candidates->values()->all(),
            $query,
            fn (Entity $e): string => (string) $e->name,
            fn (Entity $e): float => (float) ($e->impact_score ?? SearchRanking::DEFAULT_IMPACT)
                + self::prominence((int) ($mentions[$e->entity_id] ?? 0)),
        );

        return [
            'items' => array_slice($ranked, 0, $limit),
            'total' => $page->total(),
            'capped' => (bool) ($page->totalCapped ?? false),
        ];
    }

    /**
     * @param  list<string>|null  $types
     * @return list<Entity>
     */
    private function important(string $query, ?array $types, ?int $year): array
    {
        if (mb_strlen($query) < 2) {
            return [];
        }
        $base = fn () => Entity::query()->withGeoJson()
            ->when($types, fn ($q) => $q->ofTypes(array_map(fn (string $t) => EntityType::from($t), $types)))
            ->when($year !== null, fn ($q) => $q->existsAt((int) $year))
            ->orderByRaw('impact_score DESC NULLS LAST');

        // The trigram index serves an anchored-at-word-start regex.
        $wordStart = $base()->whereRaw('name ~* ?', ['\m'.preg_quote($query, '/')])->limit(self::WORD_START)->get();
        $exact = $base()->whereRaw('lower(name) = ?', [mb_strtolower($query)])->limit(self::EXACT)->get();

        $narratedIds = DB::table('chronicle_entry_entities AS c')
            ->join('entities AS e', 'e.entity_id', '=', 'c.entity_id')
            ->whereRaw('e.name ~* ?', ['\\m'.preg_quote($query, '/')])
            ->groupBy('c.entity_id')
            ->orderByRaw('count(*) DESC')
            ->limit(self::NARRATED)
            ->pluck('c.entity_id');
        $narrated = $narratedIds->isEmpty() ? collect() : $base()->whereIn('entity_id', $narratedIds)->get();

        return [...$wordStart->all(), ...$exact->all(), ...$narrated->all()];
    }

    /** Points for being mentioned in chronicles: 0, then 6, 9, 11 … capped. */
    public static function prominence(int $mentions): float
    {
        return min(self::PROMINENCE_MAX, round(8 * log(1 + max(0, $mentions)), 1));
    }
}
