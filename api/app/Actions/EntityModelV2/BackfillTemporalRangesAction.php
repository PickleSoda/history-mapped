<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityTemporalRange;

class BackfillTemporalRangesAction
{
    public function __invoke(Entity $entity): int
    {
        $startYear = $entity->getAttribute('temporal_start_year') ?? self::extractYear($entity->temporal_start);
        $endYear = $entity->getAttribute('temporal_end_year') ?? self::extractYear($entity->temporal_end);

        if ($startYear === null && $endYear === null && $entity->temporal_start === null && $entity->temporal_end === null) {
            return 0;
        }

        EntityTemporalRange::query()
            ->where('entity_id', $entity->entity_id)
            ->where('is_primary', true)
            ->delete();

        EntityTemporalRange::query()->create([
            'entity_id' => $entity->entity_id,
            'range_type' => 'primary',
            'start_year' => $startYear,
            'end_year' => $endYear,
            'start_date' => $entity->temporal_start,
            'end_date' => $entity->temporal_end,
            'duration_type' => $entity->duration_type?->value,
            'date_method' => $entity->date_method?->value,
            'date_confidence' => $entity->date_confidence?->value,
            'is_primary' => true,
        ]);

        return 1;
    }

    private static function extractYear(?string $temporal): ?int
    {
        if ($temporal === null || trim($temporal) === '') {
            return null;
        }

        if (! preg_match('/^-?\\d+/', $temporal, $matches)) {
            return null;
        }

        return (int) $matches[0];
    }
}
