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
        $inserted = DB::transaction(function () use ($entityId): int {
            EntityTimelineEntry::query()->where('entity_id', $entityId)->delete();

            $periodCount = GeometryPeriod::query()
                ->where('entity_id', $entityId)
                ->count();

            if ($periodCount === 0) {
                return 0;
            }

            $relatedEntityIdSql = <<<'SQL'
CASE
    WHEN gp.relationship_id IS NOT NULL AND rel.source_entity_id = ? THEN target_entity.entity_id
    WHEN gp.relationship_id IS NOT NULL THEN source_entity.entity_id
    WHEN gp.source_event_id IS NOT NULL THEN source_event.entity_id
    ELSE NULL
END
SQL;

            $relatedEntityNameSql = <<<'SQL'
CASE
    WHEN gp.relationship_id IS NOT NULL AND rel.source_entity_id = ? THEN target_entity.name
    WHEN gp.relationship_id IS NOT NULL THEN source_entity.name
    WHEN gp.source_event_id IS NOT NULL THEN source_event.name
    ELSE NULL
END
SQL;

            $projection = DB::table('geometry_periods as gp')
                ->leftJoin('relationships as rel', 'rel.relationship_id', '=', 'gp.relationship_id')
                ->leftJoin('entities as source_entity', 'source_entity.entity_id', '=', 'rel.source_entity_id')
                ->leftJoin('entities as target_entity', 'target_entity.entity_id', '=', 'rel.target_entity_id')
                ->leftJoin('entities as source_event', 'source_event.entity_id', '=', 'gp.source_event_id')
                ->where('gp.entity_id', $entityId)
                ->orderBy('gp.start_year')
                ->orderBy('gp.end_year')
                ->selectRaw('? as entity_id', [$entityId])
                ->selectRaw("CASE WHEN gp.period_type = 'presence' THEN 'relationship_presence' ELSE 'territory_period' END as entry_kind")
                ->addSelect([
                    'gp.start_year',
                    'gp.end_year',
                ])
                ->selectRaw(
                    "COALESCE(($relatedEntityNameSql), gp.description, CASE WHEN gp.period_type = 'presence' THEN 'Presence period' ELSE 'Territory period' END) as title",
                    [$entityId],
                )
                ->selectRaw('COALESCE(gp.description, rel.description) as description')
                ->addSelect([
                    'gp.source_event_id as location_entity_id',
                    'gp.geom',
                    'gp.territory_geom',
                ])
                ->selectRaw("'geometry_periods' as source_table")
                ->addSelect([
                    'gp.geometry_period_id as source_id',
                    'rel.relationship_type',
                ])
                ->selectRaw("($relatedEntityIdSql) as related_entity_id", [$entityId])
                ->selectRaw("($relatedEntityNameSql) as related_entity_name", [$entityId])
                ->selectRaw('CURRENT_TIMESTAMP as derived_at');

            DB::table('entity_timeline_entries')->insertUsing([
                'entity_id',
                'entry_kind',
                'start_year',
                'end_year',
                'title',
                'description',
                'location_entity_id',
                'geom',
                'territory_geom',
                'source_table',
                'source_id',
                'relationship_type',
                'related_entity_id',
                'related_entity_name',
                'derived_at',
            ], $projection);

            return $periodCount;
        });

        if ($inserted === 0) {
            $temporalRanges = EntityTemporalRange::query()
                ->where('entity_id', $entityId)
                ->where(function ($query): void {
                    $query->whereNotNull('start_year')
                        ->orWhereNotNull('end_year');
                })
                ->orderByDesc('is_primary')
                ->orderBy('start_year')
                ->get();

            if ($temporalRanges->isNotEmpty()) {
                $entityName = (string) (Entity::query()
                    ->where('entity_id', $entityId)
                    ->value('name') ?? 'Unknown entity');

                foreach ($temporalRanges as $range) {
                    if (! $range instanceof EntityTemporalRange) {
                        continue;
                    }

                    EntityTimelineEntry::query()->create(
                        $this->entryBuilder->fromPrimaryTemporalRange($range, $entityName),
                    );

                    $inserted++;
                }
            }
        }

        return $inserted;
    }
}
