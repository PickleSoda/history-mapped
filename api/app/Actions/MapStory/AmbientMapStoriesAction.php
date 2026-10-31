<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use Illuminate\Support\Facades\DB;

/**
 * GET /map-stories/ambient: the ambient stories whose period covers `$year`
 * and whose extent meets the bounding box, each with the precomputed layer
 * (`ambient_steps`) of its last step that starts in or before `$year`:
 *
 *   {"data": [{slug, kind, title, step_index, step_title, features: FeatureCollection}]}
 *
 * The FeatureCollections are copied from the stored JSON as they are.
 */
class AmbientMapStoriesAction
{
    /**
     * A strong ETag for one request: the stories' data version (last update,
     * row count) and the filters, as /entities/map does.
     *
     * @param  array{0: float, 1: float, 2: float, 3: float}|null  $bbox
     */
    public function etag(int $year, ?array $bbox): string
    {
        $stories = DB::table('map_stories')->selectRaw('MAX(updated_at) AS latest, COUNT(*) AS total')->first();

        return sha1(($stories->latest ?? '').':'.($stories->total ?? 0).'|'.json_encode(['bbox' => $bbox, 'year' => $year]));
    }

    /**
     * The response body.
     *
     * @param  array{0: float, 1: float, 2: float, 3: float}|null  $bbox
     */
    public function __invoke(int $year, ?array $bbox): string
    {
        $query = DB::table('map_stories as ms')
            ->crossJoin(DB::raw(<<<'SQL'
                LATERAL (
                    SELECT step FROM jsonb_array_elements(ms.ambient_steps) AS step
                    WHERE (step->>'start')::integer <= ?
                    ORDER BY (step->>'index')::integer DESC
                    LIMIT 1
                ) AS s
                SQL))
            ->addBinding($year, 'join')
            ->where('ms.ambient', true)
            ->where('ms.period_start', '<=', $year)
            ->where('ms.period_end', '>=', $year)
            ->whereRaw("jsonb_array_length(s.step->'features'->'features') > 0")
            ->select([
                'ms.slug', 'ms.kind', 'ms.title',
                DB::raw("(s.step->>'index')::integer AS step_index"),
                DB::raw("s.step->>'title' AS step_title"),
                DB::raw("(s.step->'features')::text AS features"),
            ])
            ->orderBy('ms.period_start')
            ->orderBy('ms.slug');

        $envelopes = $bbox === null ? [] : self::envelopes($bbox);
        if ($envelopes !== []) {
            $query->where(function ($q) use ($envelopes): void {
                foreach ($envelopes as $envelope) {
                    $q->orWhereRaw('ms.bbox && ST_MakeEnvelope(?, ?, ?, ?, 4326)', $envelope);
                }
            });
        }

        $items = [];
        foreach ($query->get() as $row) {
            $head = json_encode([
                'slug' => $row->slug,
                'kind' => $row->kind,
                'title' => $row->title,
                'step_index' => (int) $row->step_index,
                'step_title' => $row->step_title,
            ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
            $items[] = substr((string) $head, 0, -1).',"features":'.$row->features.'}';
        }

        return '{"data":['.implode(',', $items).']}';
    }

    /**
     * The box as one or two envelopes: longitudes wrapped into -180..180, two
     * when it crosses the antimeridian, none when it spans the whole world.
     *
     * @param  array{0: float, 1: float, 2: float, 3: float}  $bbox
     * @return list<array{0: float, 1: float, 2: float, 3: float}>
     */
    public static function envelopes(array $bbox): array
    {
        [$w, $s, $e, $n] = $bbox;
        if ($e - $w >= 360) {
            return [];
        }
        $w = self::wrap($w);
        $e = self::wrap($e);

        return $w <= $e ? [[$w, $s, $e, $n]] : [[$w, $s, 180.0, $n], [-180.0, $s, $e, $n]];
    }

    private static function wrap(float $lng): float
    {
        if ($lng >= -180.0 && $lng <= 180.0) {
            return $lng;
        }
        $wrapped = fmod($lng + 180.0, 360.0);

        return ($wrapped < 0 ? $wrapped + 360.0 : $wrapped) - 180.0;
    }
}
