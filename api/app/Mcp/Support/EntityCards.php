<?php

declare(strict_types=1);

namespace App\Mcp\Support;

use App\Enums\ConfidenceLevel;
use App\Models\Entity;
use App\Models\EntityTemporalRange;
use Illuminate\Support\Collection;

/**
 * The EntitySummary every list tool returns, built from entities loaded the
 * way the public API loads them (`withGeoJson()` aliases, or the
 * `primaryLocation` relation) and nothing the public API keeps back.
 */
final class EntityCards
{
    public const SUMMARY_CHARS = 300;

    /**
     * @param  iterable<Entity>  $entities
     * @return list<array<string, mixed>>
     */
    public static function summaries(iterable $entities): array
    {
        $entities = Collection::make($entities)->values();
        $years = self::years($entities->pluck('entity_id')->all());

        return $entities->map(fn (Entity $e): array => self::summary($e, $years[$e->entity_id] ?? null))->all();
    }

    /**
     * Primary start/end year per entity id, one query for the lot.
     *
     * @param  list<string>  $ids
     * @return array<string, array{0: int|null, 1: int|null}>
     */
    public static function years(array $ids): array
    {
        if ($ids === []) {
            return [];
        }

        return EntityTemporalRange::query()
            ->whereIn('entity_id', $ids)
            ->where('is_primary', true)
            ->get(['entity_id', 'start_year', 'end_year'])
            ->mapWithKeys(fn (EntityTemporalRange $r): array => [
                $r->entity_id => [
                    $r->start_year !== null ? (int) $r->start_year : null,
                    $r->end_year !== null ? (int) $r->end_year : null,
                ],
            ])
            ->all();
    }

    /**
     * @param  array{0: int|null, 1: int|null}|null  $range
     * @return array<string, mixed>
     */
    public static function summary(Entity $e, ?array $range): array
    {
        [$start, $end] = $range ?? [null, null];
        [$lng, $lat] = self::point($e);
        $approximate = in_array($e->date_confidence, [ConfidenceLevel::Low, ConfidenceLevel::Unresolved], true);

        return [
            'id' => $e->entity_id,
            'name' => $e->name,
            'type' => $e->entity_type?->value,
            'type_label' => Text::typeLabel($e->entity_type),
            'group' => $e->entity_group?->value,
            'start_year' => $start,
            'end_year' => $end,
            'date_label' => Text::dateLabel($start, $end, $approximate),
            'summary' => Text::limit($e->summary, self::SUMMARY_CHARS),
            'lng' => $lng,
            'lat' => $lat,
            'place' => self::place($e),
            'image_url' => self::image($e)['thumb_url'] ?? null,
            'impact_score' => $e->impact_score,
            'verification_status' => $e->verification_status?->value,
            'atlas_url' => AtlasUrl::entity($e->entity_id),
        ];
    }

    /**
     * The first linked Commons image, as the public EntityResource exposes it
     * (`attributes.media_refs`; nothing is copied, each item links to Commons).
     * `url` on a stored item is already a thumbnail.
     *
     * @return array{url: string, thumb_url: string, credit: string|null, license: string|null, source_url: string|null}|null
     */
    public static function image(Entity $e): ?array
    {
        $refs = ($e->getAttribute('attributes') ?? [])['media_refs'] ?? null;
        if (! is_array($refs)) {
            return null;
        }
        foreach ($refs as $ref) {
            if (is_array($ref) && ($ref['type'] ?? 'image') === 'image' && is_string($ref['url'] ?? null) && $ref['url'] !== '') {
                return [
                    'url' => (string) ($ref['original_url'] ?? $ref['url']),
                    'thumb_url' => $ref['url'],
                    'credit' => isset($ref['author']) ? Text::limit((string) $ref['author'], 200) : null,
                    'license' => isset($ref['license']) ? (string) $ref['license'] : null,
                    'source_url' => isset($ref['page_url']) ? (string) $ref['page_url'] : null,
                ];
            }
        }

        return null;
    }

    /** @return array{0: float|null, 1: float|null} [lng, lat] of a Point, else nulls */
    public static function point(Entity $e): array
    {
        $geom = $e->geom_geojson ?? ($e->relationLoaded('primaryLocation') ? $e->primaryLocation?->geom : null);
        if (is_string($geom)) {
            $geom = json_decode($geom, true);
        }
        if (! is_array($geom) || ($geom['type'] ?? null) !== 'Point' || count($geom['coordinates'] ?? []) < 2) {
            return [null, null];
        }

        return [round((float) $geom['coordinates'][0], 5), round((float) $geom['coordinates'][1], 5)];
    }

    private static function place(Entity $e): ?string
    {
        $name = array_key_exists('location_name', $e->getAttributes())
            ? $e->getAttribute('location_name')
            : ($e->relationLoaded('primaryLocation') ? $e->primaryLocation?->location_name : null);

        return $name !== null && $name !== '' ? (string) $name : null;
    }
}
