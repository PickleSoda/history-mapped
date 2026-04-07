<?php

declare(strict_types=1);

namespace App\Actions\Timeline;

use App\Models\EntityTimelineEntry;
use App\Models\GeometryPeriod;
use Illuminate\Support\Facades\DB;

/**
 * Rebuild materialized timeline entries for one entity (or all entities).
 */
class ProjectEntityTimelineAction
{
    /**
     * @return int Number of inserted timeline entries.
     */
    public function __invoke(?string $entityId = null): int
    {
        if ($entityId !== null) {
            return $this->rebuildForEntity($entityId);
        }

        $entityIds = GeometryPeriod::query()
            ->distinct()
            ->orderBy('entity_id')
            ->pluck('entity_id');

        $inserted = 0;

        foreach ($entityIds as $id) {
            $inserted += $this->rebuildForEntity($id);
        }

        return $inserted;
    }

    /**
     * @return int Number of inserted timeline entries.
     */
    public function rebuildForEntity(string $entityId): int
    {
        DB::transaction(function () use ($entityId): void {
            EntityTimelineEntry::query()->where('entity_id', $entityId)->delete();
        });

        $periods = GeometryPeriod::query()
            ->where('entity_id', $entityId)
            ->with([
                'relationship.sourceEntity',
                'relationship.targetEntity',
                'sourceEvent',
            ])
            ->orderBy('start_year')
            ->orderBy('end_year')
            ->get();

        $inserted = 0;

        foreach ($periods as $period) {
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

            EntityTimelineEntry::query()->create([
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
            ]);

            $inserted++;
        }

        return $inserted;
    }
}
