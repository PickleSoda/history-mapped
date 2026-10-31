<?php

declare(strict_types=1);

namespace App\Services\Geo;

use App\Enums\EntityGroup;
use App\Services\Ohm\OhmLookupService;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

/**
 * Turns a place name into usable coordinates for the admin AI's placement
 * tools: our own entities first (name, alias, trigram), then the OHM gazetteer.
 *
 * Many stored points are generic fallbacks — a capital's or a country's
 * centroid that a pipeline pinned hundreds of unrelated entities to (central
 * London, Rome, the middle of the US). A point shared by that many entities
 * says nothing about the entity itself, so such candidates are flagged
 * `approximate` and a small model is steered toward a better anchor.
 */
final class PlaceFinder
{
    /** A point this many entities share (or more) is a fallback centroid. */
    public const SHARED_POINT_THRESHOLD = 5;

    /** Two points closer than this (degrees, ~0.1 m) are "the same point". */
    private const SAME_POINT_DEG = 1e-6;

    private const POINT_SQL = 'ST_PointOnSurface(el.geom)';

    /** The entity's name or one of its aliases equals the query (case-insensitive). */
    private const EXACT_MATCH_SQL = '(LOWER(e.name) = LOWER(?) OR EXISTS (SELECT 1 FROM entity_aliases ea2 WHERE ea2.entity_id = e.entity_id AND LOWER(ea2.name) = LOWER(?)))';

    public function __construct(
        private OhmLookupService $ohm,
    ) {}

    /**
     * Our entities matching `$name` that have a primary point: exact name or
     * alias first, then (when given) those that existed in `$year`, then by
     * name similarity and prominence.
     *
     * @return list<array<string, mixed>>
     */
    public function searchEntities(string $name, ?string $entityType = null, ?int $year = null, int $limit = 5): array
    {
        $like = '%'.addcslashes($name, '%_\\').'%';

        $query = $this->pointQuery()
            ->where(function (Builder $q) use ($name, $like): void {
                $q->whereRaw('e.name % ?', [$name])
                    ->orWhere('e.name', 'ILIKE', $like)
                    ->orWhereExists(fn (Builder $s) => $this->aliasMatch($s, $name));
            })
            ->when($entityType !== null, fn (Builder $q) => $q->where('e.entity_type', $entityType))
            ->selectRaw(self::EXACT_MATCH_SQL.' AS exact_name', [$name, $name])
            ->orderByRaw(self::EXACT_MATCH_SQL.' DESC', [$name, $name]);

        if ($year !== null) {
            $query->orderByRaw(
                "(int4range(etr.start_year, CASE WHEN etr.end_year IS NULL THEN NULL ELSE etr.end_year + 1 END, '[)') @> ?::integer) DESC NULLS LAST",
                [$year],
            );
        }

        $rows = $query
            ->orderByRaw('similarity(e.name, ?) DESC', [$name])
            ->orderByRaw('e.impact_score DESC NULLS LAST')
            ->limit($limit)
            ->get();

        return $rows->map(fn (object $row): array => $this->entityCandidate($row))->values()->all();
    }

    /**
     * The OHM gazetteer's matches for `$name`, as point candidates.
     *
     * @return list<array<string, mixed>>
     */
    public function searchOhm(string $name, int $limit = 3): array
    {
        $out = [];
        foreach ($this->ohm->searchByName($name) as $item) {
            $meta = $item['source_meta'] ?? [];
            if (! is_numeric($meta['lon'] ?? null) || ! is_numeric($meta['lat'] ?? null)) {
                continue;
            }
            $tags = $item['external_tags'] ?? [];

            $out[] = array_filter([
                'source' => 'ohm',
                'name' => $item['match_label'] ?? $item['display_name'] ?? $name,
                'display_name' => $item['display_name'] ?? null,
                'osm' => ($item['external_type'] ?? 'feature').'/'.($item['external_id'] ?? ''),
                'kind' => trim(($meta['class'] ?? '').'/'.($meta['type'] ?? ''), '/') ?: null,
                'start_date' => $tags['start_date'] ?? null,
                'end_date' => $tags['end_date'] ?? null,
                'lon' => round((float) $meta['lon'], 5),
                'lat' => round((float) $meta['lat'], 5),
                'precision' => 'exact',
            ], fn ($v) => $v !== null);

            if (count($out) >= $limit) {
                break;
            }
        }

        return $out;
    }

    /**
     * One entity's primary point, by UUID or by exact name / alias. Returns
     * `['error' => …]` when nothing (or more than one entity) matches.
     *
     * @return array<string, mixed>
     */
    public function entityPoint(string $ref): array
    {
        $query = $this->pointQuery();

        if (Str::isUuid($ref)) {
            $query->where('e.entity_id', $ref);
        } else {
            $query->where(function (Builder $q) use ($ref): void {
                $q->whereRaw('LOWER(e.name) = LOWER(?)', [$ref])
                    ->orWhereExists(fn (Builder $s) => $this->aliasMatch($s, $ref));
            });
        }

        $rows = $query->orderByRaw('e.impact_score DESC NULLS LAST')->limit(3)->get();

        if ($rows->isEmpty()) {
            return ['error' => "No entity '{$ref}' with a map point. Call find_place with the name and use a candidate's lon/lat."];
        }
        if ($rows->count() > 1) {
            return ['error' => "Several entities are named '{$ref}'. Call find_place and pass the right candidate's entity_id or lon/lat."];
        }

        return $this->entityCandidate($rows->first());
    }

    /** Entities joined to their primary point and primary date range. */
    private function pointQuery(): Builder
    {
        $point = self::POINT_SQL;

        return DB::table('entities as e')
            ->join('entity_locations as el', function ($join): void {
                $join->on('el.entity_id', '=', 'e.entity_id')->where('el.is_primary', true);
            })
            ->leftJoin('entity_temporal_ranges as etr', function ($join): void {
                $join->on('etr.entity_id', '=', 'e.entity_id')->where('etr.is_primary', true);
            })
            ->whereNotNull('el.geom')
            ->selectRaw(
                "e.entity_id, e.name, e.entity_type, e.entity_group, etr.start_year, etr.end_year, el.location_method, ST_X({$point}) AS lon, ST_Y({$point}) AS lat",
            );
    }

    private function aliasMatch(Builder $sub, string $name): Builder
    {
        return $sub->selectRaw('1')
            ->from('entity_aliases as ea')
            ->whereColumn('ea.entity_id', 'e.entity_id')
            ->whereRaw('LOWER(ea.name) = LOWER(?)', [$name]);
    }

    /** @return array<string, mixed> */
    private function entityCandidate(object $row): array
    {
        $lon = (float) $row->lon;
        $lat = (float) $row->lat;
        $sharedWith = $this->entitiesAtPoint($lon, $lat) - 1;
        // A PLACE sharing its point is usually the place the others were
        // pinned to (the city itself), so only non-places are downgraded.
        $approximate = $sharedWith + 1 >= self::SHARED_POINT_THRESHOLD
            && $row->entity_group !== EntityGroup::Place->value;

        return array_filter([
            'source' => 'entity',
            'entity_id' => $row->entity_id,
            'name' => $row->name,
            'entity_type' => $row->entity_type,
            'start_year' => $row->start_year,
            'end_year' => $row->end_year,
            'lon' => round($lon, 5),
            'lat' => round($lat, 5),
            'location_method' => $row->location_method,
            'exact_name' => isset($row->exact_name) ? (bool) $row->exact_name : null,
            'precision' => $approximate ? 'approximate' : 'exact',
            'note' => $approximate
                ? "This exact point is shared by {$sharedWith} other entities — a generic fallback (city or country centroid), not this entity's own position. Prefer a PLACE candidate or an OHM result as the anchor."
                : null,
        ], fn ($v) => $v !== null);
    }

    private function entitiesAtPoint(float $lon, float $lat): int
    {
        return (int) DB::table('entity_locations')
            ->where('is_primary', true)
            ->whereRaw('ST_DWithin(geom, ST_SetSRID(ST_MakePoint(?, ?), 4326), ?)', [$lon, $lat, self::SAME_POINT_DEG])
            ->count();
    }
}
