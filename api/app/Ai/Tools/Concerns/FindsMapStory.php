<?php

declare(strict_types=1);

namespace App\Ai\Tools\Concerns;

use App\Ai\Tools\ToolArgumentException;
use App\Models\Entity;
use App\Models\MapStory;
use App\Services\EntityReferenceResolver;

/** Find the map story a tool call means: by slug, else the one of an entity (id or exact name) or chronicle. */
trait FindsMapStory
{
    /** @throws ToolArgumentException */
    protected function findStory(array $args): MapStory
    {
        $slug = trim((string) ($args['slug'] ?? ''));
        if ($slug !== '') {
            return MapStory::query()->where('slug', $slug)->first()
                ?? throw new ToolArgumentException("No map story with slug '{$slug}'. Pass entity_id to find an entity's stories, or create one with create_map_story.");
        }

        $ref = trim((string) ($args['entity_id'] ?? ''));
        $chronicle = trim((string) ($args['chronicle_id'] ?? ''));
        $query = MapStory::query()->orderBy('year');
        if ($ref !== '') {
            $entityId = EntityReferenceResolver::isUuid($ref) ? strtolower($ref)
                : Entity::query()->where('name', $ref)->value('entity_id');
            $query->where('entity_id', $entityId ?? '00000000-0000-0000-0000-000000000000');
        } elseif ($chronicle !== '' && EntityReferenceResolver::isUuid($chronicle)) {
            $query->where('chronicle_id', strtolower($chronicle));
        } else {
            throw new ToolArgumentException('Give the story `slug` (or an `entity_id` / `chronicle_id` that has one).');
        }

        $stories = $query->get(['story_id', 'slug', 'title', 'kind', 'year', 'entity_id', 'chronicle_id', 'document', 'step_count', 'synced_at', 'edited_at', 'file_hash']);
        if ($stories->isEmpty()) {
            throw new ToolArgumentException('That record has no map story yet. Create one with create_map_story.');
        }
        if ($stories->count() > 1) {
            throw new ToolArgumentException('It has several map stories — pass one `slug`: '
                .$stories->map(fn (MapStory $s) => "{$s->slug} ({$s->kind}, {$s->title})")->implode('; '));
        }

        return $stories->first();
    }
}
