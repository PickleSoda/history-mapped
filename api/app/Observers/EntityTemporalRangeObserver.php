<?php

declare(strict_types=1);

namespace App\Observers;

use App\Models\EntityTemporalRange;
use App\Support\TimelineRebuild;

class EntityTemporalRangeObserver
{
    public function created(EntityTemporalRange $range): void
    {
        TimelineRebuild::queue((string) $range->entity_id);
    }

    public function updated(EntityTemporalRange $range): void
    {
        TimelineRebuild::queue((string) $range->entity_id);
    }

    public function deleted(EntityTemporalRange $range): void
    {
        TimelineRebuild::queue((string) $range->entity_id);
    }
}
