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
 * commanders, units, step entities, feature entities, `area_from_entity`). A
 * dated reference whose entity is clearly of another era resolves to null
 * (EntityReferenceResolver's namesake guard).
 *
 * It also computes the story's period, extent and, for an ambient story, each
 * step's precomputed atlas layer (MapStoryAmbient). The document must already
 * pass MapStoryDocument::errors(); this adds the errors only the atlas can
 * tell (an unknown entity, chronicle or entry). It writes nothing.
 */
class ResolveMapStoryAction
{
    /** @var array<string, array<string, mixed>|null> entity area GeoJSON by "entity_id|year" */
    private array $areas = [];

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
     * An entity's atlas area in `$year` as simplified GeoJSON: its territory
     * (else polygonal geometry) period covering that year, newest first; null
     * when it has none.
     *
     * @return array<string, mixed>|null
     */
    private function entityArea(string $entityId, int $year): ?array
    {
        $key = "{$entityId}|{$year}";
        if (! array_key_exists($key, $this->areas)) {
            $json = DB::table('geometry_periods')
                ->where('entity_id', $entityId)
                ->whereRaw("int4range(start_year, CASE WHEN end_year IS NULL THEN NULL ELSE end_year + 1 END, '[)') @> ?::integer", [$year])
                ->whereRaw('ST_Dimension(COALESCE(territory_geom, geom)) = 2')
                ->orderByRaw('(territory_geom IS NULL), start_year DESC, end_year ASC NULLS FIRST')
                ->limit(1)
                ->value(DB::raw('ST_AsGeoJSON(ST_SimplifyPreserveTopology(COALESCE(territory_geom, geom), '.MapStoryGeometry::TOLERANCE.'), '.MapStoryGeometry::DECIMALS.')'));
            $this->areas[$key] = is_string($json) ? json_decode($json, true) : null;
        }

        return $this->areas[$key];
    }
}
