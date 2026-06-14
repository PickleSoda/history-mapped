<?php

declare(strict_types=1);

namespace App\Observers;

use App\Models\EntityRelationship;
use App\Support\TimelineRebuild;

class EntityRelationshipObserver
{
    public function created(EntityRelationship $relationship): void
    {
        $this->queueBoth($relationship);
    }

    public function updated(EntityRelationship $relationship): void
    {
        $this->queueBoth($relationship);
    }

    public function deleted(EntityRelationship $relationship): void
    {
        $this->queueBoth($relationship);
    }

    /**
     * A relationship surfaces on both endpoints' timelines, so rebuild both.
     */
    private function queueBoth(EntityRelationship $relationship): void
    {
        TimelineRebuild::queue((string) $relationship->source_entity_id);
        TimelineRebuild::queue((string) $relationship->target_entity_id);
    }
}
