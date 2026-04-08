<?php

declare(strict_types=1);

namespace App\Observers;

use App\Jobs\RebuildEntityTimelineJob;
use App\Models\EntityTemporalRange;

class EntityTemporalRangeObserver
{
    public function created(EntityTemporalRange $range): void
    {
        RebuildEntityTimelineJob::dispatch($range->entity_id);
    }

    public function updated(EntityTemporalRange $range): void
    {
        RebuildEntityTimelineJob::dispatch($range->entity_id);
    }

    public function deleted(EntityTemporalRange $range): void
    {
        RebuildEntityTimelineJob::dispatch($range->entity_id);
    }
}
