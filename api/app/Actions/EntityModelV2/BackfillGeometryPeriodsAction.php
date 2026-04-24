<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;

class BackfillGeometryPeriodsAction
{
    public function __invoke(Entity $entity): int
    {
        $primaryLocation = $entity->primaryLocation;
        $geom = $primaryLocation?->geom;
        $territoryGeom = $primaryLocation?->territory_geom;

        GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provenance_mode', 'manual')
            ->where('created_by', 'backfill:entity-model-v2')
            ->delete();

        GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provenance_mode', 'derived')
            ->where('created_by', 'backfill:entity-model-v2')
            ->whereNotNull('relationship_id')
            ->delete();

        $ranges = EntityTemporalRange::query()
            ->where('entity_id', $entity->entity_id)
            ->where(function ($query): void {
                $query->whereNotNull('start_year')
                    ->orWhereNotNull('end_year');
            })
            ->orderByDesc('is_primary')
            ->orderBy('start_year')
            ->get();

        $inserted = 0;

        if ($geom !== null || $territoryGeom !== null) {
            foreach ($ranges as $range) {
                $startYear = $range->start_year ?? $range->end_year;
                $endYear = $range->end_year ?? $range->start_year;

                if ($startYear === null || $endYear === null) {
                    continue;
                }

                GeometryPeriod::query()->create([
                    'entity_id' => $entity->entity_id,
                    'period_type' => 'territory',
                    'start_year' => $startYear,
                    'end_year' => $endYear,
                    'geom' => $geom,
                    'territory_geom' => $territoryGeom,
                    'description' => $range->notes,
                    'provenance_mode' => 'manual',
                    'created_by' => 'backfill:entity-model-v2',
                ]);

                $inserted++;
            }
        }

        if ($inserted > 0) {
            $inserted += $this->backfillDerivedPresencePeriods($entity, $ranges, $geom, $territoryGeom);

            return $inserted;
        }

        $primaryRange = $entity->primaryTemporalRange;
        $startYear = $primaryRange?->start_year ?? $primaryRange?->end_year;
        $endYear = $primaryRange?->end_year ?? $primaryRange?->start_year;

        if ($geom !== null || $territoryGeom !== null) {
            if ($startYear !== null && $endYear !== null) {
                GeometryPeriod::query()->create([
                    'entity_id' => $entity->entity_id,
                    'period_type' => 'territory',
                    'start_year' => $startYear,
                    'end_year' => $endYear,
                    'geom' => $geom,
                    'territory_geom' => $territoryGeom,
                    'provenance_mode' => 'manual',
                    'created_by' => 'backfill:entity-model-v2',
                ]);

                return 1 + $this->backfillDerivedPresencePeriods($entity, $ranges, $geom, $territoryGeom);
            }
        }

        return $this->backfillDerivedPresencePeriods($entity, $ranges, $geom, $territoryGeom);
    }

    /**
     * @param  \Illuminate\Support\Collection<int, EntityTemporalRange>  $ranges
     */
    private function backfillDerivedPresencePeriods(Entity $entity, $ranges, ?array $geom, ?array $territoryGeom): int
    {
        $primaryRange = $ranges->firstWhere('is_primary', true) ?? $ranges->first();

        $fallbackStart = $primaryRange?->start_year ?? $entity->primaryTemporalRange?->start_year;
        $fallbackEnd = $primaryRange?->end_year ?? $entity->primaryTemporalRange?->end_year;

        $relationships = EntityRelationship::query()
            ->with([
                'sourceEntity' => fn ($query) => $query
                    ->withoutGlobalScopes()
                    ->with(['primaryLocation', 'primaryTemporalRange']),
                'targetEntity' => fn ($query) => $query
                    ->withoutGlobalScopes()
                    ->with(['primaryLocation', 'primaryTemporalRange']),
            ])
            ->where(function ($query) use ($entity): void {
                $query->where('source_entity_id', $entity->entity_id)
                    ->orWhere('target_entity_id', $entity->entity_id);
            })
            ->get();

        $inserted = 0;

        foreach ($relationships as $relationship) {
            $startYear = $relationship->start_year ?? $fallbackStart ?? $relationship->end_year ?? $fallbackEnd;
            $endYear = $relationship->end_year ?? $fallbackEnd ?? $relationship->start_year ?? $fallbackStart;

            $counterparty = $relationship->source_entity_id === $entity->entity_id
                ? $relationship->targetEntity
                : $relationship->sourceEntity;

            $derivedGeom = $counterparty?->primaryLocation?->geom ?? $geom;
            $derivedTerritory = $counterparty?->primaryLocation?->territory_geom ?? $territoryGeom;

            if ($startYear === null || $endYear === null) {
                continue;
            }

            if ($derivedGeom === null && $derivedTerritory === null) {
                continue;
            }

            GeometryPeriod::query()->create([
                'entity_id' => $entity->entity_id,
                'period_type' => 'presence',
                'start_year' => $startYear,
                'end_year' => $endYear,
                'geom' => $derivedGeom,
                'territory_geom' => $derivedTerritory,
                'description' => $relationship->description,
                'provenance_mode' => 'derived',
                'relationship_id' => $relationship->relationship_id,
                'created_by' => 'backfill:entity-model-v2',
            ]);

            $inserted++;
        }

        return $inserted;
    }
}
