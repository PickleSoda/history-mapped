<?php

declare(strict_types=1);

namespace App\Observers;

use App\Models\GeometryPeriod;
use App\Support\TimelineRebuild;

class GeometryPeriodObserver
{
    public function created(GeometryPeriod $period): void
    {
        TimelineRebuild::queue((string) $period->entity_id);
    }

    public function updated(GeometryPeriod $period): void
    {
        TimelineRebuild::queue((string) $period->entity_id);
    }

    public function deleted(GeometryPeriod $period): void
    {
        TimelineRebuild::queue((string) $period->entity_id);
    }
}
