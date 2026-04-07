<?php

declare(strict_types=1);

namespace App\Actions\Timeline;

use App\Builders\EntityTimelineEntryBuilder;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use App\Models\EntityTimelineEntry;
use App\Models\GeometryPeriod;
use Illuminate\Support\Facades\DB;

/**
 * Rebuild materialized timeline entries for one entity (or all entities).
 */
class ProjectEntityTimelineAction
{
    public function __construct(private readonly EntityTimelineEntryBuilder $entryBuilder) {}

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
            ->pluck('entity_id')
            ->merge(
                EntityTemporalRange::query()
                    ->distinct()
                    ->pluck('entity_id'),
            )
            ->unique()
            ->sort()
            ->values();

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
            if (! $period instanceof GeometryPeriod) {
                continue;
            }

            EntityTimelineEntry::query()->create(
                $this->entryBuilder->fromGeometryPeriod($period, $entityId),
            );

            $inserted++;
        }

        if ($inserted === 0) {
            $primaryTemporalRange = EntityTemporalRange::query()
                ->where('entity_id', $entityId)
                ->where(function ($query): void {
                    $query->whereNotNull('start_year')
                        ->orWhereNotNull('end_year');
                })
                ->orderByDesc('is_primary')
                ->orderBy('start_year')
                ->first();

            if ($primaryTemporalRange !== null) {
                $entityName = (string) (Entity::query()
                    ->where('entity_id', $entityId)
                    ->value('name') ?? 'Unknown entity');

                EntityTimelineEntry::query()->create(
                    $this->entryBuilder->fromPrimaryTemporalRange($primaryTemporalRange, $entityName),
                );

                $inserted++;
            }
        }

        return $inserted;
    }
}
