<?php

declare(strict_types=1);

namespace App\Support\MapStory;

use App\Support\MapStory\MapStoryVocabulary as V;

/**
 * What a schema-3 story stores beside its document: its period, its extent,
 * and, for an ambient story, each step's faint atlas layer (`ambient_steps`,
 * served by GET /map-stories/ambient).
 *
 * Feature state resolves as in pipeline/map_stories/validate.py
 * (resolve_features): each key carries forward on its own, a `null` clears
 * it, and a new `at`/`line`/`area`/`area_from_entity` replaces the earlier
 * geometry. The colours are the ambient palette, mirrored by the web
 * (web/src/lib/map-story).
 */
final class MapStoryAmbient
{
    /** Route colour by `route_kind`, for a route with no side. */
    public const ROUTE_COLORS = [
        'trade' => '#b45309',
        'voyage' => '#0369a1',
        'migration' => '#7c3aed',
        'pilgrimage' => '#0f766e',
        'campaign' => '#b91c1c',
        'road' => '#57534e',
    ];

    /** Region colour by `region_kind`, for a region with no side. */
    public const REGION_COLORS = [
        'spread' => '#7f1d1d',
        'extent' => '#1d4ed8',
        'influence' => '#a16207',
        'affected' => '#c2410c',
        'front' => '#be123c',
    ];

    /** Point-feature colour by kind, for a point with no side. */
    public const POINT_COLORS = [
        'outbreak' => '#991b1b',
        'port' => '#0e7490',
        'market' => '#b45309',
        'city' => '#44403c',
    ];

    public const DEFAULT_COLOR = '#57534e';

    /**
     * The document with the schema-3 names: `features` for `terrain`, and each
     * step's `features` for its `terrain_state`.
     *
     * @param  array<string, mixed>  $doc
     * @return array<string, mixed>
     */
    public static function normalise(array $doc): array
    {
        $doc['features'] ??= $doc['terrain'] ?? [];
        unset($doc['terrain']);
        foreach ($doc['steps'] ?? [] as $i => $step) {
            if (is_array($step) && array_key_exists('terrain_state', $step)) {
                $step['features'] ??= $step['terrain_state'];
                unset($step['terrain_state']);
                $doc['steps'][$i] = $step;
            }
        }

        return $doc;
    }

    /**
     * Each step's [start, end] year; a step without a `date` inherits `year`.
     *
     * @param  array<string, mixed>  $doc
     * @return list<array{0: int, 1: int}|null>
     */
    public static function stepYears(array $doc): array
    {
        $year = is_int($doc['year'] ?? null) ? $doc['year'] : null;
        $out = [];
        foreach (array_values($doc['steps'] ?? []) as $step) {
            $date = is_array($step) ? ($step['date'] ?? null) : null;
            if (is_array($date) && is_int($date['year'] ?? null)) {
                $end = $date['end']['year'] ?? null;
                $out[] = [$date['year'], is_int($end) ? max($end, $date['year']) : $date['year']];
            } else {
                $out[] = $year === null ? null : [$year, $year];
            }
        }

        return $out;
    }

    /**
     * The story's [start, end] year: `period`, else the range of its step dates.
     *
     * @param  array<string, mixed>  $doc
     * @return array{0: int, 1: int}|null
     */
    public static function period(array $doc): ?array
    {
        $period = $doc['period'] ?? null;
        if (is_array($period) && is_int($period['start']['year'] ?? null) && is_int($period['end']['year'] ?? null)) {
            return [$period['start']['year'], $period['end']['year']];
        }
        $years = array_values(array_filter(self::stepYears($doc)));
        if ($years === []) {
            return is_int($doc['year'] ?? null) ? [$doc['year'], $doc['year']] : null;
        }

        return [min(array_column($years, 0)), max(array_column($years, 1))];
    }

    /**
     * Each step's features by id: the document's feature merged with its
     * carried-forward state, with `active` (default true) always set.
     *
     * @param  array<string, mixed>  $doc
     * @return list<array<string, array<string, mixed>>>
     */
    public static function resolveFeatures(array $doc): array
    {
        $doc = self::normalise($doc);
        $base = [];
        foreach ($doc['features'] as $feature) {
            if (is_array($feature) && is_string($feature['id'] ?? null)) {
                $base[$feature['id']] = $feature;
            }
        }

        $current = [];
        $out = [];
        foreach ($doc['steps'] ?? [] as $step) {
            foreach ((is_array($step) ? ($step['features'] ?? []) : []) as $id => $state) {
                if (! is_array($state)) {
                    continue;
                }
                $carried = $current[$id] ?? [];
                if (array_intersect_key($state, array_flip(V::GEOMETRY_KEYS)) !== []) {
                    $carried = array_diff_key($carried, array_flip(V::GEOMETRY_KEYS));
                }
                $current[$id] = array_filter([...$carried, ...$state], fn (mixed $v) => $v !== null);
            }
            $frame = [];
            foreach ($base as $id => $feature) {
                $state = $current[$id] ?? [];
                if (array_intersect_key($state, array_flip(V::GEOMETRY_KEYS)) !== []) {
                    $feature = array_diff_key($feature, array_flip(V::GEOMETRY_KEYS));
                }
                $frame[$id] = [...$feature, ...$state];
                $frame[$id]['active'] ??= true;
            }
            $out[] = $frame;
        }

        return $out;
    }

    /**
     * Each step's ambient layer: {index, start, title, features}, where
     * `features` is a FeatureCollection of the step's active route, region and
     * valued-point features, simplified. `$entityArea(entity_id, year)` gives
     * an entity's atlas area (GeoJSON) for `area_from_entity`, or null.
     *
     * @param  array<string, mixed>  $doc
     * @param  callable(string, int): (array<string, mixed>|null)  $entityArea
     * @return list<array{index: int, start: int, title: string, features: array{type: 'FeatureCollection', features: list<array<string, mixed>>}}>
     */
    public static function steps(array $doc, callable $entityArea): array
    {
        $sideColors = [];
        foreach ($doc['sides'] ?? [] as $side) {
            if (is_array($side) && is_string($side['id'] ?? null) && is_string($side['color'] ?? null)) {
                $sideColors[$side['id']] = $side['color'];
            }
        }
        $years = self::stepYears($doc);
        $steps = array_values($doc['steps'] ?? []);

        $out = [];
        foreach (self::resolveFeatures($doc) as $i => $frame) {
            $start = $years[$i][0] ?? (int) ($doc['year'] ?? 0);
            $features = [];
            foreach ($frame as $id => $feature) {
                $kind = $feature['kind'] ?? null;
                if (! in_array($kind, V::AMBIENT_FEATURE_KINDS, true) || $feature['active'] === false) {
                    continue;
                }
                $geometry = self::geometry($feature, $start, $entityArea);
                if ($geometry === null) {
                    continue;
                }
                $features[] = [
                    'type' => 'Feature',
                    'geometry' => $geometry,
                    'properties' => [
                        'id' => (string) $id,
                        'kind' => $kind,
                        'region_kind' => $feature['region_kind'] ?? null,
                        'route_kind' => $feature['route_kind'] ?? null,
                        'label' => $feature['label'] ?? null,
                        'color' => self::color($feature, $sideColors),
                        'value_n' => $feature['value_n'] ?? null,
                        'value_label' => $feature['value_label'] ?? null,
                        'intensity' => $feature['intensity'] ?? null,
                        'state' => $feature['state'] ?? null,
                    ],
                ];
            }
            $out[] = [
                'index' => $i,
                'start' => $start,
                'title' => (string) ($steps[$i]['title'] ?? ''),
                'features' => ['type' => 'FeatureCollection', 'features' => $features],
            ];
        }

        return $out;
    }

    /**
     * The colour of the side holding it (`held_by`), else of its own side,
     * else the palette by route kind, region kind or point kind.
     *
     * @param  array<string, mixed>  $feature
     * @param  array<string, string>  $sideColors
     */
    public static function color(array $feature, array $sideColors): string
    {
        foreach (['held_by', 'side'] as $key) {
            $side = $feature[$key] ?? null;
            if (is_string($side) && isset($sideColors[$side])) {
                return $sideColors[$side];
            }
        }

        return match ($feature['kind'] ?? null) {
            'route' => self::ROUTE_COLORS[$feature['route_kind'] ?? ''] ?? self::DEFAULT_COLOR,
            'region' => self::REGION_COLORS[$feature['region_kind'] ?? ''] ?? self::DEFAULT_COLOR,
            default => self::POINT_COLORS[$feature['kind'] ?? ''] ?? self::DEFAULT_COLOR,
        };
    }

    /**
     * The story's extent [west, south, east, north]: its features (and their
     * per-step geometry), placements, arrows and notes, plus `$extra`
     * geometry. Units placed with `frame: false` (and their arrows),
     * `continues` tails and `alt_sites` are left out.
     *
     * @param  array<string, mixed>  $doc
     * @param  list<mixed>  $extra
     * @return array{0: float, 1: float, 2: float, 3: float}|null
     */
    public static function bbox(array $doc, array $extra = []): ?array
    {
        $doc = self::normalise($doc);
        $parts = $extra;
        $geometry = fn (mixed $object) => is_array($object) ? [$object['at'] ?? null, $object['line'] ?? null, $object['area'] ?? null] : [];
        foreach ($doc['features'] as $feature) {
            $parts[] = $geometry($feature);
        }
        $offstage = [];
        foreach ($doc['steps'] ?? [] as $step) {
            if (! is_array($step)) {
                continue;
            }
            foreach (is_array($step['features'] ?? null) ? $step['features'] : [] as $state) {
                $parts[] = $geometry($state);
            }
            foreach ([$step, ...(is_array($step['beats'] ?? null) ? $step['beats'] : [])] as $phase) {
                if (! is_array($phase)) {
                    continue;
                }
                foreach (is_array($phase['positions'] ?? null) ? $phase['positions'] : [] as $unitId => $placement) {
                    if (! is_array($placement)) {
                        continue;
                    }
                    if (array_key_exists('frame', $placement)) {
                        $offstage[$unitId] = $placement['frame'] === false;
                    }
                    if (! ($offstage[$unitId] ?? false)) {
                        $parts[] = $placement['at'] ?? null;
                    }
                }
                foreach (is_array($phase['moves'] ?? null) ? $phase['moves'] : [] as $move) {
                    if (is_array($move) && ! ($offstage[$move['unit'] ?? ''] ?? false)) {
                        $parts[] = $move['path'] ?? null;
                    }
                }
                foreach (is_array($phase['notes'] ?? null) ? $phase['notes'] : [] as $note) {
                    $parts[] = is_array($note) ? ($note['at'] ?? null) : null;
                }
            }
        }

        return MapStoryGeometry::extent($parts);
    }

    /**
     * @param  array<string, mixed>  $feature
     * @param  callable(string, int): (array<string, mixed>|null)  $entityArea
     * @return array<string, mixed>|null
     */
    private static function geometry(array $feature, int $year, callable $entityArea): ?array
    {
        return match (V::FEATURE_KINDS[$feature['kind']] ?? null) {
            'at' => MapStoryDocument::point($feature['at'] ?? null) ? MapStoryGeometry::point($feature['at']) : null,
            'line' => is_array($feature['line'] ?? null) ? MapStoryGeometry::line($feature['line']) : null,
            'area' => array_key_exists('area_from_entity', $feature)
                ? (is_string($feature['area_from_entity']['entity_id'] ?? null) ? $entityArea($feature['area_from_entity']['entity_id'], $year) : null)
                : (is_array($feature['area'] ?? null) ? MapStoryGeometry::area($feature['area']) : null),
            default => null,
        };
    }
}
