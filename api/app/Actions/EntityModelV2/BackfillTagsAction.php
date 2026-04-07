<?php

declare(strict_types=1);

namespace App\Actions\EntityModelV2;

use App\Models\Entity;
use App\Models\EntityTag;

class BackfillTagsAction
{
    public function __invoke(Entity $entity): int
    {
        $tags = $entity->tags;

        if (! is_array($tags) || $tags === []) {
            return 0;
        }

        EntityTag::query()->where('entity_id', $entity->entity_id)->delete();

        $inserted = 0;

        foreach (array_unique($tags) as $tag) {
            if (! is_string($tag) || trim($tag) === '') {
                continue;
            }

            EntityTag::query()->create([
                'entity_id' => $entity->entity_id,
                'tag' => trim($tag),
            ]);

            $inserted++;
        }

        return $inserted;
    }
}
