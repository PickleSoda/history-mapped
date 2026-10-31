<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Actions\Tag\SyncTagsAction;
use App\DTOs\EntityData;
use App\Enums\EntityType;
use App\Enums\TagSource;
use App\Models\Entity;
use App\Models\EntityAlias;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;

/**
 * Apply a partial edit to an entity with the admin edit form's semantics, for
 * writers that change a few fields (the AI editor) instead of resubmitting the
 * whole form.
 *
 * `$changes` uses UpdateEntityRequest's keys and is already validated. Every
 * field it leaves out keeps its value: UpdateEntityAction rewrites the primary
 * temporal-range and location rows whole, so they are seeded from the entity.
 * Attributes merge like the form's (mergeAttributes); a key set to null is
 * cleared. Tags and alternative names change by adding and removing items, so
 * a writer never drops ones it didn't mention, and alias rows that stay keep
 * their primary flag.
 */
class ApplyEntityEditsAction
{
    /** Nullable entity columns EntityData can only set, never clear. */
    private const CLEARABLE_COLUMNS = [
        'summary', 'significance', 'impact_score', 'date_method', 'date_confidence', 'duration_type',
        'location_method', 'location_confidence', 'confidence', 'display_priority', 'icon_class',
    ];

    public function __construct(
        private UpdateEntityAction $update,
        private SyncTagsAction $syncTags,
    ) {}

    /**
     * @param  array<string, mixed>  $changes
     * @param  array{add?: list<string>, remove?: list<string>}  $tags
     * @param  array{add?: list<string>, remove?: list<string>}  $alternativeNames
     */
    public function __invoke(Entity $entity, array $changes, array $tags = [], array $alternativeNames = []): Entity
    {
        $entity->loadMissing(['primaryTemporalRange', 'primaryLocation', 'entityTags', 'aliases']);

        if (isset($changes['entity_type']) && ! isset($changes['entity_group'])) {
            $changes['entity_group'] = EntityType::from($changes['entity_type'])->group()->value;
        }

        $stored = is_array($entity->attributes) ? $entity->attributes : [];
        $merged = array_merge(self::currentValues($entity), Arr::except($changes, ['attributes']));
        $merged['attributes'] = self::mergeAttributes($stored, $changes);
        $tagList = ($tags['add'] ?? []) !== [] || ($tags['remove'] ?? []) !== []
            ? self::applyListEdit(self::manualTags($entity), $tags)
            : null;

        return DB::transaction(function () use ($entity, $changes, $merged, $stored, $tagList, $alternativeNames): Entity {
            $entity = ($this->update)($entity, EntityData::fromArray($merged));

            $cleared = array_keys(array_filter(
                Arr::only($changes, self::CLEARABLE_COLUMNS),
                fn ($value) => $value === null,
            ));
            // An attributes bag emptied by the edit: EntityData skips an empty one.
            if ($merged['attributes'] === [] && $stored !== []) {
                $cleared[] = 'attributes';
            }
            if ($cleared !== []) {
                $entity->forceFill(array_fill_keys($cleared, null))->save();
            }

            if ($tagList !== null) {
                ($this->syncTags)($entity, $tagList, TagSource::Manual);
            }

            $this->editAliases($entity, $alternativeNames);

            return $entity->fresh();
        });
    }

    /**
     * The entity's current values under UpdateEntityRequest's keys — what the
     * edit form would resubmit untouched. Tags, alternative names and the
     * attribute-stored fields (date_raw, …) are left out: they change by
     * explicit edits only.
     *
     * @return array<string, mixed>
     */
    public static function currentValues(Entity $entity): array
    {
        $temporal = $entity->primaryTemporalRange;
        $location = $entity->primaryLocation;

        return [
            'name' => $entity->name,
            'entity_type' => $entity->entity_type?->value,
            'entity_group' => $entity->entity_group?->value,
            'summary' => $entity->summary,
            'significance' => $entity->significance,
            'impact_score' => $entity->impact_score,
            'wikidata_id' => $entity->wikidata_id,
            'temporal_start' => $temporal?->start_date,
            'temporal_end' => $temporal?->end_date,
            // These live on the entity and on its primary rows; either may be
            // the only one set, and UpdateEntityAction writes both.
            'date_method' => ($entity->date_method ?? $temporal?->date_method)?->value,
            'date_confidence' => ($entity->date_confidence ?? $temporal?->date_confidence)?->value,
            'duration_type' => ($entity->duration_type ?? $temporal?->duration_type)?->value,
            'location_name' => $location?->location_name,
            'location_confidence' => ($entity->location_confidence ?? $location?->location_confidence)?->value,
            'location_method' => ($entity->location_method ?? $location?->location_method)?->value,
            'geojson' => $location?->geom,
            'territory_geojson' => $location?->territory_geom,
            'verification_status' => $entity->verification_status?->value,
            'confidence' => $entity->confidence?->value,
            'display_priority' => $entity->display_priority,
            'icon_class' => $entity->icon_class?->value,
        ];
    }

    /**
     * Merge a form-style edit's `attributes` into the stored ones instead of
     * replacing them:
     *  - keys the edit doesn't send are kept (pipeline flags, review markers, images…);
     *  - a key sent empty is removed;
     *  - lists and objects, which the form can't edit, are never overwritten;
     *  - an unchanged number or boolean keeps its type (the form sends text).
     * A top-level field EntityData stores in attributes (date_raw,
     * confidence_notes…) sent empty is removed too.
     *
     * @param  array<string, mixed>  $stored
     * @param  array<string, mixed>  $validated
     * @return array<string, mixed>
     */
    public static function mergeAttributes(array $stored, array $validated): array
    {
        $merged = $stored;

        foreach ($validated['attributes'] ?? [] as $key => $value) {
            $current = $stored[$key] ?? null;

            if (is_array($current)) {
                continue;
            }

            if ($value === null || $value === '') {
                unset($merged[$key]);
            } elseif (! (is_scalar($current) && ! is_string($current) && (string) $value === self::scalarText($current))) {
                $merged[$key] = $value;
            }
        }

        foreach (EntityData::MOVED_KEYS as $key) {
            if (array_key_exists($key, $validated) && $validated[$key] === null) {
                unset($merged[$key]);
            }
        }

        return $merged;
    }

    /**
     * The entity's manually set tags (derived ones are rebuilt by `tags:sync`).
     *
     * @return list<string>
     */
    public static function manualTags(Entity $entity): array
    {
        return $entity->loadMissing('entityTags')->entityTags->where('source', TagSource::Manual->value)->pluck('tag')->values()->all();
    }

    /**
     * `$items` with `$edit['remove']` taken out and `$edit['add']` appended,
     * compared case-insensitively.
     *
     * @param  list<string>  $items
     * @param  array{add?: list<string>, remove?: list<string>}  $edit
     * @return list<string>
     */
    public static function applyListEdit(array $items, array $edit): array
    {
        $remove = array_map(mb_strtolower(...), $edit['remove'] ?? []);
        $kept = array_values(array_filter($items, fn (string $item) => ! in_array(mb_strtolower($item), $remove, true)));
        $have = array_map(mb_strtolower(...), $kept);

        foreach ($edit['add'] ?? [] as $item) {
            $item = trim($item);
            if ($item !== '' && ! in_array(mb_strtolower($item), $have, true)) {
                $kept[] = $item;
                $have[] = mb_strtolower($item);
            }
        }

        return $kept;
    }

    /**
     * Add and remove alias rows in place (UpdateEntityAction would recreate
     * them all as non-primary).
     *
     * @param  array{add?: list<string>, remove?: list<string>}  $edit
     */
    private function editAliases(Entity $entity, array $edit): void
    {
        $remove = array_map(mb_strtolower(...), $edit['remove'] ?? []);
        if ($remove !== []) {
            EntityAlias::query()
                ->where('entity_id', $entity->entity_id)
                ->whereIn(DB::raw('LOWER(name)'), $remove)
                ->delete();
        }

        $have = EntityAlias::query()
            ->where('entity_id', $entity->entity_id)
            ->pluck('name')
            ->map(fn (string $name) => mb_strtolower($name))
            ->all();

        foreach (self::applyListEdit([], ['add' => $edit['add'] ?? []]) as $name) {
            if (! in_array(mb_strtolower($name), $have, true)) {
                EntityAlias::query()->create(['entity_id' => $entity->entity_id, 'name' => $name, 'is_primary' => false]);
            }
        }
    }

    /** A scalar as the form shows it (JavaScript's String()). */
    private static function scalarText(bool|int|float $value): string
    {
        return is_bool($value) ? ($value ? 'true' : 'false') : (string) $value;
    }
}
