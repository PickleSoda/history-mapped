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
            'start_date' => $range->start_date ?? $this->formatYear($range->start_year),
            'end_date' => $range->end_date ?? $this->formatYear($range->end_year),
            'duration_type' => $range->duration_type,
            'date_method' => $range->date_method,
            'date_confidence' => $range->date_confidence,
            'is_primary' => true,
        ]);

        return 1;
    }

    private function formatYear(?int $year): ?string
    {
        if ($year === null) {
            return null;
        }

        $absoluteYear = str_pad((string) abs($year), 4, '0', STR_PAD_LEFT);

        return $year < 0 ? '-'.$absoluteYear : $absoluteYear;
    }
}
