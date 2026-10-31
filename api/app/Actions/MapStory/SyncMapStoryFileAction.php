<?php

declare(strict_types=1);

namespace App\Actions\MapStory;

use App\Enums\EntityType;
use App\Models\Entity;
use App\Models\MapStory;
use App\Support\MapStory\MapStoryDocument;
use Illuminate\Support\Collection;
use stdClass;

/**
 * Load one resources/map-stories/<slug>.json file into `map_stories`.
 *
 * The file is checked (MapStoryDocument), its story entity resolved (Q-id,
 * else the exact name of a unique event entity), and every Q-id it carries
 * (story entity, side polities, commanders, units) gets an `entity_id` next to
 * it so the atlas can link to those pages. Rows are upserted by slug; a file
 * whose hash matches the stored row is skipped unless forced.
 */
class SyncMapStoryFileAction
{
    /**
     * @return array{status: 'created'|'updated'|'unchanged'|'failed', slug: string, errors: list<string>}
     */
    public function __invoke(string $path, bool $force = false): array
    {
        $slug = basename($path, '.json');
        $raw = (string) file_get_contents($path);
        $hash = sha1($raw);

        $existing = MapStory::query()->where('slug', $slug)->first(['story_id', 'slug', 'content_hash']);
        if (! $force && $existing !== null && $existing->content_hash === $hash) {
            return ['status' => 'unchanged', 'slug' => $slug, 'errors' => []];
        }

        $array = json_decode($raw, true);
        $object = json_decode($raw);
        if (json_last_error() !== JSON_ERROR_NONE || ! $object instanceof stdClass) {
            return $this->failed($slug, ['not a JSON object: '.json_last_error_msg()]);
        }

        $errors = MapStoryDocument::errors($array);
        if (($array['slug'] ?? null) !== $slug) {
            $errors[] = "slug '".($array['slug'] ?? '')."' must match the file name '{$slug}'";
        }
        if ($errors !== []) {
            return $this->failed($slug, $errors);
        }

        $entity = $this->storyEntity($array['entity']);
        if ($entity === null) {
            $wikidata = $array['entity']['wikidata'] ?? 'no Q-id';

            return $this->failed($slug, ["entity '{$array['entity']['name']}' ({$wikidata}) is not in the atlas (or its name is ambiguous)"]);
        }

        $this->resolveIds($object, $entity);

        $story = MapStory::query()->updateOrCreate(['slug' => $slug], [
            'entity_id' => $entity->entity_id,
            'kind' => $array['kind'],
            'title' => $array['title'],
            'year' => $array['year'],
            'step_count' => count($array['steps'] ?? []),
            'document' => $object,
            'source_path' => 'resources/map-stories/'.basename($path),
            'content_hash' => $hash,
        ]);

        return ['status' => $story->wasRecentlyCreated ? 'created' : 'updated', 'slug' => $slug, 'errors' => []];
    }

    /**
     * @param  list<string>  $errors
     * @return array{status: 'failed', slug: string, errors: list<string>}
     */
    private function failed(string $slug, array $errors): array
    {
        return ['status' => 'failed', 'slug' => $slug, 'errors' => $errors];
    }

    /** @param  array<string, mixed>  $ref  {name, wikidata?} */
    private function storyEntity(array $ref): ?Entity
    {
        if (is_string($ref['wikidata'] ?? null)) {
            $byQid = $this->byQid([$ref['wikidata']])->get($ref['wikidata']);
            if ($byQid !== null) {
                return Entity::query()->find($byQid);
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
     * Write `entity_id` beside every Q-id in the document (null when the atlas
     * lacks it); the story entity is the resolved one even without a Q-id.
     */
    private function resolveIds(stdClass $doc, Entity $entity): void
    {
        $refs = [];
        foreach ($doc->sides ?? [] as $side) {
            if (isset($side->polity) && $side->polity instanceof stdClass) {
                $refs[] = $side->polity;
            }
            foreach ($side->commanders ?? [] as $commander) {
                $refs[] = $commander;
            }
        }
        foreach ($doc->units ?? [] as $unit) {
            $refs[] = $unit;
        }

        $qids = collect($refs)->pluck('wikidata')->filter(fn ($q) => is_string($q))->unique()->values()->all();
        $ids = $this->byQid($qids);

        foreach ($refs as $ref) {
            $ref->entity_id = is_string($ref->wikidata ?? null) ? $ids->get($ref->wikidata) : null;
        }
        $doc->entity->entity_id = $entity->entity_id;
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
}
