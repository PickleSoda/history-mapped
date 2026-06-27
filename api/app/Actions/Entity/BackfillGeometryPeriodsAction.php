<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Enums\EntityGroup;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use App\Models\GeometryPeriod;

class BackfillGeometryPeriodsAction
{
    public function __invoke(Entity $entity): int
    {
        $entity = Entity::query()
            ->withoutGlobalScopes()
            ->with(['primaryLocation', 'primaryTemporalRange'])
            ->findOrFail($entity->entity_id);

        $primaryLocation = $entity->primaryLocation;
        $geom = $primaryLocation?->geom;
        $territoryGeom = $primaryLocation?->territory_geom;

        // Events are momentary: an open (NULL) end means "end unknown", NOT
        // "ongoing to the present". Collapsing it to a point (end = start) keeps the
        // map's int4range from rendering a one-day battle across every later century
        // up to today. Non-event entities (polities, monuments) keep NULL = ongoing.
        $isEvent = $entity->entity_group === EntityGroup::Event;

        GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provenance_mode', 'manual')
            ->where('created_by', 'backfill:entity')
            ->delete();

        GeometryPeriod::query()
            ->where('entity_id', $entity->entity_id)
            ->where('provenance_mode', 'derived')
            ->where('created_by', 'backfill:entity')
            ->whereNotNull('relationship_id')
            ->delete();

        // Supersede stale low-confidence relationship-inference geometry. Once an
        // entity has its own primary-location geometry, the 0.40-confidence
        // neighbour guesses written by pipeline/backfill_geo.py (which can land an
        // abstract/extended entity on the wrong continent — e.g. "Papacy" placed
        // in Canada) are replaced by the authoritative location-derived periods
        // created below. Gated on real geometry so we never strip an entity's only
        // point: with no own location, the inferred guess is its only signal.
        if ($geom !== null || $territoryGeom !== null) {
            GeometryPeriod::query()
                ->where('entity_id', $entity->entity_id)
                ->where('created_by', 'geo-backfill:relationship_inference')
                ->delete();
        }

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
                // Preserve an open end (NULL = ongoing) so the map's int4range shows
                // the point from start_year onward. Collapsing NULL to start_year
                // (the old `?? start_year`) made every still-extant entity — e.g.
                // gunpowder, 800→present — render at exactly ONE year and vanish
                // otherwise. A genuine point-in-time entity carries end_year=start.
                $endYear = $range->end_year;

                if ($endYear === null && $isEvent) {
                    $endYear = $startYear;
                }

                if ($startYear === null) {
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
                    'created_by' => 'backfill:entity',
                ]);

                $inserted++;
            }
        }

        if ($inserted > 0) {
            return $inserted;
        }

        $primaryRange = $entity->primaryTemporalRange;
        $startYear = $primaryRange?->start_year ?? $primaryRange?->end_year;
        $endYear = $primaryRange?->end_year;  // keep NULL = ongoing (see above)

        if ($endYear === null && $isEvent) {
            $endYear = $startYear;
        }

        if ($geom !== null || $territoryGeom !== null) {
            if ($startYear !== null) {
                GeometryPeriod::query()->create([
                    'entity_id' => $entity->entity_id,
                    'period_type' => 'territory',
                    'start_year' => $startYear,
                    'end_year' => $endYear,
                    'geom' => $geom,
                    'territory_geom' => $territoryGeom,
                    'provenance_mode' => 'manual',
                    'created_by' => 'backfill:entity',
                ]);

                return 1;
            }
        }

        return 0;
    }
}
