<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Actions\Tag\SyncTagsAction;
use App\Enums\TagSource;
use App\Models\Entity;

class BackfillTagsAction
{
    public function __construct(private readonly SyncTagsAction $syncTags) {}

    /**
     * Re-normalise an entity's manual tags against the vocabulary (derived tags
     * are owned by `tags:sync`).
     */
    public function __invoke(Entity $entity): int
    {
        $tags = $entity->entityTags
            ->filter(fn ($t): bool => $t->source === TagSource::Manual->value)
            ->pluck('tag')
            ->all();

        if ($tags === []) {
            return 0;
        }

        return count(($this->syncTags)($entity, $tags, TagSource::Manual));
    }
}
