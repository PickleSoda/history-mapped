<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;

class ListChroniclesAction
{
    /**
     * List chronicles with optional search, status and tag filters.
     *
     * `search` matches the title, the slug, or the name of a tag the chronicle
     * carries ("bronze" finds every Bronze Age chronicle). `tags` filters by
     * slug: AND across facets, OR within a facet (see Tag::filterGroups()).
     *
     * @param  array{search?: string|null, status?: string|null, tags?: list<string>|null, sort?: string|null, page?: int, per_page?: int}  $filters
     * @return LengthAwarePaginator<Chronicle>
     */
    public function __invoke(array $filters = []): LengthAwarePaginator
    {
        $query = Chronicle::query()->withCount('entries')->with('tags');

        if (! empty($filters['search'])) {
            $search = '%'.$filters['search'].'%';
            $query->where(function ($q) use ($search) {
                $q->where('title', 'ilike', $search)
                    ->orWhere('slug', 'ilike', $search)
                    ->orWhereHas('tags', fn ($t) => $t->where('tags.name', 'ilike', $search));
            });
        }

        if (! empty($filters['status'])) {
            $query->where('status', $filters['status']);
        }

        if (! empty($filters['tags'])) {
            $query->withTags($filters['tags']);
        }

        match ($filters['sort'] ?? 'recent') {
            'chronological' => $query->orderByRaw('start_year ASC NULLS LAST')->orderBy('title'),
            'title' => $query->orderBy('title'),
            'impact' => $query->orderByRaw('impact_score DESC NULLS LAST')->orderBy('title'),
            default => $query->orderByDesc('created_at'),
        };

        $perPage = min((int) ($filters['per_page'] ?? 20), 100);
        $page = max((int) ($filters['page'] ?? 1), 1);

        return $query->paginate($perPage, ['*'], 'page', $page);
    }
}
