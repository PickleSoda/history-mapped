<?php

declare(strict_types=1);

namespace App\Observers;

use App\Jobs\RebuildEntityTimelineJob;
use App\Models\GeometryPeriod;

class GeometryPeriodObserver
{
    public function created(GeometryPeriod $period): void
    {
        RebuildEntityTimelineJob::dispatch($period->entity_id);
    }

    public function updated(GeometryPeriod $period): void
    {
        RebuildEntityTimelineJob::dispatch($period->entity_id);
    }

    public function deleted(GeometryPeriod $period): void
    {
        RebuildEntityTimelineJob::dispatch($period->entity_id);
    }
}
