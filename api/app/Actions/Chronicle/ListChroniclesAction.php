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
     * Archived chronicles are left out unless `$includeArchived` is set (the
     * admin index sets it; the public API does not).
     *
     * `search` matches the title, the slug, or the name of a tag the chronicle
     * carries ("bronze" finds every Bronze Age chronicle). `tags` filters by
     * slug: AND across facets, OR within a facet (see Tag::filterGroups()).
     * `from` / `to` (years, BCE negative) keep chronicles whose span overlaps.
     *
     * @param  array{search?: string|null, status?: string|null, tags?: list<string>|null, from?: int|null, to?: int|null, sort?: string|null, page?: int, per_page?: int}  $filters
     * @return LengthAwarePaginator<Chronicle>
     */
    public function __invoke(array $filters = [], bool $includeArchived = false): LengthAwarePaginator
    {
        $query = Chronicle::query()->withCount('entries')->with('tags');

        if (! $includeArchived) {
            $query->notArchived();
        }

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

        // Chronicles whose span overlaps the window; an undated one never matches.
        if (isset($filters['from']) || isset($filters['to'])) {
            $query->whereNotNull('start_year');
            if (isset($filters['to'])) {
                $query->where('start_year', '<=', (int) $filters['to']);
            }
            if (isset($filters['from'])) {
                $query->whereRaw('COALESCE(end_year, start_year) >= ?', [(int) $filters['from']]);
            }
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
