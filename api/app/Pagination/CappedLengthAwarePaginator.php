<?php

declare(strict_types=1);

namespace App\Pagination;

use Illuminate\Pagination\LengthAwarePaginator;

/**
 * A length-aware paginator whose total was counted only up to a cap. When
 * the count stopped at the cap, `total` is the cap and `total_capped` is
 * true; JSON resources copy both into the response's `meta`.
 *
 * @template TKey of array-key
 * @template TValue
 *
 * @extends LengthAwarePaginator<TKey, TValue>
 */
class CappedLengthAwarePaginator extends LengthAwarePaginator
{
    public bool $totalCapped = false;

    /**
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        return [...parent::toArray(), 'total_capped' => $this->totalCapped];
    }
}
