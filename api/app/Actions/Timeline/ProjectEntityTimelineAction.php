<?php

declare(strict_types=1);

namespace App\Actions\Timeline;

use App\Builders\EntityTimelineEntryBuilder;
use App\Models\Entity;
use App\Models\EntityRelationship;
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
            ->merge(
                EntityRelationship::query()
                    ->distinct()
                    ->pluck('source_entity_id'),
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

            $inserted = 0;

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

            if ($periodCount > 0) {
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

                $inserted += $periodCount;
            }

            // Insert timeline entries for relationships that have no derived geometry period.
            // This covers both: derive_geometry_period = false, and relationships with no
            // start_year (we skip those since a timeline entry requires at least start_year).
            $relationshipsWithoutPeriod = DB::table('relationships as rel')
                ->leftJoin('geometry_periods as gp', 'gp.relationship_id', '=', 'rel.relationship_id')
                ->leftJoin('entities as target_entity', 'target_entity.entity_id', '=', 'rel.target_entity_id')
                ->where('rel.source_entity_id', $entityId)
                ->whereNull('gp.geometry_period_id')
                ->whereNotNull('rel.start_year')
                ->orderBy('rel.start_year')
                ->selectRaw('? as entity_id', [$entityId])
                ->selectRaw("'relationship' as entry_kind")
                ->addSelect(['rel.start_year', 'rel.end_year'])
                ->selectRaw("COALESCE(rel.description, target_entity.name, 'Relationship') as title")
                ->selectRaw('rel.description as description')
                ->selectRaw('NULL::uuid as location_entity_id')
                ->selectRaw('NULL::geometry as geom')
                ->selectRaw('NULL::geometry as territory_geom')
                ->selectRaw("'relationships' as source_table")
                ->addSelect(['rel.relationship_id as source_id'])
                ->selectRaw('rel.relationship_type::text as relationship_type')
                ->addSelect(['target_entity.entity_id as related_entity_id'])
                ->addSelect(['target_entity.name as related_entity_name'])
                ->selectRaw('CURRENT_TIMESTAMP as derived_at');

            $relCount = DB::table('relationships as rel')
                ->leftJoin('geometry_periods as gp', 'gp.relationship_id', '=', 'rel.relationship_id')
                ->where('rel.source_entity_id', $entityId)
                ->whereNull('gp.geometry_period_id')
                ->whereNotNull('rel.start_year')
                ->count();

            if ($relCount > 0) {
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
                ], $relationshipsWithoutPeriod);

                $inserted += $relCount;
            }

            return $inserted;
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
