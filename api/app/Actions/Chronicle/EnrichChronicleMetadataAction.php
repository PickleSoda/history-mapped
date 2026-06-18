<?php

declare(strict_types=1);

namespace App\Actions\Chronicle;

use App\Models\Chronicle;
use App\Models\ChronicleEntry;
use App\Models\Entity;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * Populate derived chronicle/entry fields from the entries' resolved
 * relationships and entities.
 *
 * Runs after entries (and their secondary entities) are persisted, so the
 * authoritative entity impact scores and locations are available:
 *  - entry.impact_score        = max impact of the entry's involved entities
 *  - entry.approximate_location = {lat,lon} of the highest-impact involved entity
 *  - entry.start_year/end_year  = kept (pipeline event dates) or backfilled from
 *                                 the primary relationship
 *  - chronicle.*                = aggregate (min start, max end, max impact, and
 *                                 the location of its most significant entry)
 *
 * Existing (non-null) values are preserved; this only fills gaps + aggregates.
 */
class EnrichChronicleMetadataAction
{
    /**
     * Weight of the peak (single most significant entity) vs the mean of all
     * involved entities when scoring a chronicle. Peak dominates so a chronicle
     * about a major polity still ranks high; the mean spreads the score by how
     * much *other* significant content the chronicle carries.
     */
    private const PEAK_WEIGHT = 0.7;

    /**
     * Score a chronicle's impact by blending its peak involved-entity impact
     * with the mean across all involved entities. Pure so it can be unit-tested
     * without a DB.
     *
     * The old behaviour (raw max of involved-entity impact) saturated — almost
     * every chronicle contains one ~98 polity, so 84% scored an identical 98,
     * and entry-count breadth did not help because these chronicles are large.
     * Blending in the mean differentiates a chronicle dense with major entities
     * from one that merely name-drops a single empire among minor figures.
     */
    public static function computeChronicleImpact(?int $peak, ?float $mean): ?int
    {
        if ($peak === null) {
            return null;
        }

        $mean ??= (float) $peak;
        $blended = self::PEAK_WEIGHT * $peak + (1.0 - self::PEAK_WEIGHT) * $mean;

        return max(1, min(100, (int) round($blended)));
    }

    public function __invoke(Chronicle $chronicle): void
    {
        $chronicle->load([
            'entries.secondaryEntities',
            'entries.primaryRelationship.sourceEntity',
            'entries.primaryRelationship.targetEntity',
        ]);

        $entityIds = $this->allEntityIds($chronicle);
        $points = $this->entityPoints($entityIds);
        $years = $this->entityYears($entityIds);

        $start = null;
        $end = null;
        $impact = null;
        $location = null;
        $locationImpact = -1;
        $involvedImpacts = [];

        foreach ($chronicle->entries as $entry) {
            $entities = $this->involvedEntities($entry);

            $entryImpact = $entities->max('impact_score');
            foreach ($entities as $involved) {
                if ($involved->impact_score !== null) {
                    $involvedImpacts[] = (int) $involved->impact_score;
                }
            }
            [$relStart, $relEnd] = $this->relationshipYears($entry);
            [$entStart, $entEnd] = $this->yearsFromEntities($entities, $years);
            $entryLocation = $this->representativePoint($entities, $points);

            // Year priority: pipeline event date -> primary relationship ->
            // listed entities (so an entry with no relation still gets a year
            // for map/timeline filtering).
            $entry->forceFill([
                'start_year' => $entry->start_year ?? $relStart ?? $entStart,
                'end_year' => $entry->end_year ?? $relEnd ?? $entEnd,
                'impact_score' => $entryImpact ?? $entry->impact_score,
                'approximate_location' => $entryLocation ?? $entry->approximate_location,
            ])->save();

            if ($entry->start_year !== null) {
                $start = $start === null ? $entry->start_year : min($start, $entry->start_year);
            }
            if ($entry->end_year !== null) {
                $end = $end === null ? $entry->end_year : max($end, $entry->end_year);
            }
            if ($entryImpact !== null) {
                $impact = $impact === null ? $entryImpact : max($impact, $entryImpact);
            }
            if ($entryLocation !== null && (int) ($entryImpact ?? 0) > $locationImpact) {
                $locationImpact = (int) ($entryImpact ?? 0);
                $location = $entryLocation;
            }
        }

        $meanImpact = $involvedImpacts === []
            ? null
            : array_sum($involvedImpacts) / count($involvedImpacts);

        $chronicle->forceFill([
            'start_year' => $chronicle->start_year ?? $start,
            'end_year' => $chronicle->end_year ?? $end,
            'impact_score' => self::computeChronicleImpact($impact, $meanImpact)
                ?? $chronicle->impact_score,
            'approximate_location' => $location ?? $chronicle->approximate_location,
        ])->save();
    }

    /**
     * Secondary entities + the primary relationship's two endpoints, deduped.
     *
     * @return Collection<int, Entity>
     */
    private function involvedEntities(ChronicleEntry $entry): Collection
    {
        $entities = $entry->secondaryEntities->all();

        $relationship = $entry->primaryRelationship;
        if ($relationship?->sourceEntity) {
            $entities[] = $relationship->sourceEntity;
        }
        if ($relationship?->targetEntity) {
            $entities[] = $relationship->targetEntity;
        }

        return collect($entities)->unique('entity_id')->values();
    }

    /**
     * @return array{0: int|null, 1: int|null}
     */
    private function relationshipYears(ChronicleEntry $entry): array
    {
        $relationship = $entry->primaryRelationship;

        return [$relationship?->start_year, $relationship?->end_year];
    }

    /**
     * Span of the involved entities: earliest start, latest end.
     *
     * @param  Collection<int, Entity>  $entities
     * @param  array<string, array{start: int|null, end: int|null}>  $years
     * @return array{0: int|null, 1: int|null}
     */
    private function yearsFromEntities(Collection $entities, array $years): array
    {
        $starts = [];
        $ends = [];
        foreach ($entities as $entity) {
            $range = $years[$entity->entity_id] ?? null;
            if ($range === null) {
                continue;
            }
            if ($range['start'] !== null) {
                $starts[] = $range['start'];
            }
            if ($range['end'] !== null) {
                $ends[] = $range['end'];
            }
        }

        return [
            $starts === [] ? null : min($starts),
            $ends === [] ? null : max($ends),
        ];
    }

    /**
     * @param  Collection<int, Entity>  $entities
     * @param  array<string, array{lat: float, lon: float}>  $points
     * @return array{lat: float, lon: float}|null
     */
    private function representativePoint(Collection $entities, array $points): ?array
    {
        $ordered = $entities->sortByDesc(fn (Entity $entity): int => (int) ($entity->impact_score ?? 0));

        foreach ($ordered as $entity) {
            if (isset($points[$entity->entity_id])) {
                return $points[$entity->entity_id];
            }
        }

        return null;
    }

    /**
     * @return list<string>
     */
    private function allEntityIds(Chronicle $chronicle): array
    {
        $ids = [];
        foreach ($chronicle->entries as $entry) {
            foreach ($this->involvedEntities($entry) as $entity) {
                $ids[] = $entity->entity_id;
            }
        }

        return array_values(array_unique($ids));
    }

    /**
     * Representative point per entity: its primary location point, or the
     * centroid of its territory polygon as a fallback.
     *
     * @param  list<string>  $entityIds
     * @return array<string, array{lat: float, lon: float}>
     */
    private function entityPoints(array $entityIds): array
    {
        if (empty($entityIds)) {
            return [];
        }

        $rows = DB::table('entity_locations')
            ->whereIn('entity_id', $entityIds)
            ->where('is_primary', true)
            ->whereRaw('(geom IS NOT NULL OR territory_geom IS NOT NULL)')
            ->selectRaw('entity_id,
                ST_Y(COALESCE(geom, ST_Centroid(territory_geom))) as lat,
                ST_X(COALESCE(geom, ST_Centroid(territory_geom))) as lon')
            ->get();

        $map = [];
        foreach ($rows as $row) {
            $map[$row->entity_id] = [
                'lat' => round((float) $row->lat, 5),
                'lon' => round((float) $row->lon, 5),
            ];
        }

        return $map;
    }

    /**
     * Primary temporal range (start_year/end_year) per entity.
     *
     * @param  list<string>  $entityIds
     * @return array<string, array{start: int|null, end: int|null}>
     */
    private function entityYears(array $entityIds): array
    {
        if (empty($entityIds)) {
            return [];
        }

        $rows = DB::table('entity_temporal_ranges')
            ->whereIn('entity_id', $entityIds)
            ->where('is_primary', true)
            ->select('entity_id', 'start_year', 'end_year')
            ->get();

        $map = [];
        foreach ($rows as $row) {
            $map[$row->entity_id] = [
                'start' => $row->start_year !== null ? (int) $row->start_year : null,
                'end' => $row->end_year !== null ? (int) $row->end_year : null,
            ];
        }

        return $map;
    }
}
