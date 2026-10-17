<?php

declare(strict_types=1);

namespace App\Actions\Saved;

use App\Enums\SaveableType;
use App\Models\Chronicle;
use App\Models\Entity;
use App\Models\EntityRelationship;
use App\Models\Star;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

/**
 * Load the summary card of every starred target in one query per type.
 *
 * Returns `"{type}:{id}" => summary`; a star whose target has been deleted has
 * no key (the resource renders `item: null`).
 */
class ResolveSavedItemsAction
{
    private const SUMMARY_LENGTH = 240;

    /**
     * @param  iterable<Star>  $stars
     * @return array<string, array<string, mixed>>
     */
    public function __invoke(iterable $stars): array
    {
        $idsByType = collect($stars)
            ->groupBy(fn (Star $s) => $s->starrable_type->value)
            ->map(fn (Collection $group) => $group->pluck('starrable_id')->unique()->values()->all());

        $items = [];

        foreach ($idsByType as $type => $ids) {
            $summaries = match (SaveableType::from($type)) {
                SaveableType::Entity => $this->entities($ids),
                SaveableType::Chronicle => $this->chronicles($ids),
                SaveableType::Relationship => $this->relationships($ids),
            };
            foreach ($summaries as $id => $summary) {
                $items["{$type}:{$id}"] = $summary;
            }
        }

        return $items;
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array<string, mixed>>
     */
    private function entities(array $ids): array
    {
        return Entity::query()
            ->whereKey($ids)
            ->get(['entity_id', 'name', 'entity_type', 'entity_group', 'summary'])
            ->mapWithKeys(fn (Entity $e) => [$e->entity_id => [
                'type' => SaveableType::Entity->value,
                ...self::entityRef($e),
                'summary' => $e->summary === null ? null : Str::limit($e->summary, self::SUMMARY_LENGTH),
            ]])
            ->all();
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array<string, mixed>>
     */
    private function chronicles(array $ids): array
    {
        return Chronicle::query()
            ->whereKey($ids)
            ->withCount('entries')
            ->get(['chronicle_id', 'slug', 'title', 'start_year', 'end_year'])
            ->mapWithKeys(fn (Chronicle $c) => [$c->chronicle_id => [
                'type' => SaveableType::Chronicle->value,
                'id' => $c->chronicle_id,
                'slug' => $c->slug,
                'title' => $c->title,
                'start_year' => $c->start_year,
                'end_year' => $c->end_year,
                'entry_count' => $c->entries_count,
            ]])
            ->all();
    }

    /**
     * @param  list<string>  $ids
     * @return array<string, array<string, mixed>>
     */
    private function relationships(array $ids): array
    {
        return EntityRelationship::query()
            ->whereKey($ids)
            ->with([
                'sourceEntity:entity_id,name,entity_type,entity_group',
                'targetEntity:entity_id,name,entity_type,entity_group',
            ])
            ->get()
            ->mapWithKeys(fn (EntityRelationship $r) => [$r->relationship_id => [
                'type' => SaveableType::Relationship->value,
                'id' => $r->relationship_id,
                'relationship_type' => $r->relationship_type?->value,
                'description' => $r->description,
                'source' => $r->sourceEntity ? self::entityRef($r->sourceEntity) : null,
                'target' => $r->targetEntity ? self::entityRef($r->targetEntity) : null,
            ]])
            ->all();
    }

    /** @return array<string, mixed> */
    private static function entityRef(Entity $e): array
    {
        return [
            'id' => $e->entity_id,
            'name' => $e->name,
            'entity_type' => $e->entity_type?->value,
            'entity_group' => $e->entity_group?->value,
        ];
    }
}
