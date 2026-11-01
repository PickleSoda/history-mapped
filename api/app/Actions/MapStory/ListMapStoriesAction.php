<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Http\Api\V1\Resources\MapStorySummaryResource;
use App\Models\MapStory;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;

class ListMapStoriesAction
{
    /**
     * A page of map stories (no documents), with the entity and chronicle
     * each is attached to. `sort`: `year` (oldest first, undated last) or
     * `title`; slug breaks ties so pages are stable.
     *
     * @param  array{kind?: list<string>|null, sort?: string|null, page?: int, per_page?: int}  $filters
     * @return LengthAwarePaginator<MapStory>
     */
    public function __invoke(array $filters = []): LengthAwarePaginator
    {
        $query = MapStory::query()
            ->select(MapStory::SUMMARY_COLUMNS)
            ->with(MapStorySummaryResource::RELATIONS);

        if (! empty($filters['kind'])) {
            $query->whereIn('kind', $filters['kind']);
        }

        match ($filters['sort'] ?? 'year') {
            'title' => $query->orderBy('title'),
            default => $query->orderByRaw('year ASC NULLS LAST')->orderBy('title'),
        };
        $query->orderBy('slug');

        $perPage = min((int) ($filters['per_page'] ?? 20), 100);
        $page = max((int) ($filters['page'] ?? 1), 1);

        return $query->paginate($perPage, ['*'], 'page', $page);
    }
}
