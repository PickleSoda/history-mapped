<?php

declare(strict_types=1);

namespace App\Observers;

use App\Models\EntityLocation;
use App\Support\TimelineRebuild;

class EntityLocationObserver
{
    public function created(EntityLocation $location): void
    {
        TimelineRebuild::queue((string) $location->entity_id);
    }

    public function updated(EntityLocation $location): void
    {
        TimelineRebuild::queue((string) $location->entity_id);
    }

    public function deleted(EntityLocation $location): void
    {
        TimelineRebuild::queue((string) $location->entity_id);
    }
}
