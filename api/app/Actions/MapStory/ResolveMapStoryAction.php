<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Enums\EntityType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Services\EntityReferenceResolver;
use App\Support\MapStory\MapStoryAmbient;
use App\Support\MapStory\MapStoryFile;
use App\Support\MapStory\MapStoryGeometry;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use stdClass;

/**
 * Resolve an authored map-story document against the atlas: what
 * `map_stories` stores for it.
 *
 * The story entity resolves by Q-id, else by a given `entity_id`, else by the
 * exact name of a unique event entity; the chronicle by slug. Every reference
 * gets an id next to it, so the atlas can link to those pages:
 * `chronicle.chronicle_id`, `steps[].entry_id` (by sequence_order in that
 * chronicle), and an `entity_id` beside every Q-id (side polities,
 * commanders and contingents, units, step entities, feature entities,
 * `area_from_entity`). A
 * dated reference whose entity is clearly of another era resolves to null
 * (EntityReferenceResolver's namesake guard). A step entity with `show: true`
 * and an `entity_id` also gets `geometry`, its atlas geometry at the step's
 * year, and `ohm`, the OpenHistoricalMap boundaries it outlines then
 * (stepGeometries()).
 *
 * It also computes the story's period, extent and, for an ambient story, each
 * step's precomputed atlas layer (MapStoryAmbient). The document must already
 * pass MapStoryDocument::errors(); this adds the errors only the atlas can
 * tell (an unknown entity, chronicle or entry). It writes nothing.
 *
 * Every resolved value is recomputed, so an already-resolved document (a
 * stored one, `map-stories:relink`) resolves as its authored copy does: a
 * Q-id re-resolves (a merged-away entity's to the survivor holding the Q-id,
 * else null), an author-given `entity_id` is kept only while it exists, and
 * `geometry` and `ohm` are redrawn or dropped.
 */
class ResolveMapStoryAction
{
    /** SQL: the geometry period covers the year bound to `?` (NULL end = ongoing). */
    private const COVERS_YEAR = "int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year + 1 END, '[)') @> ?::integer";

    /** @var array<string, array<string, mixed>|null> entity area GeoJSON by "entity_id|year|tolerance" */
    private array $areas = [];

    /** @var array<string, array<string, mixed>|null> step-entity geometry by "entity_id|year" */
    private array $geometries = [];

    /** @var array<string, list<string>> step-entity OHM boundaries by "entity_id|year" */
    private array $boundaries = [];

    /** At most this many OHM boundaries per step entity. */
    private const MAX_OHM = 4;

    /**
     * `document` is the stored (resolved) copy; `columns` the row values derived from it.
     *
     * @return array{errors: list<string>, document: stdClass|null, columns: array<string, mixed>}
     */
    public function __invoke(stdClass $authored): array
    {
        $object = MapStoryFile::copy($authored);
        $array = MapStoryFile::toArray($authored);

        $entity = null;
        if (isset($array['entity'])) {
            $entity = $this->storyEntity($array['entity']);
            if ($entity === null) {
                $wikidata = $array['entity']['wikidata'] ?? 'no Q-id';

                return $this->failed(["entity '{$array['entity']['name']}' ({$wikidata}) is not in the atlas (or its name is ambiguous)"]);
            }
            $object->entity->entity_id = $entity->entity_id;
        }

        $chronicle = null;
        if (isset($array['chronicle'])) {
            $chronicle = Chronicle::query()->where('slug', $array['chronicle']['slug'])->first(['chronicle_id', 'slug']);
            if ($chronicle === null) {
                return $this->failed(["chronicle '{$array['chronicle']['slug']}' is not in the atlas"]);
            }
            $object->chronicle->chronicle_id = $chronicle->chronicle_id;
            $errors = $this->resolveEntries($object, $chronicle);
            if ($errors !== []) {
                return $this->failed($errors);
            }
        }

        $this->resolveRefs($this->refs($object, $array));
        $this->stepGeometries($object, $array);

        $resolved = MapStoryFile::toArray($object);
        $period = MapStoryAmbient::period($resolved);
        $ambient = ($array['ambient'] ?? false) === true;
        $ambientSteps = $ambient ? MapStoryAmbient::steps($resolved, $this->entityArea(...)) : null;
        $extra = array_map(fn (array $step) => array_column($step['features']['features'], 'geometry'), $ambientSteps ?? []);
        $bbox = MapStoryAmbient::bbox($resolved, $extra);

        return [
            'errors' => [],
            'document' => $object,
            'columns' => [
                'entity_id' => $entity?->entity_id,
                'chronicle_id' => $chronicle?->chronicle_id,
                'kind' => $array['kind'],
                'title' => $array['title'],
                'year' => $array['year'],
                'period_start' => $period[0] ?? null,
                'period_end' => $period[1] ?? null,
                'ambient' => $ambient,
                'step_count' => count($array['steps'] ?? []),
                'ambient_steps' => $ambientSteps,
                'bbox' => $bbox === null ? null : DB::raw(vsprintf('ST_MakeEnvelope(%F, %F, %F, %F, 4326)', $bbox)),
            ],
        ];
    }

    /**
     * @param  list<string>  $errors
     * @return array{errors: list<string>, document: null, columns: array<string, mixed>}
     */
    private function failed(array $errors): array
    {
        return ['errors' => $errors, 'document' => null, 'columns' => []];
    }

    /** @param  array<string, mixed>  $ref  {name, wikidata?, entity_id?} */
    private function storyEntity(array $ref): ?Entity
    {
        if (is_string($ref['wikidata'] ?? null)) {
            $byQid = $this->byQid([$ref['wikidata']])->get($ref['wikidata']);
            if ($byQid !== null) {
                return Entity::query()->find($byQid);
            }
        }
        if (! is_string($ref['wikidata'] ?? null) && EntityReferenceResolver::isUuid($ref['entity_id'] ?? null)) {
            $given = Entity::query()->find(strtolower($ref['entity_id']));
            if ($given !== null) {
                return $given;
            }
        }

        $byName = Entity::query()
            ->where('name', $ref['name'])
            ->whereIn('entity_type', self::eventTypes())
            ->limit(2)
            ->get(['entity_id']);

        return $byName->count() === 1 ? $byName->first() : null;
    }

    /** @return list<string> */
    private static function eventTypes(): array
    {
        return array_values(array_map(
            fn (EntityType $t) => $t->value,
            array_filter(EntityType::cases(), fn (EntityType $t) => str_starts_with($t->value, 'event_')),
        ));
    }

    /**
     * Write `entry_id` beside each step's `entry` (the entry's sequence_order
     * in the story's chronicle); an entry the chronicle lacks is an error.
     *
     * @return list<string>
     */
    private function resolveEntries(stdClass $doc, Chronicle $chronicle): array
    {
        $entries = DB::table('chronicle_entries')
            ->where('chronicle_id', $chronicle->chronicle_id)
            ->pluck('entry_id', 'sequence_order');

        $errors = [];
        foreach ($doc->steps ?? [] as $step) {
            if (! isset($step->entry)) {
                continue;
            }
            $entryId = $entries->get($step->entry);
            if ($entryId === null) {
                $range = $entries->isEmpty() ? 'it has none' : 'its entries run '.$entries->keys()->min().'–'.$entries->keys()->max();
                $errors[] = "step '{$step->id}'.entry: chronicle '{$chronicle->slug}' has no entry {$step->entry} ({$range})";

                continue;
            }
            $step->entry_id = (string) $entryId;
        }

        return $errors;
    }

    /**
     * Every linked reference in the document with the year span that dates it
     * (null: no temporal signal).
     *
     * @param  array<string, mixed>  $array  the same document, decoded as arrays
     * @return list<array{0: stdClass, 1: array{0: int, 1: int}|null}>
     */
    private function refs(stdClass $doc, array $array): array
    {
        $refs = [];
        foreach ($doc->sides ?? [] as $side) {
            if (isset($side->polity) && $side->polity instanceof stdClass) {
                $refs[] = [$side->polity, null];
            }
            foreach ($side->commanders ?? [] as $commander) {
                $refs[] = [$commander, null];
            }
            foreach ($side->contingents ?? [] as $contingent) {
                if ($contingent instanceof stdClass && is_string($contingent->wikidata ?? null)) {
                    $refs[] = [$contingent, null];
                }
            }
        }
        foreach ($doc->units ?? [] as $unit) {
            $refs[] = [$unit, null];
        }

        $period = MapStoryAmbient::period($array);
        foreach ($doc->features ?? $doc->terrain ?? [] as $feature) {
            if (isset($feature->entity) && $feature->entity instanceof stdClass) {
                $refs[] = [$feature->entity, $period];
            }
        }

        $years = MapStoryAmbient::stepYears($array);
        foreach ($doc->steps ?? [] as $i => $step) {
            foreach ($step->entities ?? [] as $entity) {
                $refs[] = [$entity, $years[$i] ?? null];
            }
            foreach ((array) ($step->features ?? $step->terrain_state ?? []) as $state) {
                if ($state instanceof stdClass && isset($state->area_from_entity) && $state->area_from_entity instanceof stdClass) {
                    $refs[] = [$state->area_from_entity, $years[$i] ?? null];
                }
            }
        }

        return $refs;
    }

    /**
     * Write `entity_id` beside each reference: by its Q-id (null when the atlas
     * lacks it, or when a dated reference's entity is of another era), else
     * the `entity_id` it was given when that entity exists, else null.
     *
     * @param  list<array{0: stdClass, 1: array{0: int, 1: int}|null}>  $refs
     */
    private function resolveRefs(array $refs): void
    {
        $qids = collect($refs)->map(fn (array $ref) => $ref[0]->wikidata ?? null)->filter(fn ($q) => is_string($q))->unique()->values()->all();
        $byQid = $this->byQid($qids);

        $given = collect($refs)
            ->filter(fn (array $ref) => ! is_string($ref[0]->wikidata ?? null) && EntityReferenceResolver::isUuid($ref[0]->entity_id ?? null))
            ->map(fn (array $ref) => strtolower($ref[0]->entity_id))
            ->unique()->values()->all();
        $existing = $given === [] ? [] : Entity::query()->whereIn('entity_id', $given)->pluck('entity_id')->map(fn ($id) => (string) $id)->flip()->all();

        $dated = collect($refs)->filter(fn (array $ref) => $ref[1] !== null && is_string($ref[0]->wikidata ?? null))
            ->map(fn (array $ref) => $byQid->get($ref[0]->wikidata))->filter()->unique()->values()->all();
        $rows = $this->entityRows($dated);

        foreach ($refs as [$ref, $span]) {
            if (is_string($ref->wikidata ?? null)) {
                $id = $byQid->get($ref->wikidata);
                $row = $id === null ? null : ($rows[$id] ?? null);
                if ($span !== null && $row !== null
                    && EntityReferenceResolver::temporallyIncompatible($row['entity_type'], $span, EntityReferenceResolver::rowSpan($row))) {
                    $id = null;
                }
                $ref->entity_id = $id;
            } else {
                $id = is_string($ref->entity_id ?? null) ? strtolower($ref->entity_id) : null;
                $ref->entity_id = $id !== null && isset($existing[$id]) ? $id : null;
            }
        }
    }

    /**
     * Each entity's type and primary temporal range, for the namesake guard.
     *
     * @param  list<string>  $ids
     * @return array<string, array{entity_type: string|null, start_year: int|null, end_year: int|null}>
     */
    private function entityRows(array $ids): array
    {
        if ($ids === []) {
            return [];
        }

        return DB::table('entities as e')
            ->leftJoin('entity_temporal_ranges as t', function ($join): void {
                $join->on('t.entity_id', '=', 'e.entity_id')->where('t.is_primary', true);
            })
            ->whereIn('e.entity_id', $ids)
            ->get(['e.entity_id', 'e.entity_type', 't.start_year', 't.end_year'])
            ->mapWithKeys(fn (object $r) => [(string) $r->entity_id => [
                'entity_type' => $r->entity_type,
                'start_year' => $r->start_year === null ? null : (int) $r->start_year,
                'end_year' => $r->end_year === null ? null : (int) $r->end_year,
            ]])
            ->all();
    }

    /**
     * Q-id → entity id. When several rows share a Q-id (an unmerged duplicate),
     * the most prominent wins.
     *
     * @param  list<string>  $qids
     * @return Collection<string, string>
     */
    private function byQid(array $qids): Collection
    {
        if ($qids === []) {
            return collect();
        }

        return Entity::query()
            ->whereIn('wikidata_id', $qids)
            ->orderByRaw('impact_score DESC NULLS LAST')
            ->orderBy('entity_id')
            ->get(['entity_id', 'wikidata_id'])
            ->groupBy('wikidata_id')
            ->map(fn (Collection $rows) => (string) $rows->first()->entity_id);
    }

    /**
     * Write `geometry` beside each step entity with `show: true` and an
     * `entity_id`: its atlas geometry at the step's year (the step's date,
     * else the story's `year`; see entityGeometry()), null when the atlas has
     * none; and `ohm` when it has OpenHistoricalMap boundaries then
     * (ohmBoundaries()). Any other step entity carries neither.
     *
     * @param  array<string, mixed>  $array  the same document, decoded as arrays
     */
    private function stepGeometries(stdClass $doc, array $array): void
    {
        $years = MapStoryAmbient::stepYears($array);
        foreach ($doc->steps ?? [] as $i => $step) {
            foreach ($step->entities ?? [] as $entity) {
                if (! $entity instanceof stdClass) {
                    continue;
                }
                unset($entity->geometry, $entity->ohm);
                $year = $years[$i][0] ?? null;
                if (($entity->show ?? false) === true && is_string($entity->entity_id ?? null) && $year !== null) {
                    $entity->geometry = $this->entityGeometry($entity->entity_id, $year);
                    $ohm = $this->ohmBoundaries($entity->entity_id, $year);
                    if ($ohm !== []) {
                        $entity->ohm = $ohm;
                    }
                }
            }
        }
    }

    /**
     * What the story draws for a shown step entity in `$year`, as simplified
     * GeoJSON: its area (entityArea(), simplified harder while over
     * MapStoryGeometry::ENTITY_MAX_BYTES); else the point (or line) of a
     * geometry period covering the year; else its undated location (`geom`,
     * as GET /entities/{id} serves it); else null.
     *
     * @return array<string, mixed>|null
     */
    private function entityGeometry(string $entityId, int $year): ?array
    {
        $key = "{$entityId}|{$year}";
        if (array_key_exists($key, $this->geometries)) {
            return $this->geometries[$key];
        }

        $area = null;
        foreach (MapStoryGeometry::ENTITY_TOLERANCES as $tolerance) {
            $area = $this->entityArea($entityId, $year, $tolerance);
            if ($area === null || strlen((string) json_encode($area)) <= MapStoryGeometry::ENTITY_MAX_BYTES) {
                break;
            }
        }

        return $this->geometries[$key] = $area ?? $this->datedPoint($entityId, $year) ?? $this->location($entityId);
    }

    /**
     * The OpenHistoricalMap boundaries an entity outlines in `$year`, as
     * "relation/123" or "way/456": its active OHM geo-refs to a relation or
     * way whose years cover `$year` (an open end covers), not rejected, and
     * not a `type=chronology` relation (OHM draws none: its dated member
     * boundaries are linked on their own). The primary ones when any covers,
     * else the rest by match score; at most MAX_OHM. The web outlines them on
     * OHM's polygon tiles, at the step's date.
     *
     * @return list<string>
     */
    private function ohmBoundaries(string $entityId, int $year): array
    {
        $key = "{$entityId}|{$year}";
        if (! array_key_exists($key, $this->boundaries)) {
            $rows = DB::table('entity_geo_refs')
                ->where('entity_id', $entityId)
                ->where('provider', 'ohm')
                ->where('is_active', true)
                ->whereIn('external_type', ['relation', 'way'])
                ->where('match_role', '!=', 'rejected')
                ->where(fn ($q) => $q->whereNull('temporal_start_year')->orWhere('temporal_start_year', '<=', $year))
                ->where(fn ($q) => $q->whereNull('temporal_end_year')->orWhere('temporal_end_year', '>=', $year))
                ->whereRaw("COALESCE(external_tags->>'type', '') <> 'chronology'")
                ->orderByRaw("(match_role = 'primary') DESC, match_score DESC NULLS LAST, external_type, external_id")
                ->get(['external_type', 'external_id', 'match_role']);
            $primary = $rows->filter(fn (object $r) => $r->match_role === 'primary');

            $this->boundaries[$key] = ($primary->isNotEmpty() ? $primary : $rows)
                ->take(self::MAX_OHM)
                ->map(fn (object $r) => "{$r->external_type}/{$r->external_id}")
                ->values()
                ->all();
        }

        return $this->boundaries[$key];
    }

    /**
     * An entity's atlas area in `$year` as simplified GeoJSON: its territory
     * (else polygonal geometry) period covering that year, newest first; null
     * when it has none.
     *
     * @return array<string, mixed>|null
     */
    private function entityArea(string $entityId, int $year, float $tolerance = MapStoryGeometry::TOLERANCE): ?array
    {
        $key = "{$entityId}|{$year}|{$tolerance}";
        if (! array_key_exists($key, $this->areas)) {
            $this->areas[$key] = self::geoJson(DB::table('geometry_periods')
                ->where('entity_id', $entityId)
                ->whereRaw(self::COVERS_YEAR, [$year])
                ->whereRaw('ST_Dimension(COALESCE(territory_geom, geom)) = 2')
                ->orderByRaw('(territory_geom IS NULL), start_year DESC, end_year ASC NULLS FIRST')
                ->limit(1)
                ->value(DB::raw(self::simplified('COALESCE(territory_geom, geom)', $tolerance))));
        }

        return $this->areas[$key];
    }

    /**
     * The point (or line) of an entity's geometry period covering `$year`,
     * newest first; null when none does.
     *
     * @return array<string, mixed>|null
     */
    private function datedPoint(string $entityId, int $year): ?array
    {
        return self::geoJson(DB::table('geometry_periods')
            ->where('entity_id', $entityId)
            ->whereRaw(self::COVERS_YEAR, [$year])
            ->whereRaw('ST_Dimension(COALESCE(territory_geom, geom)) < 2')
            ->orderByRaw('start_year DESC, end_year ASC NULLS FIRST')
            ->limit(1)
            ->value(DB::raw(self::simplified('COALESCE(territory_geom, geom)', MapStoryGeometry::TOLERANCE))));
    }

    /**
     * An entity's undated location: the `geom` of its primary location, as
     * Entity::primaryLocation picks it; null when it has none.
     *
     * @return array<string, mixed>|null
     */
    private function location(string $entityId): ?array
    {
        return self::geoJson(DB::table('entity_locations')
            ->where('entity_id', $entityId)
            ->where('is_primary', true)
            ->orderByDesc('updated_at')
            ->limit(1)
            ->value(DB::raw(self::simplified('geom', MapStoryGeometry::TOLERANCE))));
    }

    /** SQL: `$column` simplified at `$tolerance` degrees, as GeoJSON with MapStoryGeometry::DECIMALS. */
    private static function simplified(string $column, float $tolerance): string
    {
        return sprintf('ST_AsGeoJSON(ST_SimplifyPreserveTopology(%s, %F), %d)', $column, $tolerance, MapStoryGeometry::DECIMALS);
    }

    /** @return array<string, mixed>|null */
    private static function geoJson(mixed $json): ?array
    {
        return is_string($json) ? json_decode($json, true) : null;
    }
}
