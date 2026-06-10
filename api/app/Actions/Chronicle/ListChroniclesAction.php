<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;

class ListChroniclesAction
{
    /**
     * List chronicles with optional search and status filter.
     *
     * @param  array{search?: string|null, status?: string|null, page?: int, per_page?: int}  $filters
     * @return LengthAwarePaginator<Chronicle>
     */
    public function __invoke(array $filters = []): LengthAwarePaginator
    {
        $query = Chronicle::query()->withCount('entries');

        if (!empty($filters['search'])) {
            $query->where(function ($q) use ($filters) {
                $q->where('title', 'ilike', '%' . $filters['search'] . '%')
                  ->orWhere('slug', 'ilike', '%' . $filters['search'] . '%');
            });
        }

        if (!empty($filters['status'])) {
            $query->where('status', $filters['status']);
        }

        $perPage = min((int) ($filters['per_page'] ?? 20), 100);
        $page = max((int) ($filters['page'] ?? 1), 1);

        return $query->orderByDesc('created_at')->paginate($perPage, ['*'], 'page', $page);
    }
}
