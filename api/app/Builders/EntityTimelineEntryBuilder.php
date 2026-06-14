<?php

declare(strict_types=1);

namespace App\Builders;

use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;

class EntityTimelineEntryBuilder
{
    /**
     * @return array<string, mixed>
     */
    public function fromGeometryPeriod(GeometryPeriod $period, string $entityId): array
    {
        $relationship = $period->relationship;

        $relatedEntity = null;
        if ($relationship !== null) {
            $relatedEntity = $relationship->source_entity_id === $entityId
                ? $relationship->targetEntity
                : $relationship->sourceEntity;
        }

        if ($relatedEntity === null && $period->sourceEvent !== null) {
            $relatedEntity = $period->sourceEvent;
        }

        $entryKind = $period->period_type === 'presence'
            ? 'relationship_presence'
            : 'territory_period';

        $title = $relatedEntity?->name
            ?? $period->description
            ?? ($period->period_type === 'presence' ? 'Presence period' : 'Territory period');

        return [
            'entity_id' => $entityId,
            'entry_kind' => $entryKind,
            'start_year' => $period->start_year,
            'end_year' => $period->end_year,
            'title' => $title,
            'description' => $period->description ?? $relationship?->description,
            'location_entity_id' => $period->source_event_id,
            'geom' => $period->geom,
            'territory_geom' => $period->territory_geom,
            'source_table' => 'geometry_periods',
            'source_id' => $period->geometry_period_id,
            'relationship_type' => $relationship?->relationship_type?->value,
            'related_entity_id' => $relatedEntity?->entity_id,
            'related_entity_name' => $relatedEntity?->name,
            'derived_at' => now(),
        ];
    }

    /**
     * @return array<string, mixed>
     */
    public function fromPrimaryTemporalRange(EntityTemporalRange $range, string $entityName): array
    {
        $title = $range->is_primary
            ? 'Primary temporal range'
            : 'Temporal range';

        return [
            'entity_id' => $range->entity_id,
            'entry_kind' => 'temporal_range',
            // Coalesce symmetrically so an open-start range never writes NULL into
            // the NOT NULL start_year (LC-3); mirrors the end_year fallback.
            'start_year' => $range->start_year ?? $range->end_year,
            'end_year' => $range->end_year ?? $range->start_year,
            'title' => $title,
            'description' => $range->notes,
            'source_table' => 'entity_temporal_ranges',
            'source_id' => $range->temporal_range_id,
            'related_entity_name' => $entityName,
            'derived_at' => now(),
        ];
    }
}
