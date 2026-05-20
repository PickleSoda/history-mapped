<?php

declare(strict_types=1);

namespace App\Actions\Entity;

use App\Models\Entity;
use App\Models\EntityTag;

class BackfillTagsAction
{
    public function __invoke(Entity $entity): int
    {
        $tags = $entity->entityTags->pluck('tag')->filter(fn ($t) => is_string($t) && trim($t) !== '')->all();

        if ($tags === []) {
            return 0;
        }

        EntityTag::query()->where('entity_id', $entity->entity_id)->delete();

        $inserted = 0;

        foreach (array_unique($tags) as $tag) {
            EntityTag::query()->create([
                'entity_id' => $entity->entity_id,
                'tag' => trim($tag),
            ]);

            $inserted++;
        }

        return $inserted;
    }
}
