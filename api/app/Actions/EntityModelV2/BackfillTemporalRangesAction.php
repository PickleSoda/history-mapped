<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityTemporalRange;

class BackfillTemporalRangesAction
{
    public function __invoke(Entity $entity): int
    {
        $range = $entity->primaryTemporalRange;

        if ($range === null) {
            return 0;
        }

        EntityTemporalRange::query()
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_date' => $range->start_date,
            'end_date' => $range->end_date,
            'duration_type' => $range->duration_type,
            'date_method' => $range->date_method,
            'date_confidence' => $range->date_confidence,
            'is_primary' => true,
        ]);

        return 1;
    }
}
